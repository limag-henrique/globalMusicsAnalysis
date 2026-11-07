import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest


@pytest.fixture
def discovery(monkeypatch):
    scripts = Path(__file__).resolve().parents[3] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location(
        "chart_gap_test", scripts / "discover_quota_chart_gaps.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def capture():
    return dict(
        country_code="IL",
        observed_country_code="IL",
        period_end="2023-12-28",
        observed_period_end="2023-12-28",
        source_url="https://charts.youtube.com/charts/TopSongs/il/weekly/20231228",
        rows=[dict(rank=1, title="Song", artist="Artist", metric_value=100)],
    )


def test_approved_weeks_only(discovery):
    assert max(discovery.weeks(2026)).isoformat() == "2026-10-15"
    assert all(d.year == 2018 for d in discovery.weeks(2018))
    with pytest.raises(ValueError):
        list(discovery.weeks(2017))


@pytest.mark.parametrize(
    "field,value",
    [
        ("observed_country_code", "GLOBAL"),
        ("observed_period_end", "2024-12-26"),
        ("source_url", "https://charts.youtube.com/charts/TopSongs/us/weekly/20231228"),
        ("period_end", "2026-10-22"),
    ],
)
def test_wrong_market_calendar_and_cutoff_rejected(discovery, field, value):
    doc = capture()
    doc[field] = value
    with pytest.raises(ValueError):
        discovery.validate_capture(doc)


def test_duplicate_display_identity_preserved_in_quarantine(discovery):
    doc = capture()
    doc["rows"].append(dict(doc["rows"][0], rank=2))
    result = discovery.validate_capture(doc)
    assert len(result["rows"]) == 2
    assert result["repeated_display_identities"]
    assert result["annual_rank_certified"] is False
    assert result["classification_ready"] is False


def test_incomplete_year_never_emits_provisional_ranking(discovery):
    result = discovery.annual_discovery(dict(country_code="IL", year=2023, quota=120), {})
    assert result["blocker"] == "incomplete_weekly_history"
    assert not result["candidates"]


def test_complete_history_keeps_quota_and_identity_blocker(discovery, tmp_path, monkeypatch):
    from datetime import date

    monkeypatch.setattr(discovery, "STATE", tmp_path)
    monkeypatch.setattr(discovery, "weeks", lambda year: [date(2023, 12, 28)])
    (tmp_path / "captures").mkdir()
    doc = capture()
    doc["rows"].append(dict(rank=2, title="Second", artist="Artist", metric_value=50))
    raw = json.dumps(doc).encode()
    digest = hashlib.sha256(raw).hexdigest()
    path = tmp_path / "captures" / f"{digest}.json"
    path.write_bytes(raw)
    checkpoint = {"IL/2023-12-28": dict(sha256=digest)}
    result = discovery.annual_discovery(dict(country_code="IL", year=2023, quota=1), checkpoint)
    assert len(result["candidates"]) == 1
    assert result["candidates"][0]["title"] == "Song"
    assert result["annual_rank_certified"] is False
    path.write_bytes(raw + b" ")
    with pytest.raises(ValueError, match="hash mismatch"):
        discovery.annual_discovery(dict(country_code="IL", year=2023, quota=1), checkpoint)


def test_timeout_retry_preserves_history_and_does_not_retry_identity_error(
    discovery, tmp_path, monkeypatch
):
    monkeypatch.setattr(discovery, "STATE", tmp_path)
    original = {
        "IL/2023-12-28": dict(status="unresolved_source", error="TimeoutError"),
        "IL/2023-12-21": dict(status="unresolved_source", error="ValueError"),
    }
    path = tmp_path / "checkpoint.json"
    path.write_text(json.dumps(original), encoding="utf-8")
    discovery.prepare_timeout_retry()
    assert list(json.loads(path.read_text(encoding="utf-8"))) == ["IL/2023-12-21"]
    history = json.loads((tmp_path / "timeout-retry-history.json").read_text(encoding="utf-8"))
    assert history[0]["previous_attempts"]["IL/2023-12-28"] == original["IL/2023-12-28"]
