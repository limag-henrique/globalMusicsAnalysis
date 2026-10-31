import json
from pathlib import Path

from chart_observatory.runtime_status import publish_status


def test_status_retries_sharing_failure_and_publishes_complete_json(tmp_path, monkeypatch):
    path = tmp_path / "status.json"
    path.write_text('{"stage":"old"}', encoding="utf-8")
    replace = Path.replace
    attempts = []

    def transient(self, target):
        attempts.append(target)
        assert json.loads(path.read_text())["stage"] == "old"
        if len(attempts) < 3:
            raise PermissionError("sharing violation")
        return replace(self, target)

    monkeypatch.setattr(Path, "replace", transient)
    monkeypatch.setattr("chart_observatory.runtime_status.time.sleep", lambda seconds: None)
    assert publish_status(path, {"stage": "recovering", "counter": 23})
    assert len(attempts) == 3
    assert json.loads(path.read_text()) == {"stage": "recovering", "counter": 23}
    assert not list(tmp_path.glob("*.part"))


def test_unavailable_status_file_does_not_abort_work_or_destroy_previous_status(
    tmp_path, monkeypatch, capsys
):
    path = tmp_path / "status.json"
    path.write_text('{"stage":"old"}', encoding="utf-8")

    def blocked(self, target):
        raise PermissionError("sharing violation")

    monkeypatch.setattr(Path, "replace", blocked)
    monkeypatch.setattr("chart_observatory.runtime_status.time.sleep", lambda seconds: None)
    assert publish_status(path, {"stage": "recovering"}, attempts=2) is False
    assert json.loads(path.read_text()) == {"stage": "old"}
    assert "durable work continues" in capsys.readouterr().err
    assert not list(tmp_path.glob("*.part"))
