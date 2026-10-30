import importlib
import json
from pathlib import Path

import polars as pl
import pytest


@pytest.mark.parametrize("prior_status,expected_targets,deferred", [
    ("candidate_pending_validation", 1, 2), ("not_found", 2, 1),
])
def test_preparation_reuses_acquisition_without_promoting_it_and_retains_memberships(
    tmp_path, monkeypatch, prior_status, expected_targets, deferred,
):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[3] / "scripts"))
    preparation = importlib.import_module("prepare_annual_revision")
    root, raw, historical = tmp_path / "root", tmp_path / "raw", tmp_path / "history"
    country = root / "research/article/analysis-final/country-metrics.parquet"
    country.parent.mkdir(parents=True)
    pl.DataFrame({"market_code": ["BR"]}).write_parquet(country)
    raw.mkdir()
    (raw / "inventory_manifest.json").write_text(json.dumps({
        "periods": [{"end": "2026-10-15"}],
    }))
    (root / "config").mkdir()
    (root / "config/lyrics_identity_quarantine.json").write_text('{"entries": []}')
    (historical / "acquisition").mkdir(parents=True)
    (historical / "recovery-targets.jsonl").write_text(json.dumps({
        "recording_id": "SPOTIFY:1", "document_id": "old-doc", "lyrics_hash": "a" * 64,
    }) + "\n")
    (historical / "acquisition/acquisition.jsonl").write_text(json.dumps({
        "status": prior_status, "original_document_id": "old-doc",
    }) + "\n")
    first = dict(country_code="BR", year=2025, platform="SPOTIFY", window="full_year",
                 position=1, candidate_id="SPOTIFY:1", title="One", artist="Artist",
                 recording_id=None, coverage_status="COMPLETE")
    second = {**first, "position": 2, "candidate_id": "SPOTIFY:2", "title": "Two"}
    rows = [first, second, {**second, "window": "equivalent"},
            {**first, "candidate_id": "SPOTIFY:3", "position": 3,
             "coverage_status": "INCOMPLETE"},
            {**first, "candidate_id": "SPOTIFY:4", "position": 81}]
    monkeypatch.setattr(preparation, "ROOT", root)
    monkeypatch.setattr(preparation, "RAW", raw)
    monkeypatch.setattr(preparation, "HISTORICAL", historical)
    monkeypatch.setattr(preparation, "daily_candidates", lambda *args: (rows, []))
    monkeypatch.setattr(preparation, "weekly_candidates", lambda *args: ([], []))
    monkeypatch.setattr(preparation, "database_metadata", lambda *args: (
        {}, {}, {"status": "unavailable"}, [],
    ))
    monkeypatch.setattr(preparation, "load_review_evidence", lambda: [])
    output = tmp_path / "output"
    preparation.prepare(output, 120, None)
    queue = list(preparation.jsonl(output / "recovery-targets.jsonl"))
    assert len(queue) == expected_targets
    assert queue[0]["recording_id"] == "SPOTIFY:2"
    assert len(queue[0]["chart_bindings"]) == 2
    assert list(preparation.jsonl(output / "classification_queue.jsonl")) == []
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["existing_acquisition_reused"] == {prior_status: 1}
    assert manifest["paid_calls"] == 0
    assert manifest["deferred_reserve_or_incomplete_identities"] == deferred
    assert manifest["effective_cutoff"] == "2026-10-15"
