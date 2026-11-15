import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest


def load_module():
    path = Path(__file__).resolve().parents[2] / "scripts/resume_research_collectors.py"
    spec = importlib.util.spec_from_file_location("resume_research_collectors_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def recovery(tmp_path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    base, state = tmp_path / "selection", tmp_path / "runtime"
    base.mkdir()
    source = base / "manifest.json"
    source.write_text("{}", encoding="utf-8")
    calls = []

    def snapshot(selected):
        calls.append(selected)
        return (
            "run-exact",
            [{"candidate_id": "SPOTIFY:a", "reason": "text_missing"}],
            {str(source): module.file_hash(source)},
        )

    return module, base, state, source, calls, snapshot


def test_new_campaign_freezes_global_selection_scope_and_has_no_paid_authorization(recovery):
    module, base, state, _source, calls, snapshot = recovery
    before = datetime.now(UTC)
    campaign = module.freeze_campaign(state, base, hours=12, snapshot=snapshot, now=before)
    assert calls == [base]
    assert campaign["selection_root"] == str(base)
    assert campaign["staging_run_id"] == "run-exact"
    assert campaign["candidate_count"] == 1
    assert campaign["paid_calls_authorized"] == 0
    assert campaign["classification_ready"] is False
    assert datetime.fromisoformat(campaign["ends_at"]) == before + timedelta(hours=12)
    module.verify_campaign(campaign)
    targets = [json.loads(row) for row in (state / "candidate-ids.jsonl").read_text().splitlines()]
    assert targets == [{"candidate_id": "SPOTIFY:a", "reason": "text_missing"}]


def test_resume_does_not_reset_campaign_clock_or_overwrite_prior_targets(recovery):
    module, base, state, _source, calls, snapshot = recovery
    first = module.freeze_campaign(state, base, hours=12, snapshot=snapshot)
    second = module.freeze_campaign(state, base, hours=24, snapshot=snapshot)
    assert first == second
    assert calls == [base]


def test_existing_campaign_cannot_switch_selection(recovery):
    module, base, state, _source, _calls, snapshot = recovery
    module.freeze_campaign(state, base, hours=12, snapshot=snapshot)
    with pytest.raises(ValueError, match="different selection"):
        module.freeze_campaign(state, base / "other", hours=12, snapshot=snapshot)


@pytest.mark.parametrize("changed", ["source", "targets"])
def test_mutated_inputs_block_resumption_before_collection(recovery, changed):
    module, base, state, source, _calls, snapshot = recovery
    campaign = module.freeze_campaign(state, base, hours=12, snapshot=snapshot)
    path = source if changed == "source" else state / "candidate-ids.jsonl"
    path.write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="input changed"):
        module.verify_campaign(campaign)


def test_expired_window_is_not_silently_extended(recovery):
    module, base, state, _source, _calls, snapshot = recovery
    campaign = module.freeze_campaign(
        state, base, hours=1, snapshot=snapshot, now=datetime(2020, 1, 1, tzinfo=UTC)
    )
    with pytest.raises(ValueError, match="campaign expired"):
        module.verify_campaign(campaign)


@pytest.mark.parametrize("hours", [0, -1, 25])
def test_invalid_campaign_windows_do_not_create_queue(recovery, hours):
    module, base, state, _source, calls, snapshot = recovery
    with pytest.raises(ValueError):
        module.freeze_campaign(state, base, hours=hours, snapshot=snapshot)
    assert not state.exists()
    assert calls == []


def test_failed_phase_is_not_mistaken_for_successful_checkpoint(recovery):
    module, _base, state, *_ = recovery
    state.mkdir()
    assert module.phase_succeeded(state) is False
    (state / "exit.json").write_text('{"returncode":1}')
    assert module.phase_succeeded(state) is False
    (state / "exit.json").write_text('{"returncode":0}')
    assert module.phase_succeeded(state) is True


def test_active_worker_discovery_reports_only_safe_identity_not_commandline(recovery, monkeypatch):
    module, *_ = recovery
    raw = [
        {"ProcessId": 222, "CommandLine": "python scripts/autonomous_lyrics.py --private flag"},
        {"ProcessId": module.os.getpid(), "CommandLine": "autonomous_lyrics.py"},
        {"ProcessId": 333, "CommandLine": "python unrelated.py"},
    ]
    monkeypatch.setattr(
        module.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=json.dumps(raw))
    )
    assert module.active_workers() == [{"pid": 222, "worker": "autonomous_lyrics.py"}]


def test_process_logs_and_exit_checkpoint_are_written_without_shell_or_visible_window(
    recovery, monkeypatch
):
    module, _base, state, *_ = recovery
    captured = {}

    def start(command, **kwargs):
        captured.update(command=command, **kwargs)
        return SimpleNamespace(pid=444, wait=lambda: 0)

    monkeypatch.setattr(module.subprocess, "Popen", start)
    module.run_job([sys.executable, "worker.py"], state, {"TOKEN": "private"})
    assert captured["creationflags"] == module.subprocess.CREATE_NO_WINDOW
    assert "shell" not in captured
    process = json.loads((state / "process.json").read_text())
    assert process["pid"] == 444
    assert "private" not in (state / "process.json").read_text()
    assert module.phase_succeeded(state)
