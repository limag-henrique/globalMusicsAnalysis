"""Recover deeper positions only from an exact matching annual-source prefix."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import polars as pl

from chart_observatory.final_pipeline import digest, encode, save
from chart_observatory.research_flow import load_selection

ROOT = Path(__file__).resolve().parents[1]
KEYS = ["country_code", "year", "platform", "provider"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest, cells, rows, _ = load_selection(args.selection)
    out = args.output.resolve()
    if not out.is_relative_to(ROOT / "data/derived/annual_revision"):
        raise ValueError("selection must remain in annual_revision")
    out.mkdir(parents=True, exist_ok=False)
    originals = defaultdict(list)
    for row in rows:
        originals[tuple(row[k] for k in KEYS)].append(row)
    pool_paths = [
        ROOT
        / "data/derived/annual_revision/global-rescan-2018-2026-20261111-v4-final-0002/new_market_rankings.parquet",
        ROOT
        / "data/derived/annual_revision/reconciled-russia-2018-2026-20261031/sources/rankings.parquet",
        ROOT
        / "data/derived/annual_revision/global-rescan-2018-2026-20261111/new_market_rankings.parquet",
        ROOT
        / "data/derived/annual_revision/global-2018-2026-20261108/new_market_rankings.parquet",
    ]
    used, additions, source_hashes = set(), [], {}
    for path in pool_paths:
        table = pl.read_parquet(path).filter(pl.col("position") <= 500)
        groups = defaultdict(list)
        for record in table.iter_rows(named=True):
            key = tuple(record[k] for k in KEYS)
            if key in originals and key not in used:
                groups[key].append(record)
        for key, candidates in groups.items():
            old = sorted(originals[key], key=lambda r: r["position"])
            quota = old[0]["quota_main"]
            by_rank = {r["position"]: r for r in candidates}
            if len(by_rank) != len(candidates):
                continue
            if any(
                r["position"] not in by_rank
                or by_rank[r["position"]]["candidate_id"] != r["candidate_id"]
                or by_rank[r["position"]].get("metric_value") != r.get("metric_value")
                for r in old
            ):
                continue
            last = old[-1]["position"]
            extra = []
            for rank in range(last + 1, quota + 1):
                if rank not in by_rank:
                    break
                extra.append(
                    dict(
                        old[-1],
                        **by_rank[rank],
                        quota_main=quota,
                        archive_extension_source=str(path.relative_to(ROOT)),
                        archive_prefix_identity_and_metric_verified=True,
                    )
                )
            if extra:
                used.add(key)
                additions.extend(extra)
                source_hashes[str(path.relative_to(ROOT))] = digest(path.read_bytes())
    combined = sorted(rows + additions, key=lambda r: (r["country_code"], r["year"], r["position"]))
    by_cell = defaultdict(list)
    for row in combined:
        by_cell[row["country_code"], row["year"]].append(row)
    updated_cells = []
    for cell in cells:
        members = by_cell[cell["country_code"], cell["year"]]
        quota = cell["quota"] or 0
        missing = sorted(set(range(1, quota + 1)) - {r["position"] for r in members})
        complete = (
            sum(r.get("selection_status") == "CALENDAR_ELIGIBLE" for r in members)
            if cell["year"] < 2026
            else 0
        )
        updated_cells.append(
            dict(
                cell,
                selected_positions=len(members),
                missing_positions=len(missing),
                missing_position_numbers=missing,
                provisional_positions=sum(
                    str(r.get("selection_status", "")).startswith("PROVISIONAL_") for r in members
                ),
                complete_calendar_year_positions=complete,
                missing_complete_annual_positions=max(0, quota - complete),
                selection_statuses=dict(Counter(r.get("selection_status") for r in members)),
            )
        )
    for name, records in [("combined.jsonl", combined), ("country_years.jsonl", updated_cells)]:
        with (out / name).open("x", encoding="utf-8") as handle:
            for row in records:
                handle.write(encode(row) + "\n")
    for name in ["allocation.jsonl", "allocation.csv"]:
        (out / name).write_bytes((args.selection / name).read_bytes())
    summary = json.loads((args.selection / "allocation-summary.json").read_text())
    summary.update(
        observed_positions=len(combined),
        unique_known_songs=len({r["candidate_id"] for r in combined}),
        missing_positions=150000 - len(combined),
        archive_added_positions=len(additions),
    )
    save(out / "allocation-summary.json", summary)
    save(
        out / "archive-extension.json",
        dict(
            added_positions=len(additions),
            source_hashes=source_hashes,
            prefix_check="all pre-existing native IDs and metric values exactly equal",
            scientific_approval=False,
        ),
    )
    manifest.update(
        selection_revision=out.name,
        parent_selection=str(args.selection.resolve()),
        parent_manifest_sha256=digest((args.selection / "manifest.json").read_bytes()),
        memberships=len(combined),
        unique_candidates=summary["unique_known_songs"],
        candidate_identities=summary["unique_known_songs"],
        missing_positions=summary["missing_positions"],
        remaining_missing_ranking_positions=summary["missing_positions"],
        missing_complete_annual_positions=sum(
            c["missing_complete_annual_positions"] for c in updated_cells
        ),
        archive_added_positions=len(additions),
        archive_source_hashes=source_hashes,
        output_hashes={p.name: digest(p.read_bytes()) for p in out.iterdir() if p.is_file()},
    )
    save(out / "manifest.json", manifest)
    load_selection(out)
    print(encode(summary))


if __name__ == "__main__":
    main()
