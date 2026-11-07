import pytest

from chart_observatory.ingestion.import_quotas import select_quota_candidates
from chart_observatory.ingestion.quota_boundary import (
    validate_quota_memberships,
    validate_ranking_positions,
)


def israel_rows(count):
    return [
        dict(country_code="IL", year=2024, position=i, quota_main=120, candidate_id=f"SPOTIFY:{i}")
        for i in range(1, count + 1)
    ]


def test_israel_annual_limit_is_120():
    assert validate_quota_memberships(israel_rows(120), {"IL": 120})[0]["selected_positions"] == 120
    with pytest.raises(ValueError, match="exceeds"):
        validate_quota_memberships(israel_rows(121), {"IL": 120})


def test_3700_weekly_occurrences_cannot_be_annual_memberships():
    with pytest.raises(ValueError):
        validate_quota_memberships(israel_rows(3700), {"IL": 120})


@pytest.mark.parametrize(
    "change",
    [dict(year=2017), dict(quota_main=3700), dict(selection_status="DISCOVERY_QUARANTINE")],
)
def test_wrong_scope_or_reference_input_rejected(change):
    row = dict(israel_rows(1)[0], **change)
    with pytest.raises(ValueError):
        validate_quota_memberships([row], {"IL": 120})


def test_no_replacement_or_duplicate_positions():
    rows = israel_rows(2)
    rows[1]["position"] = 1
    with pytest.raises(ValueError, match="duplicate"):
        validate_quota_memberships(rows, {"IL": 120})


def test_new_selection_defaults_to_2018_and_rejects_2017():
    result = select_quota_candidates([], [], {"IL": 120})
    assert [cell["year"] for cell in result["coverage"]] == list(range(2018, 2027))
    with pytest.raises(ValueError, match="2018"):
        select_quota_candidates([], [], {"IL": 120}, years=[2017])


@pytest.mark.parametrize(
    "change",
    [
        dict(country_code="US"),
        dict(year=2023),
        dict(position=2),
        dict(candidate_id="SPOTIFY:other"),
    ],
)
def test_exact_country_year_position_and_native_id_required(change):
    source = dict(israel_rows(1)[0], platform="SPOTIFY")
    with pytest.raises(ValueError, match="differs"):
        validate_ranking_positions([dict(source, **change)], [source])
