from datetime import date

import polars as pl

from chart_observatory.ingestion.historical_backfill import (
    annual_ranks,
    archive_overlap_agrees,
    integer_metric,
    merge_sources,
    required_dates,
)


def test_archive_omissions_do_not_override_primary_or_hide_conflicting_metrics():
    primary = {"day1": {"one": 10, "two": 20}, "day2": {"one": 11, "two": 21}}
    auxiliary = {"day1": {"one": 10, "two": 20}, "day2": {"one": 11}}
    proof = archive_overlap_agrees(primary, auxiliary)
    assert proof["compatible"] and proof["exact_overlap_days"] == proof["subset_overlap_days"] == 1
    assert primary["day2"]["two"] == 21
    assert not archive_overlap_agrees(primary, {**auxiliary, "day2": {"one": 99}})["compatible"]
    assert not archive_overlap_agrees(primary, {**auxiliary, "day2": {"other": 11}})["compatible"]
    assert not archive_overlap_agrees(primary, {"day2": {"one": 11}})["compatible"]


def test_csv_decimal_integer_counts_are_exact_and_fractional_counts_rejected():
    values = ["7232900.0", "9007199254740993.000", "12", "1.5", "NaN", None]
    assert pl.DataFrame({"views": values}).select(integer_metric("views"))["views"].to_list() == [
        7232900,
        9007199254740993,
        12,
        None,
        None,
        None,
    ]


def test_exact_calendar_duplicate_rows_and_conflicts():
    cutoff = date(2026, 1, 2)
    rows = [
        dict(
            country_code="BR",
            period_end=date(2026, 1, day),
            native_id="track",
            title="Song",
            artist="Artist",
            metric_value=value,
        )
        for day, value in [(1, 10), (2, 20), (2, 20)]
    ]
    kwargs = dict(
        markets={"BR"},
        year=2026,
        cutoff=cutoff,
        frequency="DAILY",
        platform="SPOTIFY",
        provider="TEST",
    )
    ranked, coverage = annual_ranks(pl.DataFrame(rows), **kwargs)
    assert ranked[0]["metric_value"] == 30
    assert coverage[0]["coverage_status"] == "COMPLETE"
    assert coverage[0]["duplicate_observations"] == 1
    rows[-1]["metric_value"] = 99
    ranked, coverage = annual_ranks(pl.DataFrame(rows), **kwargs)
    assert ranked == []
    assert coverage[0]["coverage_status"] == "CONFLICT_OR_INVALID"


def test_missing_week_stays_incomplete_and_does_not_turn_sample_into_census():
    frame = pl.DataFrame(
        [
            dict(
                country_code="BR",
                period_end=date(2026, 1, 1),
                native_id="track",
                title="S",
                artist="A",
                metric_value=10,
            )
        ]
    )
    _, coverage = annual_ranks(
        frame,
        markets={"BR"},
        year=2026,
        cutoff=date(2026, 1, 15),
        frequency="WEEKLY",
        platform="SPOTIFY",
        provider="SAMPLED",
    )
    assert coverage[0]["collected_periods"] == 1
    assert coverage[0]["expected_periods"] == 3
    assert coverage[0]["coverage_status"] == "INCOMPLETE"
    assert required_dates(2026, date(2026, 1, 15), "WEEKLY") == {
        date(2026, 1, 1),
        date(2026, 1, 8),
        date(2026, 1, 15),
    }


def test_complete_source_beats_deeper_incomplete_and_metrics_are_not_added():
    cell = dict(
        country_code="BR",
        year=2025,
        platform="SPOTIFY",
        coverage_status="INCOMPLETE",
        expected_periods=365,
        collected_periods=300,
        minimum_depth=200,
        provider="OLD",
    )
    new = {
        **cell,
        "coverage_status": "COMPLETE",
        "collected_periods": 52,
        "expected_periods": 52,
        "minimum_depth": 100,
        "provider": "NEW",
    }
    row = dict(
        country_code="BR",
        year=2025,
        platform="SPOTIFY",
        provider="OLD",
        position=1,
        metric_value=999,
    )
    selected, coverage = merge_sources(
        [row], [cell], [{**row, "provider": "NEW", "metric_value": 10}], [new]
    )
    assert coverage[0]["provider"] == "NEW"
    assert selected[0]["metric_value"] == 10


def test_valid_incomplete_source_beats_conflicting_calendar_for_provisional_work():
    cell = dict(
        country_code="BR",
        year=2025,
        platform="SPOTIFY",
        coverage_status="INCOMPLETE",
        expected_periods=365,
        collected_periods=300,
        minimum_depth=200,
        provider="VALID",
    )
    bad = {
        **cell,
        "coverage_status": "CONFLICT_OR_INVALID",
        "provider": "BAD",
        "collected_periods": 365,
    }
    row = dict(
        country_code="BR",
        year=2025,
        platform="SPOTIFY",
        provider="VALID",
        position=1,
        metric_value=10,
    )
    selected, coverage = merge_sources(
        [row], [cell], [{**row, "provider": "BAD", "metric_value": 999}], [bad]
    )
    assert selected == [row]
    assert coverage[0]["provider"] == "VALID"


def test_missing_display_metadata_does_not_invalidate_native_stream_ranking():
    rows = [
        dict(
            country_code="BR",
            period_end=date(2026, 1, day),
            native_id="track",
            title=title,
            artist=artist,
            metric_value=streams,
        )
        for day, title, artist, streams in [(1, "", "", 10), (2, "Song", "Artist", 20)]
    ]
    ranked, coverage = annual_ranks(
        pl.DataFrame(rows),
        markets={"BR"},
        year=2026,
        cutoff=date(2026, 1, 2),
        frequency="DAILY",
        platform="SPOTIFY",
        provider="TEST",
    )
    assert coverage[0]["coverage_status"] == "COMPLETE"
    assert coverage[0]["metadata_missing_observations"] == 1
    assert ranked[0]["metric_value"] == 30
    assert ranked[0]["title"] == "Song"
    assert ranked[0]["artist"] == "Artist"
