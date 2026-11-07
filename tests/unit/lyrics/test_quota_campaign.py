import json
from datetime import UTC, datetime, timedelta

import pytest

import chart_observatory.quota_campaign as campaign


@pytest.fixture
def config(tmp_path, monkeypatch):
    path = tmp_path / "campaign.json"
    monkeypatch.setattr(campaign, "CAMPAIGN", path)
    monkeypatch.setattr(campaign, "ROOT", tmp_path)
    return path


def test_deadline_survives_restart_and_never_becomes_negative(config):
    now = datetime(2026, 11, 1, 23, tzinfo=UTC)
    config.write_text(json.dumps(dict(ends_at=(now + timedelta(hours=24)).isoformat())))
    assert campaign.remaining_seconds(now) == 86400
    assert campaign.remaining_seconds(now + timedelta(hours=25)) == 0


def test_deadline_requires_timezone(config):
    config.write_text('{"ends_at":"2026-11-02T23:00:00"}')
    with pytest.raises(ValueError, match="timezone"):
        campaign.remaining_seconds()


def test_frozen_source_change_stops_campaign(config):
    import hashlib

    source = config.parent / "ranking.csv"
    source.write_bytes(b"original")
    config.write_text(
        json.dumps(dict(frozen_inputs={"ranking.csv": hashlib.sha256(b"original").hexdigest()}))
    )
    campaign.verify_frozen_inputs()
    source.write_bytes(b"other song")
    with pytest.raises(ValueError, match="changed"):
        campaign.verify_frozen_inputs()


def test_reference_path_cannot_escape_project(config):
    config.write_text(json.dumps(dict(frozen_inputs={"../elsewhere": "bad"})))
    with pytest.raises(ValueError, match="outside"):
        campaign.verify_frozen_inputs()


def test_campaign_override_is_scoped_and_does_not_change_old_manifest(config, monkeypatch):
    replacement = config.parent / "new-campaign.json"
    config.write_text('{"ends_at":"2026-11-02T00:00:00Z"}')
    replacement.write_text('{"ends_at":"2026-11-08T00:00:00Z"}')
    monkeypatch.setenv("CHART_OBSERVATORY_CAMPAIGN_PATH", str(replacement))
    assert campaign.campaign()["ends_at"] == "2026-11-08T00:00:00Z"
    assert json.loads(config.read_text())["ends_at"] == "2026-11-02T00:00:00Z"
    replacement.unlink()
    with pytest.raises(FileNotFoundError):
        campaign.campaign()


def test_campaign_override_cannot_leave_repository(config, monkeypatch):
    monkeypatch.setenv("CHART_OBSERVATORY_CAMPAIGN_PATH", str(config.parent.parent / "other.json"))
    with pytest.raises(ValueError, match="outside"):
        campaign.campaign()


def test_import_supervisor_records_real_child_exit_offline(tmp_path):
    import importlib.util
    import sys
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "all_import_supervisor",
        Path(__file__).resolve().parents[3] / "scripts/import_all_quota_lyrics.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert (
        module.run_job(
            [sys.executable, "-c", "print('offline supervisor fixture')"], tmp_path, None
        )
        == 0
    )
    assert json.loads((tmp_path / "process.json").read_text())["pid"] > 0
    assert json.loads((tmp_path / "exit.json").read_text())["returncode"] == 0
