"""Continuous coordination of existing batch interfaces with durable checkpoints."""

import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

from chart_observatory.lyrics.batch_service import CostBudgetExceeded

# Individual response failures; job/authentication/integrity failures still stop coordination.
TECHNICAL_RESPONSE_ERRORS = frozenset(
    {
        "batch_malformed_response",
        "batch_missing_output",
        "batch_incomplete_response",
        "batch_missing_usage",
        "batch_schema_validation_error",
        "batch_provider_error",
    }
)


@dataclass(frozen=True)
class ContinuousRun:
    id: str
    state: str
    request_count: int
    completed_count: int | None = None
    provider_job_name: str | None = None


class ContinuousBackend(Protocol):
    def runs(self, ids: list[str]) -> list[ContinuousRun]: ...
    def refresh(self, run_id: str) -> ContinuousRun: ...
    def reconcile(self, run_id: str) -> None: ...
    def budget(self) -> tuple[Decimal, Decimal]: ...
    def candidate_prefix(self, baseline: str, excluded_runs: list[str]) -> int: ...
    def prepare(self, baseline: str, limit: int) -> list[ContinuousRun]: ...
    def submit(self, run_id: str) -> ContinuousRun: ...


class ContinuityError(RuntimeError):
    """An interrupted operation needs inspection before further submissions."""


@contextmanager
def exclusive_controller_lock(path: Path) -> Iterator[bool]:
    """Return false for a competing coordinator, without reading its locked byte."""
    import msvcrt

    with path.open("a+b") as handle:
        try:
            if os.fstat(handle.fileno()).st_size == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            yield False
            return
        yield True


class ContinuousBatchController:
    def __init__(
        self,
        backend: ContinuousBackend,
        save: Callable[[dict[str, Any]], None],
        *,
        max_inflight: int = 4,
    ) -> None:
        if max_inflight < 1:
            raise ValueError("max_inflight must be positive")
        self.backend = backend
        self.save = save
        self.max_inflight = max_inflight

    def tick(self, state: dict[str, Any]) -> bool:
        """Advance once; return whether continuous polling should continue."""
        if state.get("preparation_in_progress"):
            raise ContinuityError("interrupted preparation requires inspection")
        ids = state["retry_run_ids"]
        summaries = state.setdefault("run_summaries", {})
        failed = False
        for run in self.backend.runs(ids):
            if run.state in {"imported", "cleaned"}:
                continue
            if run.state in {"submitted", "running"}:
                run = self.backend.refresh(run.id)
            summaries.setdefault(run.id, {}).update(
                state=run.state,
                request_count=run.request_count,
                completed_count=run.completed_count,
                provider_job_name=run.provider_job_name,
            )
            if run.state in {"succeeded", "failed", "expired", "cancelled"}:
                self.backend.reconcile(run.id)
                summaries[run.id]["state"] = "imported"
                failed |= run.state != "succeeded"
            elif run.state == "uploaded":
                if state.get("quality_hold") or state.get("controller_stop_requested"):
                    continue
                if summaries[run.id].get("submission_attempted"):
                    raise ContinuityError("ambiguous submission requires inspection")
                self._submit(run, state)
            elif run.state not in {"submitted", "running"}:
                raise ContinuityError("unrecognized run state requires inspection")
        if failed:
            state.update(status="failed", stop_reason="provider_job_failed")
            self.save(state)
            return False
        pending = sum(run.state not in {"imported", "cleaned"} for run in self.backend.runs(ids))
        if state.get("quality_hold"):
            pending = sum(run.state in {"submitted", "running"} for run in self.backend.runs(ids))
            state.update(status="running" if pending else "stopped", stop_reason="quality_hold")
            self.save(state)
            return bool(pending)
        state.update(status="running", stop_reason=None)
        while pending < self.max_inflight:
            if state.get("controller_stop_requested"):
                state.update(status="stopped", stop_reason="controller_stop_requested")
                self.save(state)
                return False
            remaining, unit_cost = self.backend.budget()
            if unit_cost <= 0 or not unit_cost.is_finite() or not remaining.is_finite():
                raise ContinuityError("invalid budget estimate")
            if remaining <= 0 or state.get("budget_blocked_remaining_usd") == str(remaining):
                state.update(status="running" if pending else "budget_exhausted")
                self.save(state)
                return bool(pending)
            baseline = None
            candidate_count = 0
            for prior in state["baseline_run_ids"]:
                candidate_count = self.backend.candidate_prefix(prior, ids)
                if candidate_count:
                    baseline = prior
                    break
            if baseline is None:
                state.update(status="running" if pending else "completed")
                self.save(state)
                return bool(pending)
            limit = min(190_000, candidate_count, max(1, int(remaining / unit_cost)))
            while True:
                state["preparation_in_progress"] = {"baseline": baseline, "limit": limit}
                self.save(state)
                if state.get("controller_stop_requested"):
                    state.pop("preparation_in_progress")
                    state.update(status="stopped", stop_reason="controller_stop_requested")
                    self.save(state)
                    return False
                try:
                    prepared = self.backend.prepare(baseline, limit)
                except CostBudgetExceeded:
                    state.pop("preparation_in_progress")
                    self.save(state)
                    if limit == 1:
                        state["budget_blocked_remaining_usd"] = str(self.backend.budget()[0])
                        state.update(status="running" if pending else "budget_exhausted")
                        self.save(state)
                        return bool(pending)
                    limit = max(1, limit // 2)
                    continue
                # IDs and successful preparation become one durable checkpoint.
                for run in prepared:
                    if run.id in ids:
                        raise ContinuityError("preparation returned a duplicate run")
                    ids.append(run.id)
                    summaries[run.id] = {"state": run.state, "request_count": run.request_count}
                state.pop("preparation_in_progress")
                state.pop("budget_blocked_remaining_usd", None)
                self.save(state)
                if state.get("controller_stop_requested"):
                    state.update(status="stopped", stop_reason="controller_stop_requested")
                    self.save(state)
                    return False
                if not prepared or pending + len(prepared) > self.max_inflight:
                    raise ContinuityError("unexpected number of prepared shards")
                for run in prepared:
                    self._submit(run, state)
                    pending += 1
                break
        self.save(state)
        return True

    def _submit(self, run: ContinuousRun, state: dict[str, Any]) -> None:
        summary = state["run_summaries"][run.id]
        summary["submission_attempted"] = True
        self.save(state)
        submitted = self.backend.submit(run.id)
        summary.update(state=submitted.state, provider_job_name=submitted.provider_job_name)
        state.update(
            latest_run_id=run.id,
            retry_run_state=submitted.state,
            provider_job_name=submitted.provider_job_name,
            request_count=run.request_count,
            completed_count=submitted.completed_count,
            progress_percent=None,
        )
        self.save(state)
        if submitted.state not in {"submitted", "running", "succeeded"}:
            raise ContinuityError("provider rejected submission")
