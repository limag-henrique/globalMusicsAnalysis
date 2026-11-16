"""Freeze a revised, population-weighted selection with <=150k total positions."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from chart_observatory.final_pipeline import digest, encode, save
from chart_observatory.population_allocation import TOTAL_POSITIONS, allocate, weight
from chart_observatory.research_flow import load_selection

ROOT = Path(__file__).resolve().parents[1]


def write_rows(path, rows):
    with path.open("x", encoding="utf-8") as handle:
        for row in rows:
            handle.write(encode(row) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    old, cells, members, hashes = load_selection(args.selection)
    out = args.output.resolve()
    if not out.is_relative_to(ROOT / "data/derived/annual_revision"):
        raise ValueError("selection must remain inside annual_revision")
    out.mkdir(parents=True, exist_ok=False)
    evidence_path = ROOT / "research/global_inventory/expansion_20261108/population_evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    population = {r["country_code"]: r for r in evidence["rows"]}
    platforms = defaultdict(set)
    by_cell = defaultdict(list)
    for row in members:
        by_cell[row["country_code"], row["year"]].append(row)
        platforms[row["country_code"]].add(row["platform"])
    years = sorted({c["year"] for c in cells})
    countries = sorted({c["country_code"] for c in cells})
    valid = {
        c: population[c]
        for c in countries
        if c in population
        and isinstance(population[c].get("population"), (int, float))
        and population[c]["population"] > 0
    }
    quotas, details = {}, []
    for offset, year in enumerate(years):
        year_cells = {c["country_code"]: c for c in cells if c["year"] == year}
        budget = TOTAL_POSITIONS // len(years) + (offset < TOTAL_POSITIONS % len(years))
        inputs = {}
        for country in valid:
            old_quota = year_cells[country].get("quota") or 0
            available = len(by_cell[country, year])
            need = 1 - min(1, available / old_quota) if old_quota else 1
            relevance = min(1, len(platforms[country]) / 2)
            inputs[country] = (
                weight(valid[country]["population"], relevance, need),
                relevance,
                need,
            )
        assigned = allocate({k: v[0] for k, v in inputs.items()}, budget)
        for country in countries:
            quota = assigned.get(country)
            quotas[country, year] = quota
            item = dict(
                country_code=country,
                year=year,
                quota=quota,
                previous_quota=year_cells[country].get("quota"),
                population=valid.get(country, {}).get("population"),
                population_reference_year=valid.get(country, {}).get("population_year"),
                population_source=valid.get(country, {}).get("population_source"),
                allocation_population_is_fixed_reference=True,
                relevance=inputs[country][1] if country in inputs else None,
                need=inputs[country][2] if country in inputs else None,
                status="ALLOCATED" if quota else "POPULATION_UNRESOLVED_OR_UNINHABITED",
            )
            details.append(item)
    selected = []
    new_cells = []
    for cell in cells:
        key = cell["country_code"], cell["year"]
        quota = quotas[key]
        rows = [dict(r, quota_main=quota) for r in by_cell[key] if quota and r["position"] <= quota]
        selected.extend(rows)
        missing = sorted(set(range(1, (quota or 0) + 1)) - {r["position"] for r in rows})
        provisional = sum(
            str(r.get("selection_status", "")).startswith("PROVISIONAL_") for r in rows
        )
        complete = (
            sum(r.get("selection_status") == "CALENDAR_ELIGIBLE" for r in rows)
            if cell["year"] < 2026
            else 0
        )
        new_cells.append(
            dict(
                cell,
                quota=quota,
                selected_positions=len(rows),
                provisional_positions=provisional,
                complete_calendar_year_positions=complete,
                missing_complete_annual_positions=max(0, (quota or 0) - complete),
                platforms=sorted({r["platform"] for r in rows}),
                selection_statuses=dict(
                    Counter(r.get("selection_status", "UNKNOWN") for r in rows)
                ),
                missing_positions=len(missing),
                missing_position_numbers=missing,
                classification_ready=False,
            )
        )
    write_rows(out / "combined.jsonl", selected)
    write_rows(out / "country_years.jsonl", new_cells)
    write_rows(out / "allocation.jsonl", details)
    with (out / "allocation.csv").open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(details[0]))
        writer.writeheader()
        writer.writerows(details)
    output_hashes = {p.name: digest(p.read_bytes()) for p in out.iterdir() if p.is_file()}
    manifest = dict(
        protocol=old["protocol"],
        selection_revision=out.name,
        years=old["years"],
        cutoff=old["cutoff"],
        scientifically_verified=False,
        classification_ready=False,
        lyrics_acquisition_ready=False,
        current_snapshots_used_as_annual=False,
        policy_id="population-total-150k-v1",
        parent_selection=str(args.selection.resolve()),
        parent_input_hashes=hashes,
        output_hashes=output_hashes,
        requested_positions=sum(q or 0 for q in quotas.values()),
        memberships=len(selected),
        unique_candidates=len({r["candidate_id"] for r in selected}),
        candidate_identities=len({r["candidate_id"] for r in selected}),
        countries_with_memberships=len({r["country_code"] for r in selected}),
        cells_with_memberships=len({(r["country_code"], r["year"]) for r in selected}),
        missing_positions=sum(c["missing_positions"] for c in new_cells),
        missing_complete_annual_positions=sum(
            c["missing_complete_annual_positions"] for c in new_cells
        ),
        candidate_limit_exceeded=False,
        hard_maximum_total_positions=TOTAL_POSITIONS,
        hard_maximum_classified_songs=TOTAL_POSITIONS,
        budget_is_shared_across_all_countries_years_platforms=True,
        countries=len(countries),
        country_year_cells=len(cells),
        population_evidence_sha256=digest(evidence_path.read_bytes()),
        allocation_formula="sqrt(population_2024)*(1+0.10*source_platform_relevance+0.10*ranking_gap_need)",
        min_per_populated_country_year=1,
        max_per_country_year=500,
        scientific_approval=False,
        annual_rankings_reconstructed=False,
        remaining_missing_ranking_positions=sum(c["missing_positions"] for c in new_cells),
    )
    save(out / "manifest.json", manifest)
    load_selection(out)
    totals = Counter()
    for detail in details:
        totals[detail["country_code"]] += detail["quota"] or 0
    save(
        out / "allocation-summary.json",
        dict(
            total_positions=manifest["requested_positions"],
            observed_positions=len(selected),
            unique_known_songs=manifest["unique_candidates"],
            years=years,
            country_totals=totals,
            missing_positions=manifest["remaining_missing_ranking_positions"],
            unresolved_countries=sorted(set(countries) - set(valid)),
            priority_countries=sorted(
                totals, key=lambda c: (-totals[c], -valid.get(c, {}).get("population", 0), c)
            ),
        ),
    )
    print(
        encode(
            dict(
                output=str(out),
                total_positions=manifest["requested_positions"],
                observed_positions=len(selected),
                unique_known_songs=manifest["unique_candidates"],
                country_totals=dict(totals.most_common(15)),
            )
        )
    )


if __name__ == "__main__":
    main()
