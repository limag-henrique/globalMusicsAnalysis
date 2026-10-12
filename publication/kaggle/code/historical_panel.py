"""Duration-weighted local Trends trajectories, with auditable censoring and coverage."""

import calendar
import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import polars as pl

from article_context import EXCLUDED_MARKETS


def export_historical_panel(
    annual: pl.DataFrame,
    observations: pl.DataFrame,
    output: Path,
) -> dict[str, int]:
    """Export one row per musical country-year and separate local term/batch series."""
    annual = annual.filter(~pl.col("market_code").is_in(EXCLUDED_MARKETS))
    if annual.select(pl.struct("market_code", "year").n_unique()).item() != annual.height:
        raise ValueError("Duplicate musical country/year")
    music = {(r["market_code"], r["year"]): r for r in annual.to_dicts()}
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    seen = set()
    for row in observations.to_dicts():
        key = (row["country_iso2"], row["term"], row["language"], row["comparison_group"])
        sample = (*key, row["sample_date"])
        if sample in seen:
            raise ValueError("Duplicate Trends sample")
        seen.add(sample)
        grouped[key].append(row)
    records = []
    for (country, term, language, group), rows in sorted(grouped.items()):
        windows = {(r["period_start"], r["period_end"], r["aggregation"]) for r in rows}
        if len(windows) != 1:
            raise ValueError("Inconsistent window or aggregation within series")
        start_text, end_text, aggregation = windows.pop()
        start, end = date.fromisoformat(start_text), date.fromisoformat(end_text)
        buckets = []
        for r in rows:
            day = date.fromisoformat(r["sample_date"])
            if aggregation in {"Month", "Mês"}:
                if day.day != 1:
                    raise ValueError("Monthly sample must start on day one")
                last = day.replace(day=calendar.monthrange(day.year, day.month)[1])
            elif aggregation in {"Week", "Semana"}:
                last = day + timedelta(days=6)
            elif aggregation in {"Day", "Dia"}:
                last = day
            else:
                raise ValueError(f"Unsupported aggregation: {aggregation}")
            if last < start or day > end:
                raise ValueError("Trends sample outside requested window")
            buckets.append((day, last, r))
        buckets.sort(key=lambda b: b[0])
        if any(buckets[i][0] <= buckets[i - 1][1] for i in range(1, len(buckets))):
            raise ValueError("Overlapping Trends buckets")
        for (market, year), musical in sorted(music.items()):
            if market != country:
                continue
            first = max(start, date(year, 1, 1))
            last_day = min(end, date(year, 12, 31))
            if first > last_day:
                continue
            lower = upper = 0.0
            days = censored = numeric = zeros = excluded = missing = 0
            for day, last, r in buckets:
                left, right = max(first, day), min(last_day, last)
                if left > right:
                    continue
                if day < start or last > end:
                    excluded += 1
                    continue
                weight = (right - left).days + 1
                if r["status"] == "below_reporting_threshold":
                    lo, hi = 0.0, 1.0
                    censored += 1
                elif r["status"] == "observed_relative_index" and r["value"] is not None:
                    lo = hi = float(r["value"])
                    if not 0 <= lo <= 100:
                        raise ValueError("Trends value outside 0-100")
                    numeric += 1
                    zeros += int(lo == 0)
                else:
                    missing += 1
                    continue
                days += weight
                lower += lo * weight
                upper += hi * weight
            expected = (last_day - first).days + 1
            records.append(
                {
                    **musical,
                    "term": term,
                    "language": language,
                    "comparison_group": group,
                    "period_start": first.isoformat(),
                    "period_end": last_day.isoformat(),
                    "series_start": start_text,
                    "series_end": end_text,
                    "aggregation": aggregation,
                    "covered_days": days,
                    "expected_days": expected,
                    "temporal_coverage": days / expected,
                    "numeric_samples": numeric,
                    "censored_samples": censored,
                    "zero_samples": zeros,
                    "missing_samples": missing,
                    "excluded_boundary_samples": excluded,
                    "mean_lower": lower / days if days else None,
                    "mean_upper": upper / days if days else None,
                    "mean_index": lower / days if days and not censored and not missing else None,
                    "partial_year": first != date(year, 1, 1) or last_day != date(year, 12, 31),
                    "cross_country_comparable": False,
                    "raw_sha256": ";".join(sorted({r["raw_sha256"] for r in rows})),
                    "source": "google_trends_export",
                }
            )
    panel = pl.from_dicts(records, infer_schema_length=None)
    output.mkdir(parents=True, exist_ok=True)
    panel.write_csv(output / "country-year-trends.csv")
    panel.write_parquet(output / "country-year-trends.parquet")
    # Keep the musical denominator at its original country-year grain.
    annual.write_csv(output / "country-year-music.csv")
    annual.write_parquet(output / "country-year-music.parquet")
    result = {
        "country_years": annual.height,
        "series_years": panel.height,
        "countries": annual["market_code"].n_unique(),
        "series": len(grouped),
    }
    (output / "panel-status.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
