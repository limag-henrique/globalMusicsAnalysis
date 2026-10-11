"""Import public contextual data and export exact-year country/music joins.

Run with uv run python scripts/import_article_context.py. No database writes.
"""

import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import httpx
import polars as pl
import pycountry
from import_article_context_supplements import load_supplements

from chart_observatory.analysis.article_context import EXCLUDED_MARKETS, export_crossings

ROOT = Path(__file__).resolve().parents[1]
WB = {
    "SI.POV.GINI": ("gini", "index_0_100"),
    "NY.GDP.PCAP.PP.KD": ("gdp_pc_ppp_constant", "constant_2021_international_dollar"),
    "NY.GDP.PCAP.CD": ("gdp_pc_current_usd", "current_USD"),
    "SL.UEM.1524.ZS": ("youth_unemployment", "percent_labor_force_age_15_24_ILO_modeled"),
    "IT.NET.USER.ZS": ("internet_users", "percent_population"),
    "IT.NET.BBND.P2": ("fixed_broadband", "subscriptions_per_100_people"),
    "SP.URB.TOTL.IN.ZS": ("urban_population", "percent_population"),
    "SP.POP.TOTL": ("population", "persons"),
    "VC.IHR.PSRC.P5": ("homicide_wdi", "per_100000_population_UNODC_WDI_republication"),
}


def download(url: str, path: Path) -> dict:
    """Cache original bytes and sidecar provenance, including failed attempts."""
    meta = path.with_suffix(path.suffix + ".provenance.json")
    if path.exists() and meta.exists():
        info = json.loads(meta.read_text(encoding="utf-8"))
        if (
            info["source_url"] != url
            or info["sha256"] != hashlib.sha256(path.read_bytes()).hexdigest()
        ):
            raise ValueError(f"Cache provenance mismatch: {path.name}")
        return info
    path.parent.mkdir(parents=True, exist_ok=True)
    response = httpx.get(url, timeout=90, follow_redirects=True)
    response.raise_for_status()
    path.write_bytes(response.content)
    info = {
        "source_url": url,
        "resolved_url": str(response.url),
        "retrieved_at": datetime.now(UTC).isoformat(),
        "status_code": response.status_code,
        "sha256": hashlib.sha256(response.content).hexdigest(),
        "bytes": len(response.content),
        "raw_path": str(path.relative_to(ROOT)),
    }
    meta.write_text(json.dumps(info, indent=2), encoding="utf-8")
    return info


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--annual",
        type=Path,
        default=ROOT
        / "data/derived/research_quality/country-all-history-20261011-022524"
        / "annual-country-metrics.csv",
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "data/derived/article-country-context/20261011"
    )
    args = parser.parse_args()
    annual = pl.read_csv(args.annual).filter(~pl.col("market_code").is_in(EXCLUDED_MARKETS))
    pairs = set(annual.select("market_code", "year").iter_rows())
    markets = sorted({country for country, _ in pairs})
    years = sorted({year for _, year in pairs})
    raw = ROOT / "data/raw/country_context/20261011"
    rows, errors, sources = [], [], []

    def add(country, year, code, value, unit, source, meta, **extra):
        if (country, year) not in pairs:
            return
        rows.append(
            {
                "market_code": country,
                "country_iso3": pycountry.countries.get(alpha_2=country).alpha_3,
                "reference_year": year,
                "indicator_code": code,
                "value": value,
                "unit": unit,
                "source": source,
                "source_url": meta["source_url"],
                "retrieved_at": meta["retrieved_at"],
                "raw_sha256": meta["sha256"],
                "raw_path": meta["raw_path"],
                "coverage_status": "observed" if value is not None else "source_missing",
                "methodology_version": "article-context-v1",
                **extra,
            }
        )

    def fetch_wb(item):
        code, (label, unit) = item
        url = f"https://api.worldbank.org/v2/country/all/indicator/{code}?format=json&date={min(years)}:{max(years)}&per_page=20000"
        path = raw / f"worldbank-{code}.json"
        try:
            meta = download(url, path)
            data = json.loads(path.read_bytes())
            if not isinstance(data, list) or len(data) != 2 or data[0]["pages"] != 1:
                raise ValueError("Invalid/paginated World Bank response")
            parsed = []
            for r in data[1]:
                country = pycountry.countries.get(alpha_3=r["countryiso3code"])
                if country and (country.alpha_2, int(r["date"])) in pairs:
                    parsed.append((country.alpha_2, int(r["date"]), r["value"]))
            return item, meta, parsed, None
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            return item, None, [], str(exc)

    with ThreadPoolExecutor(max_workers=3) as pool:
        for (code, (label, unit)), meta, parsed, error in pool.map(fetch_wb, WB.items()):
            if error:
                errors.append({"source": "worldbank", "indicator": label, "error": error})
            else:
                sources.append(meta)
                for country, year, value in parsed:
                    add(
                        country,
                        year,
                        label,
                        value,
                        unit,
                        "World Bank WDI",
                        meta,
                        original_indicator_code=code,
                    )
            print(json.dumps({"source": code, "records": len(parsed), "error": error}), flush=True)

    gii_path = raw / "HDR25_Composite_indices_complete_time_series.csv"
    url = "https://hdr.undp.org/sites/default/files/2025_HDR/HDR25_Composite_indices_complete_time_series.csv"
    try:
        meta = download(url, gii_path)
        sources.append(meta)
        # The official HDR25 CSV uses legacy Western-European bytes (e.g. Côte).
        # Preserve the original bytes/hash; record the decoding used in each row.
        try:
            gii_text = gii_path.read_text(encoding="utf-8-sig")
            encoding = "utf-8-sig"
        except UnicodeDecodeError:
            gii_text = gii_path.read_text(encoding="cp1252")
            encoding = "cp1252"
        for r in csv.DictReader(io.StringIO(gii_text)):
            country = pycountry.countries.get(alpha_3=r["iso3"])
            if not country or country.alpha_2 not in markets:
                continue
            for year in years:
                value = r.get(f"gii_{year}", "").strip()
                add(
                    country.alpha_2,
                    year,
                    "gender_inequality_index",
                    float(value) if value and value != ".." else None,
                    "index_0_1",
                    "UNDP HDR 2025",
                    meta,
                    source_encoding=encoding,
                )
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        errors.append({"source": "undp", "error": str(exc)})

    domains = "pornhub.com,xvideos.com,xnxx.com"
    for year in years:
        until = "2022-03-14" if year == 2022 else f"{year + 1}-01-01"
        url = str(
            httpx.URL(
                "https://api.ooni.io/api/v1/aggregation",
                params={
                    "probe_cc": ",".join(markets),
                    "test_name": "web_connectivity",
                    "domain": domains,
                    "since": f"{year}-01-01",
                    "until": until,
                    "axis_x": "probe_cc",
                    "axis_y": "domain",
                },
            )
        )
        path = raw / f"ooni-adult-domains-{year}.json"
        try:
            meta = download(url, path)
            data = json.loads(path.read_bytes())
            if "error" in data or not isinstance(data.get("result"), list):
                raise ValueError(str(data)[:200])
            sources.append(meta)
            totals = {}
            for r in data["result"]:
                counts = totals.setdefault(r["probe_cc"], Counter())
                for key in [
                    "anomaly_count",
                    "confirmed_count",
                    "failure_count",
                    "ok_count",
                    "measurement_count",
                ]:
                    counts[key] += r[key]
            for country, counts in totals.items():
                common = {
                    "sample_scope": domains,
                    "period_start": f"{year}-01-01",
                    "period_end": "2022-03-13" if year == 2022 else f"{year}-12-31",
                }
                for key in [
                    "anomaly_count",
                    "confirmed_count",
                    "failure_count",
                    "ok_count",
                    "measurement_count",
                ]:
                    add(
                        country,
                        year,
                        "ooni_" + key,
                        float(counts[key]),
                        "tests",
                        "OONI selected adult domains",
                        meta,
                        **common,
                    )
                denominator = counts["measurement_count"] - counts["failure_count"]
                for key in ["anomaly", "confirmed"]:
                    add(
                        country,
                        year,
                        "ooni_" + key + "_pct_valid_tests",
                        100 * counts[key + "_count"] / denominator if denominator else None,
                        "percent_nonfailed_tests_not_population",
                        "OONI selected adult domains",
                        meta,
                        **common,
                    )
            print(
                json.dumps({"source": "ooni", "year": year, "markets_with_tests": len(totals)}),
                flush=True,
            )
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            errors.append({"source": "ooni", "year": year, "error": str(exc)})
            print(json.dumps({"source": "ooni", "year": year, "error": str(exc)}), flush=True)

    supplementary_rows, supplementary_sources, supplementary_indicators = load_supplements(
        ROOT, pairs
    )
    rows.extend(supplementary_rows)
    sources.extend(supplementary_sources)
    for source in supplementary_sources:
        if "error" in source:
            errors.append(source)
    blockers = [
        (
            "WVS/EVS",
            "wvs_sexual_values",
            "microdata_download_unavailable",
            "https://www.worldvaluessurvey.org/WVSEVSjoint2017.jsp",
            "Official CSV download returned whitespace; weighted survey aggregates unavailable",
        ),
        (
            "Radar/Similarweb",
            "pornography_interest",
            "access_and_historical_coverage_unverified",
            "https://developers.cloudflare.com/radar/investigate/dns/",
            "No authenticated access; DNS/traffic do not directly measure population consumption",
        ),
        (
            "TikTok Research API",
            "tiktok_music_exposure",
            "restricted_access_no_track_time_data",
            "https://developers.tiktok.com/products/research-api/",
            "No approved access and no historical sound-to-track exposure series",
        ),
    ]
    retrieved = datetime.now(UTC).isoformat()
    for source, code, status, url, reason in blockers:
        for country, year in sorted(pairs):
            rows.append(
                {
                    "market_code": country,
                    "country_iso3": pycountry.countries.get(alpha_2=country).alpha_3,
                    "reference_year": year,
                    "indicator_code": code,
                    "value": None,
                    "unit": "not_yet_operationalized",
                    "source": source,
                    "source_url": url,
                    "retrieved_at": retrieved,
                    "raw_sha256": None,
                    "raw_path": None,
                    "coverage_status": status,
                    "methodology_version": "article-context-v1",
                    "limitation": reason,
                }
            )
    observations = pl.from_dicts(rows, infer_schema_length=None)
    indicators = (
        [item[0] for item in WB.values()]
        + ["gender_inequality_index"]
        + [
            "ooni_" + key
            for key in [
                "anomaly_count",
                "confirmed_count",
                "failure_count",
                "ok_count",
                "measurement_count",
                "anomaly_pct_valid_tests",
                "confirmed_pct_valid_tests",
            ]
        ]
    )
    indicators += supplementary_indicators + [b[1] for b in blockers]
    result = export_crossings(annual, observations, indicators, args.output)
    coverage = pl.read_parquet(args.output / "coverage.parquet")
    coverage.group_by("indicator_code", "coverage_status").len().sort(
        "indicator_code", "coverage_status"
    ).write_csv(args.output / "coverage-summary.csv")
    for name in ["genre_variation", "persistence"]:
        frame = pl.read_parquet(ROOT / f"data/derived/article/{name}.parquet")
        frame = frame.filter(pl.col("market_code").is_in(markets))
        if "year" in frame.columns:
            frame = frame.join(
                annual.select("market_code", "year"), on=["market_code", "year"], how="semi"
            )
        frame.write_parquet(args.output / f"music-{name}.parquet")
        frame.write_csv(args.output / f"music-{name}.csv")
    diversity_path = ROOT / "data/derived/genre_diversity_by_market_period.parquet"
    diversity = pl.read_parquet(diversity_path).rename({"country_code": "market_code"})
    diversity = diversity.join(
        annual.select("market_code", "year"), on=["market_code", "year"], how="semi"
    )
    diversity.write_csv(args.output / "music-genre-diversity.csv")
    diversity.write_parquet(args.output / "music-genre-diversity.parquet")
    pl.DataFrame(
        [
            {
                "source": source,
                "indicator_code": code,
                "status": status,
                "source_url": url,
                "reason": reason,
            }
            for source, code, status, url, reason in blockers
        ]
    ).write_csv(args.output / "sources-status.csv")
    music_paths = [
        ROOT / f"data/derived/article/{name}.parquet" for name in ["genre_variation", "persistence"]
    ] + [diversity_path]
    manifest = {
        "methodology_version": "article-context-v1",
        "annual_input": str(args.annual),
        "annual_input_sha256": hashlib.sha256(args.annual.read_bytes()).hexdigest(),
        "markets": markets,
        "years": years,
        "music_cutoff": "2022-03-13",
        **result,
        "sources": sources,
        "music_inputs": [
            {"path": str(p.relative_to(ROOT)), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in music_paths
        ],
        "errors": errors,
        "notes": [
            "Exact year only; no interpolation or imputation",
            "2022 annual context can include months after music cutoff",
            "OONI sample covers three selected domains; anomalies are not confirmed blocking",
            "WDI homicide republishes UNODC; do not treat as independent evidence",
        ],
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
