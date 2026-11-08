import copy

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError

from chart_observatory.ingestion.global_annual import (
    assemble,
    cells_table,
    countries_table,
    memberships_table,
    persist,
    runs,
)


def country(code, legacy=False, quota=100):
    return dict(country_code=code, legacy_frozen=legacy, quota_per_year_main=quota)


def ranked(code="NG", year=2025, count=100):
    return [
        dict(
            country_code=code,
            year=year,
            position=i,
            candidate_id=f"SPOTIFY:track{i}",
            title=f"Song {i}",
            artist="Artist",
            platform="SPOTIFY",
            provider="TEST",
            metric_value=1000 - i,
        )
        for i in range(1, count + 1)
    ]


def coverage(year=2025, status="COMPLETE", periods=365):
    return [
        dict(
            country_code="NG",
            year=year,
            platform="SPOTIFY",
            provider="TEST",
            coverage_status=status,
            expected_periods=365,
            collected_periods=periods,
            ranking_period_end=f"{year}-12-31",
            minimum_depth=100,
        )
    ]


def test_each_country_has_every_year_without_fake_missing_memberships():
    result = assemble(
        [country("NG"), country("TD"), country("AQ", quota=None)], [], ranked(), coverage()
    )
    assert len(result["cells"]) == 27
    assert len(result["memberships"]) == 100
    assert result["new_definitive_memberships"] == 100
    empty = next(c for c in result["cells"] if c["country_code"] == "TD" and c["year"] == 2025)
    assert empty["missing_position_numbers"] == list(range(1, 101))
    assert empty["status"] == "NO_VERIFIED_ANNUAL_SOURCE"
    assert all(c["quota"] is None for c in result["cells"] if c["country_code"] == "AQ")


def test_existing_data_preserved_without_replacement_or_mutation():
    baseline = ranked("BR", count=90)
    original = copy.deepcopy(baseline)
    result = assemble([country("BR", True), country("NG")], baseline, ranked(), coverage())
    assert baseline == original
    assert [r for r in result["memberships"] if r["country_code"] == "BR"] == original
    with pytest.raises(ValueError, match="replace a frozen"):
        assemble([country("BR", True)], baseline, ranked("BR"), [])


def test_incomplete_and_partial_years_are_never_complete_annual_evidence():
    result = assemble([country("NG")], [], ranked(), coverage(status="INCOMPLETE", periods=300))
    assert result["new_provisional_memberships"] == 100
    cell = next(c for c in result["cells"] if c["year"] == 2025)
    assert cell["complete_calendar_year_positions"] == 0
    assert cell["missing_complete_annual_positions"] == 100
    partial = assemble([country("NG")], [], ranked(year=2026), coverage(year=2026))
    assert next(c for c in partial["cells"] if c["year"] == 2026)["status"] == "PARTIAL_YEAR"
    assert all(not c["classification_ready"] for c in partial["cells"])
    assert all(r["not_for_paid_submission"] for r in partial["memberships"])


def test_snapshot_rejected_at_annual_import_boundary():
    baseline = ranked("BR", count=1)
    baseline[0]["period_scope"] = "CURRENT_DAILY_SNAPSHOT"
    with pytest.raises(ValueError, match="current snapshot"):
        assemble([country("BR", True)], baseline, [], [])


def test_separate_import_is_atomic_idempotent_and_keeps_all_country_years():
    engine = create_engine("sqlite://")
    result = assemble([country("NG"), country("TD")], [], ranked(), coverage())
    first = persist(engine, dict(protocol="test"), result)
    assert first["inserted"]
    assert not persist(engine, dict(protocol="test"), result)["inserted"]
    broken = copy.deepcopy(result)
    broken["memberships"].append(broken["memberships"][0])
    with pytest.raises(IntegrityError):
        persist(engine, dict(protocol="broken"), broken)
    with engine.connect() as conn:
        for table, expected in [
            (runs, 1),
            (countries_table, 2),
            (cells_table, 18),
            (memberships_table, 100),
        ]:
            assert conn.execute(select(func.count()).select_from(table)).scalar_one() == expected
    engine.dispose()
