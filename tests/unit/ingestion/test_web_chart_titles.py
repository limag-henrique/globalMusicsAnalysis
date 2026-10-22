"""Public acquisition boundaries: period/market identity and lossless title import."""

from pathlib import Path

import pytest


def test_limited_collection_does_not_claim_complete(modules):
    _, scraper = modules
    assert scraper.collection_status(100, 5, []) == "PARTIAL"
    assert scraper.collection_status(5, 5, []) == "COMPLETE"
    assert scraper.collection_status(5, 5, [{"error": "timeout"}]) == "PARTIAL"


def test_pause_request_does_not_start_collection(modules, monkeypatch, tmp_path):
    import sys

    _, scraper = modules
    monkeypatch.setattr(sys, "argv", ["scraper", "--pause", "--output", str(tmp_path)])
    monkeypatch.setattr(scraper, "collect", lambda _: pytest.fail("pause started collection"))
    scraper.main()
    assert (tmp_path / "pause.request").exists()


def test_paused_collection_cannot_claim_complete(modules):
    _, scraper = modules
    assert scraper.collection_status(5, 5, [], paused=True) == "PAUSED"


@pytest.mark.parametrize("title", [None, True, 123])
def test_nontext_titles_are_rejected_instead_of_imported(modules, snapshot, title):
    importer, _ = modules
    snapshot["rows"][0]["title"] = title
    with pytest.raises(ValueError, match="title"):
        importer.validate_snapshot(snapshot)


def test_coverage_requires_inventory_and_deduplicates_verified_cells(modules, snapshot, tmp_path):
    import json

    import report_web_chart_coverage

    for name in ("one", "two"):
        (tmp_path / f"YOUTUBE_CHARTS_WEB_{name}.json").write_text(
            json.dumps(snapshot), encoding="utf-8"
        )
    report = report_web_chart_coverage.coverage(tmp_path)
    assert report["verified_weekly_snapshots"] == 1
    assert report["title_observations"] == 2
    assert report["status"] == "PARTIAL"
    (tmp_path / "inventory_manifest.json").write_text(
        json.dumps(
            {"available_markets": ["BR"], "periods": [{"end": "2026-10-15"}, {"end": "2025-01-02"}]}
        ),
        encoding="utf-8",
    )
    report = report_web_chart_coverage.coverage(tmp_path)
    assert report["status"] == "PARTIAL"
    assert report["coverage"][0]["missing_weeks"] == ["2025-01-02"]


@pytest.fixture
def modules(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[3] / "scripts"))
    import import_web_chart_titles
    import scrape_youtube_chart_titles

    return import_web_chart_titles, scrape_youtube_chart_titles


@pytest.fixture
def snapshot():
    return {
        "provider": "YOUTUBE_CHARTS_WEB",
        "country_code": "BR",
        "observed_country_code": "BR",
        "period_start": "2026-10-09",
        "period_end": "2026-10-15",
        "source_url": "https://charts.youtube.com/charts/TopSongs/br/weekly/20261015",
        "rows": [
            {"rank": 1, "title": "Mesmo nome", "artist": "Artista A"},
            {"rank": 2, "title": "Mesmo nome", "artist": "Artista B"},
        ],
    }


def test_same_title_different_artists_keep_distinct_source_identities(modules, snapshot):
    importer, _ = modules
    result = importer.validate_snapshot(snapshot)
    assert result["rows"][0]["native_id"] != result["rows"][1]["native_id"]
    assert importer.validate_snapshot(result) == result


def test_source_tied_ranks_do_not_discard_a_title(modules, snapshot):
    importer, _ = modules
    for row in snapshot["rows"]:
        row["source_rank"] = 1
    result = importer.validate_snapshot(snapshot)
    assert [r["rank"] for r in result["rows"]] == [1, 2]
    assert [r["source_rank"] for r in result["rows"]] == [1, 1]


@pytest.mark.parametrize(
    "field,value",
    [("country_code", "US"), ("observed_country_code", "US"), ("period_end", "2026-10-22")],
)
def test_mismatched_provenance_or_future_period_is_rejected(modules, snapshot, field, value):
    importer, _ = modules
    snapshot[field] = value
    with pytest.raises(ValueError):
        importer.validate_snapshot(snapshot)


def test_a_named_row_cannot_also_be_declared_missing(modules, snapshot):
    importer, _ = modules
    snapshot["missing_title_positions"] = [1]
    with pytest.raises(ValueError, match="missing"):
        importer.validate_snapshot(snapshot)


def test_native_week_can_cross_calendar_year_without_changing_its_end(modules):
    _, scraper = modules
    period = scraper.parse_period("dez. 26, 2025 – jan. 1, 2026")
    assert (period["start"], period["end"]) == ("2025-12-26", "2026-01-01")
