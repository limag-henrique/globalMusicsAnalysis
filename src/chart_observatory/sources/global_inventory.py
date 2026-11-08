"""Research inventory distinct from observed chart coverage and ingestion eligibility."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from typing import Any

NATIONAL_SCOPES = frozenset({"NATIONAL", "NATIONAL_PLATFORM_LABEL"})
SCOPES = NATIONAL_SCOPES | {
    "REGIONAL",
    "REPERTOIRE_RESTRICTED",
    "COUNTRY_LEAD",
    "GLOBAL_DISCOVERY_ONLY",
}


def geographic_universe(
    iso_rows: list[dict[str, Any]], un_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Preserve every ISO entry, official UN grouping and explicit project exception."""
    iso = {row["alpha_2"]: row for row in iso_rows}
    un = {row["ISO-alpha2 Code"]: row for row in un_rows}
    if len(iso) != len(iso_rows) or len(un) != len(un_rows):
        raise ValueError("duplicate geographic code")
    if set(un) - set(iso) or set(iso) - set(un) != {"TW"}:
        raise ValueError("geographic references changed; review exceptions explicitly")
    result = []
    for code, entry in sorted(iso.items()):
        grouping = un.get(code)
        if grouping:
            if (entry["alpha_3"], entry["numeric"]) != (
                grouping["ISO-alpha3 Code"],
                grouping["M49 Code"],
            ):
                raise ValueError("ISO and M49 identifier mismatch")
            region = grouping["Region Name"] or "UN_REGION_UNASSIGNED"
            subregion = grouping["Sub-region Name"]
            intermediate = grouping["Intermediate Region Name"]
        else:
            # Taiwan is ISO-assigned but absent from the published UN table.
            # Never attribute the following project assignment to the UN.
            region, subregion, intermediate = "Asia", "Eastern Asia", ""
        result.append(
            dict(
                country_code=code,
                iso3=entry["alpha_3"],
                iso_numeric=entry["numeric"],
                country_name=entry["name"],
                region=region,
                subregion=subregion,
                intermediate_region=intermediate,
                code_basis="ISO_3166_1",
                grouping_basis="UN_M49_PUBLISHED" if grouping else "EXPLICIT_PROJECT_TW_POLICY",
                geographic_scope="REFERENCE_ONLY" if code == "AQ" else "RESEARCH_CANDIDATE",
            )
        )
    result.append(
        dict(
            country_code="XK",
            iso3=None,
            iso_numeric=None,
            country_name="Kosovo (project exception)",
            region="Europe",
            subregion="Southern Europe",
            intermediate_region="",
            code_basis="PROJECT_EXCEPTION_NOT_ISO_3166_1",
            grouping_basis="EXPLICIT_PROJECT_XK_POLICY",
            geographic_scope="RESEARCH_CANDIDATE",
        )
    )
    return sorted(result, key=lambda row: row["country_code"])


def build_inventory(
    geography: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    quotas: dict[str, int],
    selections: Iterable[dict[str, Any]],
    years: Iterable[int] = range(2018, 2027),
) -> dict[str, Any]:
    """Expose missing observations without inventing coverage, quotas or national charts."""
    countries = {row["country_code"] for row in geography}
    if len(countries) != len(geography):
        raise ValueError("duplicate inventory country")
    if set(quotas) - countries:
        raise ValueError("quota country outside geographic inventory")
    identifiers = [source["source_id"] for source in sources]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("duplicate source identifier")
    for source in sources:
        if source["scope"] not in SCOPES or set(source["countries"]) - countries:
            raise ValueError("invalid source scope or geographic binding")
        if source["ingestion_ready"] is not False:
            raise ValueError("documentary inventory cannot certify ingestion readiness")
    observed = defaultdict(list)
    for row in selections:
        if row["country_code"] not in countries:
            raise ValueError("observed market outside inventory")
        observed[row["country_code"], row["year"]].append(row)
    years = tuple(years)
    if len(years) != len(set(years)):
        raise ValueError("duplicate inventory year")
    global_routes = sorted(s["source_id"] for s in sources if s["scope"] == "GLOBAL_DISCOVERY_ONLY")
    country_rows, cells = [], []
    for geo in geography:
        code = geo["country_code"]
        bound = [source for source in sources if code in source["countries"]]
        national = sorted(s["source_id"] for s in bound if s["scope"] in NATIONAL_SCOPES)
        restricted = sorted(s["source_id"] for s in bound if s["scope"] == "REPERTOIRE_RESTRICTED")
        regional = sorted(s["source_id"] for s in bound if s["scope"] == "REGIONAL")
        leads = sorted(s["source_id"] for s in bound if s["scope"] == "COUNTRY_LEAD")
        selected_years = [year for year in years if observed.get((code, year))]
        memberships = sum(len(observed.get((code, year), [])) for year in years)
        status = (
            "REFERENCE_ONLY"
            if geo["geographic_scope"] == "REFERENCE_ONLY"
            else "EXISTING_SELECTION_RETAIN_GAPS"
            if selected_years
            else "DOCUMENTED_NATIONAL_CANDIDATE_UNVALIDATED"
            if national
            else "RESTRICTED_REPERTOIRE_ONLY"
            if restricted
            else "REGIONAL_CONTEXT_ONLY"
            if regional
            else "COUNTRY_SOURCE_DISCOVERY_REQUIRED"
        )
        country_rows.append(
            dict(
                **geo,
                in_current_quota_frame=code in quotas,
                current_quota_main=quotas.get(code),
                baseline_selected_years=selected_years,
                baseline_memberships=memberships,
                national_documented_source_ids=national,
                restricted_source_ids=restricted,
                regional_context_source_ids=regional,
                country_lead_source_ids=leads,
                unverified_discovery_routes=global_routes,
                research_status=status,
                new_source_ingestion_ready=False,
                next_action="AUDIT_COUNTRY_CHART_METRIC_CALENDAR_DEPTH_IDENTITY_ACCESS_BEFORE_SELECTION",
            )
        )
        for year in years:
            rows = observed.get((code, year), [])
            cells.append(
                dict(
                    country_code=code,
                    year=year,
                    current_quota_main=quotas.get(code),
                    local_selected_positions=len(rows),
                    local_selection_statuses=dict(Counter(r["selection_status"] for r in rows)),
                    local_platforms=sorted({r["platform"] for r in rows}),
                    observation_status="LOCAL_FROZEN_SELECTION_PRESENT"
                    if rows
                    else "NO_SELECTION_IN_FROZEN_FRAME",
                    candidate_source_ids=national,
                    restricted_source_ids=restricted,
                    regional_context_source_ids=regional,
                    expansion_calendar_status="UNVERIFIED_NO_YEARLY_CALENDAR_AUDIT",
                    new_source_ingestion_ready=False,
                )
            )
    summary = dict(
        total_geographic_entries=len(country_rows),
        iso_entries=sum(r["code_basis"] == "ISO_3166_1" for r in country_rows),
        explicit_non_iso_exceptions=sum(r["code_basis"] != "ISO_3166_1" for r in country_rows),
        country_year_cells=len(cells),
        source_records=len(sources),
        baseline_quota_markets=len(quotas),
        baseline_selected_markets=sum(bool(r["baseline_selected_years"]) for r in country_rows),
        baseline_memberships=sum(r["baseline_memberships"] for r in country_rows),
        documented_national_candidate_markets=sum(
            bool(r["national_documented_source_ids"]) for r in country_rows
        ),
        documented_national_candidates_outside_quota_frame=[
            r["country_code"]
            for r in country_rows
            if r["national_documented_source_ids"] and not r["in_current_quota_frame"]
        ],
        regions={},
        new_rankings_imported=0,
        paid_calls=0,
    )
    for region in sorted({r["region"] for r in country_rows}):
        rows = [r for r in country_rows if r["region"] == region]
        summary["regions"][region] = dict(
            inventory_entries=len(rows),
            baseline_quota_markets=sum(r["in_current_quota_frame"] for r in rows),
            baseline_selected_markets=sum(bool(r["baseline_selected_years"]) for r in rows),
            national_documentary_candidates=sum(
                bool(r["national_documented_source_ids"]) for r in rows
            ),
        )
    return dict(countries=country_rows, country_years=cells, summary=summary)
