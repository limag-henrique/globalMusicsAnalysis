from datetime import date, timedelta

import pytest

from chart_observatory.research_rankings import reconstruct_chart_sum


def daily(days=3):
    return [
        dict(
            country_code="BR",
            platform="SPOTIFY",
            provider="TEST",
            period_start=f"2026-01-{day:02d}",
            period_end=f"2026-01-{day:02d}",
            candidate_id=f"SPOTIFY:{candidate}",
            position=position,
            metric_value=str(100 - position * 10),
            title=candidate,
            artist="artist",
        )
        for day in range(1, days + 1)
        for candidate, position in (("a", 1), ("b", 2))
    ]


def reconstruct(rows, **kwargs):
    parameters = dict(
        country_code="BR",
        year=2026,
        platform="SPOTIFY",
        provider="TEST",
        quota=2,
        cutoff="2026-01-03",
        expected_depth=2,
    )
    parameters.update(kwargs)
    return reconstruct_chart_sum(rows, **parameters)


def test_daily_sum_complete_to_partial_cutoff_preserves_semantics():
    result = reconstruct(daily())
    assert result["approved"]
    assert result["partial_year"]
    assert result["rows"][0]["metric_value"] == "270"
    assert result["rows"][1]["metric_value"] == "240"
    assert result["rows"][0]["position"] == 1
    assert not result["source_semantics"]["platform_wide_consumption"]
    assert not result["source_semantics"]["native_published_annual_rank"]


def test_exact_duplicates_are_not_added_twice():
    rows = daily()
    result = reconstruct([*rows, rows[0]])
    assert result["approved"]
    assert result["counts"]["exact_duplicates"] == 1
    assert result["rows"][0]["metric_value"] == "270"


def test_missing_display_name_does_not_invent_calendar_or_depth_gaps():
    rows = daily()
    rows[0]["title"] = ""
    rows[0]["artist"] = None
    result = reconstruct(rows)
    assert result["approved"]
    assert result["counts"]["missing_display_metadata_observations"] == 1
    assert result["counts"]["invalid_observations"] == 0
    assert result["incomplete_depth_period_ends"] == []
    assert result["rows"][0]["metric_value"] == "270"
    assert result["rows"][0]["title"] == "a"
    assert result["metadata_complete"] is False
    assert result["scientific_approval"] is False


def test_fully_missing_names_remain_unknown_without_zeroing_native_metrics():
    rows = daily()
    for row in rows:
        if row["candidate_id"] == "SPOTIFY:a":
            row["title"] = row["artist"] = ""
    result = reconstruct(rows)
    assert result["approved"]
    assert result["rows"][0]["title"] is None
    assert result["rows"][0]["artist"] is None
    assert result["rows"][0]["metric_value"] == "270"


@pytest.mark.parametrize(
    "field,value", [("metric_value", "99"), ("position", 2), ("artist", "different")]
)
def test_candidate_conflicts_are_explicit_and_blocked(field, value):
    rows = daily()
    result = reconstruct([*rows, {**rows[0], field: value}])
    assert not result["approved"]
    assert "conflicting_observations" in result["reasons"]


def test_multiple_candidates_cannot_occupy_one_native_position():
    rows = daily()
    result = reconstruct([*rows, {**rows[0], "candidate_id": "SPOTIFY:other"}])
    assert result["diagnostics"]["position_conflict_within_period"] == 1
    assert not result["approved"]


def test_missing_day_and_shallow_chart_are_different_failures():
    rows = daily()
    result = reconstruct(rows[1:4])
    assert "missing_periods" in result["reasons"]
    assert "incomplete_chart_depth" in result["reasons"]
    assert result["missing_period_ends"] == ["2026-01-03"]


def test_other_provider_platform_market_and_future_window_are_not_summed():
    rows = daily()
    extras = [
        {**rows[0], field: value}
        for field, value in (
            ("provider", "MIRROR"),
            ("platform", "YOUTUBE"),
            ("country_code", "US"),
        )
    ]
    extras.append({**rows[0], "period_start": "2026-01-04", "period_end": "2026-01-04"})
    result = reconstruct([*rows, *extras])
    assert result["approved"]
    assert result["counts"]["ignored_observations"] == 4
    assert result["rows"][0]["metric_value"] == "270"


@pytest.mark.parametrize("value", [True, "NaN", "Infinity", "-1", None, "invalid"])
def test_invalid_metrics_do_not_become_zero(value):
    rows = daily()
    rows[0]["metric_value"] = value
    result = reconstruct(rows)
    assert not result["approved"]
    assert result["counts"]["invalid_observations"] == 1


def test_decimal_sums_do_not_round_through_floats():
    rows = daily()
    for row in rows:
        row["metric_value"] = "0.1" if row["position"] == 1 else "0.01"
    result = reconstruct(rows)
    assert result["rows"][0]["metric_value"] == "0.3"


def test_boundary_tie_does_not_assign_arbitrary_rank_or_selection():
    rows = daily()
    for row in rows:
        row["metric_value"] = "100"
    result = reconstruct(rows, quota=1)
    assert not result["approved"]
    assert "unresolved_quota_boundary_tie" in result["reasons"]
    assert all(row["position"] is None and row["selected"] is None for row in result["rows"])
    assert result["rows"][0]["tie_group"] == ["SPOTIFY:a", "SPOTIFY:b"]


def test_internal_tie_is_shared_rank_and_not_arbitrary_distinct_positions():
    rows = daily()
    for row in rows:
        row["metric_value"] = "100"
    result = reconstruct(rows)
    assert result["approved"]
    assert [row["position"] for row in result["rows"]] == [1, 1]
    assert all(row["selected"] for row in result["rows"])


def weekly():
    ends = [date(2026, 1, 2) + timedelta(days=7 * week) for week in range(2)]
    rows = [
        dict(
            country_code="BR",
            platform="YOUTUBE",
            provider="TEST",
            period_start=(end - timedelta(days=6)).isoformat(),
            period_end=end.isoformat(),
            candidate_id="YOUTUBE:opaque",
            position=1,
            metric_value=123,
            title="track",
            artist="artist",
        )
        for end in ends
    ]
    return rows, [value.isoformat() for value in ends]


def test_weekly_requires_explicit_schedule_and_assigns_by_end_year():
    rows, ends = weekly()
    result = reconstruct(
        rows,
        platform="YOUTUBE",
        frequency="weekly",
        expected_depth=1,
        quota=1,
        cutoff="2026-01-14",
        expected_period_ends=ends,
    )
    assert result["approved"]
    assert result["rows"][0]["metric_value"] == "246"
    assert rows[0]["period_start"].startswith("2025")
    missing = reconstruct(
        rows, platform="YOUTUBE", frequency="weekly", expected_depth=1, quota=1, cutoff="2026-01-14"
    )
    assert not missing["approved"]
    assert "weekly_expected_period_ends_required" in missing["reasons"]


def test_weekly_schedule_cannot_claim_completeness_from_a_short_subset():
    rows, ends = weekly()
    result = reconstruct(
        rows,
        platform="YOUTUBE",
        frequency="weekly",
        expected_depth=1,
        quota=1,
        cutoff="2026-02-14",
        expected_period_ends=ends,
    )
    assert "weekly_schedule_does_not_cover_window" in result["reasons"]
    assert not result["approved"]


def test_annual_union_can_exceed_daily_depth_and_requires_full_quota():
    rows = daily()
    rows[-1] = {**rows[-1], "candidate_id": "SPOTIFY:c", "title": "c"}
    result = reconstruct(rows, quota=3)
    assert result["approved"]
    assert len(result["rows"]) == 3
    assert not reconstruct(rows, quota=4)["approved"]


def test_prior_year_requires_full_calendar_including_leap_day():
    rows = daily()
    result = reconstruct(rows, year=2024)
    assert result["counts"]["expected_periods"] == 366
    assert "2024-02-29" in result["missing_period_ends"]
    assert not result["partial_year"]
