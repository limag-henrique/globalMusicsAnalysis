"""Analyze missing annual ranking cells (2018-2026) and separate current snapshots,
quota-unresolved territories, and external source dependencies.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from chart_observatory.research_flow import load_selection

ROOT = Path(__file__).resolve().parents[1]
COLLAB = ROOT / "data/runtime/antigravity-collaboration-20261115"
V5_SEL = ROOT / "data/derived/annual_revision/global-rescan-2018-2026-20261115-v5-published-provisional-0003"


def main() -> None:
    countries = json.loads((V5_SEL / "countries.json").read_text(encoding="utf-8-sig"))
    country_map = {c["country_code"]: c for c in countries}
    _, cells, _, _ = load_selection(V5_SEL)
    cell_map = {(c["country_code"], int(c["year"])): c for c in cells}

    yt_dir = COLLAB / "worldwide-chart-recovery-20261116-codex/source-directory.json"
    yt_markets = set()
    if yt_dir.is_file():
        yt_markets = set(json.loads(yt_dir.read_text(encoding="utf-8")).get("markets", {}).keys())

    yt_cp_path = COLLAB / "worldwide-chart-recovery-20261116-codex/checkpoint.json"
    yt_failed_markets = Counter()
    if yt_cp_path.is_file():
        cp = json.loads(yt_cp_path.read_text(encoding="utf-8"))
        for k, v in cp.items():
            cc = k.split("/", 1)[0]
            if v.get("status") == "historical_route_unresolved":
                yt_failed_markets[cc] += 1

    final_rankings_path = ROOT / "data/runtime/final-pipeline/rankings-report.json"
    current_charts: dict[str, dict[str, Any]] = defaultdict(dict)
    if final_rankings_path.is_file():
        fr = json.loads(final_rankings_path.read_text(encoding="utf-8"))
        for ch in fr.get("charts", []):
            current_charts[ch["country"]][ch["platform"]] = {
                "status": ch.get("status"),
                "observed_positions": ch.get("observed_positions"),
                "period": ch.get("period"),
                "annual_ranking": False,
            }

    queue_path = COLLAB / "missing-ranking-queue-20261116.jsonl"
    v5_gaps: list[dict[str, Any]] = []
    v4_gaps_count = 0
    with queue_path.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if row["scope"] == "v4":
                v4_gaps_count += 1
                continue
            cc = row["country_code"]
            yr = int(row["year"])
            cinfo = country_map.get(cc, {})
            cell = cell_map.get((cc, yr), {})
            status = row["provenance_status"]
            curr = current_charts.get(cc, {})
            if status == "POPULATION_QUOTA_UNRESOLVED":
                dep = "methodological_decision_required_for_territory_population_quota"
                avail_src = None
                depth = 0
            elif cc in yt_markets:
                dep = (
                    "youtube_charts_historical_spa_timeout_or_no_annual_archive"
                    if yt_failed_markets.get(cc)
                    else "youtube_charts_official_market_requires_authenticated_or_full_year_weekly_archive"
                )
                avail_src = "YOUTUBE_CHARTS_OFFICIAL_DIRECTORY (current/weekly only; annual unverified)"
                depth = curr.get("YOUTUBE", {}).get("observed_positions") or 0
            elif any(p.get("status") in {"complete", "partial"} for p in curr.values()):
                dep = "current_kworb_snapshot_only_does_not_replace_annual_2018_2026_ranking"
                avail_src = "KWORB_CURRENT_SNAPSHOT_ONLY"
                depth = max((p.get("observed_positions") or 0 for p in curr.values()), default=0)
            else:
                dep = "no_public_annual_source_in_mgd_kaggle_spotify_youtube_or_ifpi"
                avail_src = None
                depth = 0

            v5_gaps.append({
                "country_code": cc,
                "country_name": cinfo.get("country_name"),
                "year": yr,
                "requested_positions": row.get("quota"),
                "observed_positions": row.get("observed_positions"),
                "missing_positions": row.get("missing_ranking_positions"),
                "provenance_status": status,
                "available_source": avail_src,
                "available_snapshot_depth": depth,
                "covered_calendar": cell.get("covered_calendar") or "none_verified_for_annual",
                "reconstruction_artifact": cell.get("source_artifact") or None,
                "external_dependency_or_restriction": dep,
                "current_snapshots_separate": curr,
            })

    summary = {
        "schema_version": "missing-ranking-gap-analysis-20261116-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "v4_missing_cells": v4_gaps_count,
        "v5_missing_cells": len(v5_gaps),
        "v5_by_provenance_status": dict(Counter(g["provenance_status"] for g in v5_gaps)),
        "v5_by_dependency": dict(Counter(g["external_dependency_or_restriction"] for g in v5_gaps)),
        "v5_missing_positions_known_quota": sum(
            g["missing_positions"] for g in v5_gaps if isinstance(g["missing_positions"], int)
        ),
        "population_quota_unresolved_countries": sorted(
            {g["country_code"] for g in v5_gaps if g["provenance_status"] == "POPULATION_QUOTA_UNRESOLVED"}
        ),
        "note": (
            "Current daily/weekly Kworb snapshots are strictly separated and never substituted "
            "for annual 2018-2026 rankings. No quotas, countries, or denominators were altered."
        ),
    }

    out_json = COLLAB / "missing-ranking-gap-analysis-20261116.json"
    out_jsonl = COLLAB / "missing-ranking-gap-analysis-20261116.jsonl"
    out_jsonl.write_text(
        "".join(json.dumps(g, ensure_ascii=False, sort_keys=True) + "\n" for g in v5_gaps),
        encoding="utf-8",
    )
    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
