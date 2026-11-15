import copy

import pytest

from chart_observatory.ingestion.published_annual_overlay import (
    STATUS,
    inspect_cell_semantics,
    validate_published_delta,
)


@pytest.fixture
def publication():
    rows = [
        dict(
            country_code="SI",
            year=2018,
            platform="NATIONAL_PUBLIC_PERFORMANCE",
            provider="IPF",
            candidate_id=f"IPF:2018:{p}",
            source_native_id=str(p),
            position=p,
            title=f"Song {p}",
            artist="Artist",
            metric_value=None,
            period_start="2018-01-01",
            period_end="2018-12-31",
            ranking_kind="published_annual",
            scientifically_verified=False,
        )
        for p in range(1, 4)
    ]
    return dict(
        cells=[dict(country_code="SI", year=2018, quota=2)],
        memberships=[],
        observations=rows,
        selected=copy.deepcopy(rows[:2]),
        declared_checks=[
            dict(
                country_code="SI",
                year=2018,
                platform="NATIONAL_PUBLIC_PERFORMANCE",
                provider="IPF",
                expected_depth=3,
                period_start="2018-01-01",
                ranking_period_end="2018-12-31",
            )
        ],
    )


def test_native_rows_remain_provisional_and_have_no_synthetic_metrics(publication):
    accepted, checks = validate_published_delta(**publication)
    assert len(accepted) == 2
    assert all(r["selection_status"] == STATUS and r["metric_value"] is None for r in accepted)
    assert all(r["not_for_paid_submission"] and not r["classification_ready"] for r in accepted)
    assert checks[0]["approved"] and not checks[0]["scientific_approval"]


def test_existing_cell_rejected_even_when_slots_differ(publication):
    publication["memberships"] = [dict(country_code="SI", year=2018, position=3)]
    with pytest.raises(ValueError, match="collides"):
        validate_published_delta(**publication)


def test_underquota_does_not_fill_missing_slots_from_other_source(publication):
    publication["selected"].pop()
    with pytest.raises(ValueError, match="entire contiguous quota"):
        validate_published_delta(**publication)


def test_missing_native_publication_row_rejected(publication):
    publication["observations"].pop()
    with pytest.raises(ValueError, match="native list invalid"):
        validate_published_delta(**publication)


@pytest.mark.parametrize("metric", [0, 3, "100", 1.5])
def test_rank_cannot_be_converted_to_streams(publication, metric):
    publication["observations"][0]["metric_value"] = metric
    with pytest.raises(ValueError, match="stream/view metric"):
        validate_published_delta(**publication)


def test_selected_identity_must_equal_whole_publication(publication):
    publication["selected"][0]["candidate_id"] = "wrong"
    with pytest.raises(ValueError, match="differs from preserved"):
        validate_published_delta(**publication)


def test_row_period_cannot_differ_from_documented_scope(publication):
    publication["observations"][0]["period_start"] = "2018-02-01"
    with pytest.raises(ValueError, match="native list invalid"):
        validate_published_delta(**publication)


def test_duplicate_native_position_rejected(publication):
    publication["observations"][1]["position"] = 1
    with pytest.raises(ValueError, match="native list invalid"):
        validate_published_delta(**publication)


def test_paid_or_scientific_approval_cannot_be_inherited(publication):
    publication["observations"][0]["scientifically_verified"] = True
    with pytest.raises(ValueError, match="cannot carry"):
        validate_published_delta(**publication)


def test_provisional_native_annual_rows_are_not_complete_calendar_positions():
    rows = [dict(country_code="SI", year=2018, selection_status=STATUS)] * 2
    cells = [
        dict(
            country_code="SI",
            year=2018,
            quota=2,
            selected_positions=2,
            provisional_positions=2,
            complete_calendar_year_positions=0,
            missing_positions=0,
            missing_complete_annual_positions=2,
        )
    ]
    assert inspect_cell_semantics(cells, rows)[0]["passed"]
    cells[0]["complete_calendar_year_positions"] = 2
    with pytest.raises(ValueError, match="counters differ"):
        inspect_cell_semantics(cells, rows)
