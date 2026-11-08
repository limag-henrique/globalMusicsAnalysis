"""Prevent geographic omissions and documentary leads becoming false chart coverage."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from chart_observatory.sources.global_inventory import build_inventory, geographic_universe

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def geography():
    iso = json.loads(
        (ROOT / "research/geography/iso_3166_20261108.json").read_text(encoding="utf-8")
    )
    un = json.loads((ROOT / "research/geography/un_m49_20261108.json").read_text(encoding="utf-8"))
    return geographic_universe(iso["rows"], un["rows"])


@pytest.fixture
def sources():
    return json.loads(
        (ROOT / "research/global_inventory/source_registry_20261108.json").read_text(
            encoding="utf-8"
        )
    )["sources"]


def test_every_iso_country_and_territory_is_retained_with_explicit_exceptions(geography):
    rows = {r["country_code"]: r for r in geography}
    assert len(rows) == 250
    assert sum(r["code_basis"] == "ISO_3166_1" for r in rows.values()) == 249
    assert rows["TW"]["iso3"] == "TWN"
    assert rows["TW"]["grouping_basis"] == "EXPLICIT_PROJECT_TW_POLICY"
    assert rows["XK"]["iso3"] is None and rows["XK"]["iso_numeric"] is None
    assert rows["XK"]["grouping_basis"] != "UN_M49_PUBLISHED"
    assert rows["AQ"]["geographic_scope"] == "REFERENCE_ONLY"
    assert rows["PS"]["iso3"] == "PSE" and rows["VA"]["iso3"] == "VAT"
    assert rows["CY"]["region"] == "Asia"
    assert rows["MK"]["subregion"] == "Southern Europe"


def test_regional_charts_never_become_country_observations_or_national_sources(geography, sources):
    result = build_inventory(geography, sources, {}, [], years=[2025, 2026])
    rows = {r["country_code"]: r for r in result["countries"]}
    for code in ("DZ", "MA", "TN"):
        assert "IFPI_NORTH_AFRICA" in rows[code]["regional_context_source_ids"]
        assert "IFPI_NORTH_AFRICA" not in rows[code]["national_documented_source_ids"]
        assert rows[code]["research_status"] == "REGIONAL_CONTEXT_ONLY"
    for row in result["country_years"]:
        assert row["local_selected_positions"] == 0
        assert row["observation_status"] == "NO_SELECTION_IN_FROZEN_FRAME"
        assert not row["new_source_ingestion_ready"]


def test_foreign_language_only_and_chinese_repertoire_do_not_prove_whole_country_chart(
    geography, sources
):
    result = build_inventory(geography, sources, {}, [], years=[2026])
    rows = {r["country_code"]: r for r in result["countries"]}
    assert rows["IN"]["restricted_source_ids"] == ["IMI_INTERNATIONAL"]
    assert "IMI_INTERNATIONAL" not in rows["IN"]["national_documented_source_ids"]
    assert "TME_UNI" not in rows["CN"]["national_documented_source_ids"]
    assert rows["CN"]["national_documented_source_ids"] == ["APPLE_DOCUMENTED_COUNTRY_PLAYLISTS"]
    assert rows["KE"]["national_documented_source_ids"] == ["MDUNDO"]
    assert "APPLE_DISCOVERY" in rows["AF"]["unverified_discovery_routes"]
    assert rows["AF"]["research_status"] == "COUNTRY_SOURCE_DISCOVERY_REQUIRED"


def test_missing_data_is_explicit_and_provisional_selection_is_not_promoted(geography, sources):
    result = build_inventory(
        geography,
        sources,
        {"NG": 100},
        [
            dict(
                country_code="NG",
                year=2026,
                platform="SPOTIFY",
                selection_status="PROVISIONAL_OBSERVED_PERIODS",
            )
        ],
        years=[2025, 2026],
    )
    cells = {(r["country_code"], r["year"]): r for r in result["country_years"]}
    assert len(cells) == 500
    assert cells["NG", 2025]["observation_status"] == "NO_SELECTION_IN_FROZEN_FRAME"
    assert cells["NG", 2026]["local_selection_statuses"] == {"PROVISIONAL_OBSERVED_PERIODS": 1}
    assert cells["NG", 2026]["expansion_calendar_status"] == "UNVERIFIED_NO_YEARLY_CALENDAR_AUDIT"
    assert cells["KE", 2026]["current_quota_main"] is None
    assert not cells["NG", 2026]["new_source_ingestion_ready"]


@pytest.mark.parametrize("defect", ["duplicate", "unknown_country", "premature_ready"])
def test_registry_errors_fail_instead_of_fabricating_capability(geography, sources, defect):
    sources = deepcopy(sources)
    if defect == "duplicate":
        sources.append(deepcopy(sources[0]))
    elif defect == "unknown_country":
        sources[0]["countries"].append("ZZ")
    else:
        sources[0]["ingestion_ready"] = True
    with pytest.raises(ValueError):
        build_inventory(geography, sources, {}, [])


def test_playlist_country_label_is_not_its_display_storefront_and_directory_is_bounded():
    payload = json.loads(
        (ROOT / "research/global_inventory/apple_country_chart_directory_20261108.json").read_text(
            encoding="utf-8"
        )
    )
    rows = {r["country_code"]: r for r in payload["rows"]}
    assert len(rows) == 52
    assert rows["NP"]["provider_chart_label"] == "Top 100: Nepal"
    assert "/ba/" in rows["NP"]["playlist_url"]
    assert rows["KZ"]["provider_chart_label"] == "Top 100: Kazakhstan"
    assert "not the complete" in payload["directory_scope"]
    assert "PK" not in rows  # A Pakistan storefront showing Saudi charts proves no Pakistan chart.
