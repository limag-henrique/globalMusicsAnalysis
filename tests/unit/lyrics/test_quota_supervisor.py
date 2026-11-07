import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def supervisor(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[3] / "scripts/supervise_quota_recovery.py"
    spec = importlib.util.spec_from_file_location("quota_supervisor_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "STATE", tmp_path)
    return module


def test_existing_wrapper_blocks_duplicate(supervisor, monkeypatch):
    s = supervisor
    monkeypatch.setattr(s, "jobs", lambda: [("native", "worker.py", [], s.STATE / "none")])
    owners = [
        dict(
            CommandLine=f'"{s.ROOT}/.venv/python.exe" wrapper.py worker.py',
            ProcessId=42,
            CreationDate="original",
        )
    ]
    monkeypatch.setattr(s, "execute", lambda *args: pytest.fail("duplicated worker"))
    actions = s.tick({}, owners, False)
    assert actions[0]["processes"][0]["CreationDate"] == "original"


def test_reboot_resumes_missing_worker(supervisor, monkeypatch):
    s = supervisor
    monkeypatch.setattr(
        s, "jobs", lambda: [("native", "worker.py", ["worker.py"], s.STATE / "none")]
    )
    actions = s.tick({}, [], False)
    assert actions[0]["stage"] == "ready_to_resume"


def test_access_pause_is_terminal(supervisor, monkeypatch):
    s = supervisor
    proof = s.STATE / "proof.json"
    proof.write_text('{"stage":"provider_access_paused"}', encoding="utf-8")
    monkeypatch.setattr(s, "jobs", lambda: [("native", "worker.py", [], proof)])
    checkpoint = {}
    s.tick(checkpoint, [], False)
    assert checkpoint["native"] == "done"


def test_failed_dependency_stops_chain(supervisor, monkeypatch):
    s = supervisor
    proof = s.STATE / "proof.json"
    proof.write_text('{"returncode":1}', encoding="utf-8")
    monkeypatch.setattr(s, "jobs", lambda: [("replay", "worker.py", [], proof)])
    with pytest.raises(RuntimeError, match="previous worker failed"):
        s.tick({}, [], False)


def test_expired_campaign_does_not_start_another_worker(supervisor, monkeypatch):
    s = supervisor
    monkeypatch.setattr(s, "jobs", lambda: [])
    monkeypatch.setattr(s, "remaining_seconds", lambda: 0)
    monkeypatch.setattr(s.subprocess, "Popen", lambda *a, **kw: pytest.fail("past deadline"))
    assert s.tick({}, [], True)[0]["stage"] == "campaign_deadline_reached"


def test_duplicate_observation_keeps_original_process_creation(supervisor):
    s = supervisor
    process = dict(
        CommandLine=f'"{s.ROOT}/.venv/python.exe" scripts/autonomous_lyrics.py',
        ProcessId=123,
        CreationDate="known-original",
    )
    assert s.active([process], "scripts/autonomous_lyrics.py") == [process]
