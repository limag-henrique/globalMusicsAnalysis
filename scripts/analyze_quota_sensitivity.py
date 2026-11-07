"""Offline quota scenarios on the same frozen source/cell frame; never replaces selection."""

import csv
import hashlib
import json
import math
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/derived/annual_revision/reconciled-russia-2018-2026-20261031"
OUT = ROOT / "data/runtime/remediation-20261106/quota-sensitivity"


def allocation(rows, alpha, diversity, budget=9980):
    if budget < 100 * len(rows):
        raise ValueError("budget cannot support the predefined country floors")
    weights = {
        r["country_code"]: (float(r["population_2024"]) / 1e6) ** alpha
        * (1 + diversity * float(r["historical_ethnic_diversity"]))
        for r in rows
    }

    def quotas(scale):
        return {
            key: min(500, 100 + 10 * math.floor(scale * weight / 10))
            for key, weight in weights.items()
        }

    lower, upper = 0, 100000.0
    for _ in range(80):
        middle = (lower + upper) / 2
        if sum(quotas(middle).values()) <= budget:
            lower = middle
        else:
            upper = middle
    return quotas(lower)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    selection_raw = (BASE / "combined.jsonl").read_bytes()
    selected = [json.loads(x) for x in selection_raw.decode().splitlines() if x]
    with (BASE / "sources/country_quotas.csv").open(encoding="utf-8-sig") as file:
        countries = list(csv.DictReader(file))
    main_quotas = {r["country_code"]: int(r["quota_per_year_main"]) for r in countries}
    frame = {(r["country_code"], r["year"], r["platform"]) for r in selected}
    ranking = pl.read_parquet(BASE / "sources/rankings.parquet").to_dicts()
    ranking = [r for r in ranking if (r["country_code"], r["year"], r["platform"]) in frame]

    def choose(quotas):
        return [r for r in ranking if r["position"] <= quotas[r["country_code"]]]

    baseline_rows = choose(main_quotas)

    def signature(r):
        return tuple(r[k] for k in ("country_code", "year", "platform", "position", "candidate_id"))

    assert {signature(r) for r in baseline_rows} == {signature(r) for r in selected}
    baseline_ids = {r["candidate_id"] for r in selected}
    results = []
    for alpha in (0, 0.25, 0.5, 0.75, 1):
        for diversity in (0, 0.5):
            quotas = allocation(countries, alpha, diversity)
            chosen = choose(quotas)
            ids = {r["candidate_id"] for r in chosen}
            assert all(100 <= q <= 500 and q % 10 == 0 for q in quotas.values())
            assert sum(quotas.values()) <= 9980
            top5 = sum(sorted(quotas.values(), reverse=True)[:5]) / sum(quotas.values())
            results.append(
                dict(
                    alpha=alpha,
                    diversity_weight=diversity,
                    quota_sum=sum(quotas.values()),
                    target_slack=9980 - sum(quotas.values()),
                    memberships=len(chosen),
                    candidates=len(ids),
                    india=quotas["IN"],
                    netherlands=quotas["NL"],
                    india_netherlands_ratio=quotas["IN"] / quotas["NL"],
                    top5_quota_share=top5,
                    repertoire_jaccard=len(ids & baseline_ids) / len(ids | baseline_ids),
                    quotas=quotas,
                )
            )
    summary = dict(
        selection_sha256=hashlib.sha256(selection_raw).hexdigest(),
        baseline_memberships=len(selected),
        baseline_candidates=len(baseline_ids),
        baseline_quota_sum=sum(main_quotas.values()),
        baseline_reproduced=True,
        frame=(
            "Same observed country/year/platform cells and frozen ranking; "
            "missing cells stay missing"
        ),
        scenarios=results,
        production_selection_changed=False,
        paid_calls=0,
        caveat=(
            "Operational sensitivity, not measured thematic effects or proof of representativeness"
        ),
    )
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    with (OUT / "scenarios.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=[k for k in results[0] if k != "quotas"])
        writer.writeheader()
        writer.writerows({k: v for k, v in r.items() if k != "quotas"} for r in results)
    print(json.dumps({k: v for k, v in summary.items() if k != "scenarios"}))


if __name__ == "__main__":
    main()
