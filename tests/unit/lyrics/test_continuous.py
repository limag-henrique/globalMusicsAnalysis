import sys
from decimal import Decimal

import pytest

from chart_observatory.lyrics.batch_service import CostBudgetExceeded
from chart_observatory.lyrics.continuous import (
    ContinuityError,
    ContinuousBatchController,
    ContinuousRun,
    exclusive_controller_lock,
)


class Backend:
    def __init__(self) -> None:
        self.items = {"old": ContinuousRun("old", "succeeded", 10)}
        self.remaining = Decimal("0")
        self.events: list[tuple[str, object]] = []

    def runs(self, ids: list[str]) -> list[ContinuousRun]:
        return [self.items[key] for key in ids]

    def refresh(self, run_id: str) -> ContinuousRun:
        self.events.append(("refresh", run_id))
        return self.items[run_id]

    def reconcile(self, run_id: str) -> None:
        self.events.append(("reconcile", run_id))
        self.items[run_id] = ContinuousRun(run_id, "imported", 10)
        self.remaining = Decimal("1")

    def budget(self) -> tuple[Decimal, Decimal]:
        return self.remaining, Decimal("0.002")

    def candidate_prefix(self, baseline: str, excluded_runs: list[str]) -> int:
        return 1000

    def prepare(self, baseline: str, limit: int) -> list[ContinuousRun]:
        self.events.append(("prepare", limit))
        self.remaining -= Decimal("0.002") * limit
        item = ContinuousRun("new", "uploaded", limit)
        self.items[item.id] = item
        return [item]

    def submit(self, run_id: str) -> ContinuousRun:
        self.events.append(("submit", run_id))
        item = self.items[run_id]
        self.items[run_id] = ContinuousRun(item.id, "submitted", item.request_count)
        return self.items[run_id]


def test_continuous_run_reconciles_and_uses_affordable_capacity_above_200() -> None:
    backend = Backend()
    state = {"retry_run_ids": ["old"], "baseline_run_ids": ["baseline"], "quality_hold": False}
    saved = []
    controller = ContinuousBatchController(backend, lambda state: saved.append(dict(state)))
    assert controller.tick(state)
    assert backend.events == [("reconcile", "old"), ("prepare", 500), ("submit", "new")]
    assert state["retry_run_ids"] == ["old", "new"]
    assert state["status"] == "running"
    assert saved


def test_quality_hold_stops_without_submitting_uploaded_inputs() -> None:
    backend = Backend()
    backend.items["old"] = ContinuousRun("old", "uploaded", 10)
    state = {"retry_run_ids": ["old"], "baseline_run_ids": ["baseline"], "quality_hold": True}
    assert not ContinuousBatchController(backend, lambda state: None).tick(state)
    assert backend.events == []
    assert state["status"] == "stopped"


def test_stop_request_received_during_checkpoint_prevents_new_preparation() -> None:
    backend = Backend()
    backend.items["old"] = ContinuousRun("old", "imported", 10)
    backend.remaining = Decimal("1")
    state = {"retry_run_ids": ["old"], "baseline_run_ids": ["baseline"]}

    def save(value):
        value["controller_stop_requested"] = True

    assert not ContinuousBatchController(backend, save).tick(state)
    assert backend.events == []
    assert state["status"] == "stopped"


def test_restart_does_not_resubmit_an_ambiguous_attempt() -> None:
    backend = Backend()
    backend.items["old"] = ContinuousRun("old", "uploaded", 10)
    state = {
        "retry_run_ids": ["old"],
        "baseline_run_ids": ["baseline"],
        "run_summaries": {"old": {"submission_attempted": True}},
    }
    with pytest.raises(ContinuityError, match="ambiguous"):
        ContinuousBatchController(backend, lambda state: None).tick(state)
    assert backend.events == []


def test_ambiguous_submit_is_checkpointed_before_network_failure() -> None:
    class FailingBackend(Backend):
        def submit(self, run_id: str) -> ContinuousRun:
            self.events.append(("submit", run_id))
            raise RuntimeError("network outcome unknown")

    backend = FailingBackend()
    backend.items["old"] = ContinuousRun("old", "imported", 10)
    backend.remaining = Decimal("1")
    state = {"retry_run_ids": ["old"], "baseline_run_ids": ["baseline"]}
    controller = ContinuousBatchController(backend, lambda state: None)
    with pytest.raises(RuntimeError, match="network"):
        controller.tick(state)
    assert state["retry_run_ids"] == ["old", "new"]
    assert state["run_summaries"]["new"]["submission_attempted"]
    with pytest.raises(ContinuityError, match="ambiguous"):
        controller.tick(state)
    assert backend.events == [("prepare", 500), ("submit", "new")]


def test_active_job_limit_prevents_new_reservations() -> None:
    backend = Backend()
    backend.items["old"] = ContinuousRun("old", "submitted", 10)
    backend.remaining = Decimal("1")
    state = {"retry_run_ids": ["old"], "baseline_run_ids": ["baseline"]}
    assert ContinuousBatchController(backend, lambda state: None, max_inflight=1).tick(state)
    assert backend.events == [("refresh", "old")]


def test_budget_rejection_reduces_size_without_uploading_rejected_jobs() -> None:
    class ConservativeBackend(Backend):
        def prepare(self, baseline: str, limit: int) -> list[ContinuousRun]:
            if limit > 100:
                self.events.append(("rejected", limit))
                raise CostBudgetExceeded("actual reserve exceeds remaining budget")
            return super().prepare(baseline, limit)

    backend = ConservativeBackend()
    backend.items["old"] = ContinuousRun("old", "imported", 10)
    backend.remaining = Decimal("1")
    state = {"retry_run_ids": ["old"], "baseline_run_ids": ["baseline"]}
    assert ContinuousBatchController(backend, lambda state: None, max_inflight=1).tick(state)
    assert backend.events == [
        ("rejected", 500),
        ("rejected", 250),
        ("rejected", 125),
        ("prepare", 62),
        ("submit", "new"),
    ]


def test_imported_job_is_never_refreshed_remotely() -> None:
    backend = Backend()
    backend.items["old"] = ContinuousRun("old", "imported", 10)
    state = {"retry_run_ids": ["old"], "baseline_run_ids": ["baseline"]}
    assert not ContinuousBatchController(backend, lambda state: None).tick(state)
    assert backend.events == []
    assert state["status"] == "budget_exhausted"


def test_interrupted_preparation_requires_inspection() -> None:
    backend = Backend()
    state = {
        "retry_run_ids": ["old"],
        "baseline_run_ids": ["baseline"],
        "preparation_in_progress": {"limit": 500},
    }
    with pytest.raises(ContinuityError, match="interrupted"):
        ContinuousBatchController(backend, lambda state: None).tick(state)
    assert backend.events == []


def test_provider_failure_preserves_outputs_and_stops_new_jobs() -> None:
    backend = Backend()
    backend.items["old"] = ContinuousRun("old", "failed", 10)
    state = {"retry_run_ids": ["old"], "baseline_run_ids": ["baseline"]}
    assert not ContinuousBatchController(backend, lambda state: None).tick(state)
    assert backend.events == [("reconcile", "old")]
    assert state["status"] == "failed"


def test_immediate_submission_failure_prevents_further_jobs() -> None:
    class RejectedBackend(Backend):
        def submit(self, run_id: str) -> ContinuousRun:
            self.events.append(("submit", run_id))
            return ContinuousRun(run_id, "failed", 500)

    backend = RejectedBackend()
    backend.items["old"] = ContinuousRun("old", "imported", 10)
    backend.remaining = Decimal("1")
    state = {"retry_run_ids": ["old"], "baseline_run_ids": ["baseline"]}
    with pytest.raises(ContinuityError, match="rejected submission"):
        ContinuousBatchController(backend, lambda state: None).tick(state)
    assert backend.events == [("prepare", 500), ("submit", "new")]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows byte-range locks")
def test_second_controller_cannot_acquire_the_active_lock(tmp_path) -> None:
    path = tmp_path / "continuous.lock"
    with exclusive_controller_lock(path) as first:
        assert first
        with exclusive_controller_lock(path) as second:
            assert not second
    with exclusive_controller_lock(path) as after_close:
        assert after_close
