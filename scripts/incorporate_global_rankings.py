"""Build versioned global population quotas; optionally collect public chart titles.

Writes a separate evidence database, never the canonical corpus or paid queues.
Run with --collect to extract the documented Apple national charts.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import pycountry

from chart_observatory.ingestion.global_expansion import (
    african_ranking,
    apple_ranking,
    population_quota,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research/global_inventory/expansion_20261108"
RUNTIME = ROOT / "data/runtime/global-expansion-20261108"


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    RUNTIME.mkdir(parents=True, exist_ok=True)
    countries = read("research/global_inventory/countries_20261108.json")
    legacy_path = (
        ROOT
        / "data/derived/annual_revision/reconciled-russia-2018-2026-20261031"
        / "sources/country_quotas.csv"
    )
    with legacy_path.open(encoding="utf-8-sig", newline="") as f:
        legacy = {r["country_code"]: r for r in csv.DictReader(f)}
    wb = read("research/global_inventory/inputs_20261108/population-worldbank-2024.json")
    population = {
        r["country"]["id"]: (int(r["value"]), 2024, wb["url"], "WORLD_BANK_ESTIMATE")
        for r in wb["response"][1]
        if r.get("value")
    }
    un = read("research/global_inventory/inputs_20261108/un_population_2024.json")
    for r in un["rows"]:
        population.setdefault(
            r["ISO2_code"],
            (int(Decimal(r["TPopulation1July"]) * 1000), 2024, un["url"], "UN_WPP2024_PROJECTION"),
        )
    supplements = {
        "PN": (
            42,
            2022,
            "https://digitallibrary.un.org/record/4040657/files/A_AC.109_2024_12-EN.pdf",
            "UN_2022_INCLUDES_TEMPORARILY_ABROAD_NOT_2024",
        ),
        "CC": (
            593,
            2021,
            "https://www.abs.gov.au/census/find-census-data/quickstats/2021/90102",
            "CENSUS_2021_NOT_2024",
        ),
        "AX": (
            30654,
            2024,
            "https://www.lagtinget.ax/dokument/finans-och-naringsutskottets-utlatande-over-lf-202024-2025-58904",
            "YEAR_END_COUNT",
        ),
        "CX": (
            1692,
            2021,
            "https://abs.gov.au/census/find-census-data/quickstats/2021/SAL90001",
            "CENSUS_2021_NOT_2024",
        ),
        "NF": (
            2188,
            2021,
            "https://www.abs.gov.au/articles/understanding-ancestry-language-and-birthplace-norfolk-island-population",
            "CENSUS_2021_NOT_2024",
        ),
    }
    population.update(supplements)
    aliases = dict(
        zip(
            [
                "Brunei",
                "Cape Verde",
                "Congo, Dem. Rep. (Zaire)",
                "Cote d'Ivoire",
                "East Timor",
                "Gambia, The",
                "Korea, North",
                "Korea, South",
                "Lao People's Dem Rep",
                "Macau",
                "Macedonia (Former Yug. Rep)",
                "Micronesia",
                "Myanmar (Burma)",
                "Reunion",
                "Saint Vincent and Grenadines",
                "Western Samoa",
                "St Kitts & Nevis",
                "Swaziland",
                "Turkey",
                "Virgin Islands (U.S.)",
            ],
            [
                "BN",
                "CV",
                "CD",
                "CI",
                "TL",
                "GM",
                "KP",
                "KR",
                "LA",
                "MO",
                "MK",
                "FM",
                "MM",
                "RE",
                "VC",
                "WS",
                "KN",
                "SZ",
                "TR",
                "VI",
            ],
            strict=True,
        )
    )
    diversity = {}
    for r in read("research/global_inventory/inputs_20261108/alesina-all.json"):
        if not isinstance(r["ethnic"], (int, float)):
            continue
        name = r["source_country"].strip()
        try:
            code = aliases.get(name) or pycountry.countries.lookup(name).alpha_2
        except LookupError:
            continue
        if code in diversity:
            raise ValueError(f"ambiguous diversity mapping: {code}")
        diversity[code] = r["ethnic"]
    rows = []
    for c in countries:
        code = c["country_code"]
        old = legacy.get(code)
        p = population.get(code)
        if old:
            p = (int(old["population_2024"]), 2024, old["population_source"], "LEGACY_FROZEN")
        d = float(old["historical_ethnic_diversity"]) if old else diversity.get(code)
        quota = int(old["quota_per_year_main"]) if old else population_quota(p[0], d) if p else None
        rows.append(
            dict(
                country_code=code,
                country_name=c["country_name"],
                region=c["region"],
                population=p[0] if p else None,
                population_year=p[1] if p else None,
                population_source=p[2] if p else None,
                population_status=p[3] if p else "POPULATION_REVIEW_REQUIRED",
                historical_diversity=d,
                diversity_status="HISTORICAL_ALESINA_2003"
                if d is not None
                else "MISSING_NEUTRAL_MULTIPLIER",
                quota_per_year_main=quota,
                legacy_frozen=bool(old),
                annual_years=list(range(2018, 2027)),
                annual_admission="FULL_CALENDAR_AND_IDENTITY_GATE_REQUIRED",
            )
        )
    manifest = dict(
        version="global-population-20261108-v1",
        countries=rows,
        coefficient=7.470872933481587,
        floor=100,
        ceiling=500,
        step=10,
        formula="min(500,100+10*floor(7.470872933481587*sqrt(population/1000000)*(1+0.5*diversity)/10))",
        legacy_quota_sha256=hashlib.sha256(legacy_path.read_bytes()).hexdigest(),
        paid_calls_authorized=False,
        annual_2026_partial=True,
        policy=(
            "Evidence staging only. Preserve legacy corpus. Missing population holds quota; "
            "missing diversity uses explicit neutral multiplier. "
            "Current snapshots are never annual ranks."
        ),
    )
    write(OUT / "campaign.json", manifest)
    registry = read("research/global_inventory/source_registry_20261108.json")
    enabled = {"APPLE_DOCUMENTED_COUNTRY_PLAYLISTS", "TURNTABLE_NG", "MDUNDO"}
    write(
        OUT / "source_admission_plan.json",
        [
            dict(
                source_id=s["source_id"],
                countries=s["countries"],
                scope=s["scope"],
                family=s["family"],
                evidence_url=s["evidence_url"],
                snapshot_adapter=(
                    "ENABLED_DOCUMENTED_URLS_ONLY"
                    if s["source_id"] in enabled
                    else "HOLD_PROVIDER_SPECIFIC_ADAPTER_AND_ACCESS_REVIEW"
                ),
                annual_admission="HOLD_UNTIL_COMPLETE_CALENDAR_AND_COMPARABLE_METRIC_VERIFIED",
                regional_replication_allowed=False,
                paid_acquisition_allowed=False,
            )
            for s in registry["sources"]
        ],
    )
    write(
        OUT / "input_integrity.json",
        {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT / "research/global_inventory/inputs_20261108").glob("*.json"))
        },
    )
    write(
        OUT / "population_evidence.json",
        dict(world_bank=wb["url"], un_wpp=un["url"], un_raw_sha256=un["raw_sha256"], rows=rows),
    )
    with (OUT / "country_quotas.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "country_code",
                "quota_per_year_main",
                "population",
                "population_year",
                "population_status",
            ],
        )
        writer.writeheader()
        writer.writerows(
            {k: r[k] for k in writer.fieldnames}
            for r in rows
            if r["quota_per_year_main"] is not None
        )
    write(
        OUT / "annual_admission_queue.json",
        [
            dict(
                country_code=r["country_code"],
                year=y,
                quota=r["quota_per_year_main"],
                status="LEGACY_MEMBERSHIPS_PRESERVED"
                if r["legacy_frozen"]
                else "AWAITING_VERIFIED_COMPLETE_ANNUAL_RANKING",
            )
            for r in rows
            for y in range(2018, 2027)
        ],
    )
    return rows


def collect(rows, retry_held=False):
    quotas = {r["country_code"]: r["quota_per_year_main"] for r in rows}
    directory = read("research/global_inventory/apple_country_chart_directory_20261108.json")
    tasks = [dict(t, source="APPLE_NATIONAL_DAILY") for t in directory["rows"]]
    tasks.extend(
        [
            dict(
                country_code="NG",
                source="TURNTABLE_NG_COMPOSITE",
                playlist_url="https://www.turntablecharts.com/charts/1",
            ),
            dict(
                country_code="KE",
                source="MDUNDO_KE_WEEKLY",
                playlist_url="https://mdundo.com/best/ke/64",
            ),
        ]
    )
    db = sqlite3.connect(RUNTIME / "evidence.sqlite3")
    db.execute(
        "CREATE TABLE IF NOT EXISTS captures_v2 (country TEXT, sha256 TEXT, "
        "payload TEXT NOT NULL, PRIMARY KEY(country,sha256))"
    )
    results = []
    previous_path = OUT / "extraction_results.json"
    if retry_held and previous_path.exists():
        previous = json.loads(previous_path.read_text(encoding="utf-8"))
        results = [r for r in previous if r["status"] == "CAPTURED_EVIDENCE_ONLY"]
        done = {(r["country_code"], r["source"]) for r in results}
        tasks = [t for t in tasks if (t["country_code"], t["source"]) not in done]
    with httpx.Client(timeout=45, follow_redirects=True) as client:
        for task in tasks:
            code = task["country_code"]
            result = dict(
                country_code=code,
                source=task["source"],
                url=task["playlist_url"],
                quota=quotas[code],
            )
            try:
                response = client.get(task["playlist_url"])
                response.raise_for_status()
                raw = response.content
                digest = hashlib.sha256(raw).hexdigest()
                (RUNTIME / f"apple-{code}-{digest}.html").write_bytes(raw)
                parsed = (
                    apple_ranking(
                        response.text,
                        task["provider_chart_label"],
                        urlsplit(task["playlist_url"]).path.rsplit("/", 1)[1],
                    )
                    if task["source"] == "APPLE_NATIONAL_DAILY"
                    else african_ranking(response.text, task["source"])
                )
                selected = parsed["rows"][: quotas[code]] if quotas[code] else []
                result.update(
                    parsed,
                    observed_at=datetime.now(UTC).isoformat(),
                    sha256=digest,
                    status="CAPTURED_EVIDENCE_ONLY",
                    available_depth=len(parsed["rows"]),
                    selected_count=len(selected),
                    quota_shortfall=max(0, (quotas[code] or 0) - len(selected)),
                    selected_rows=selected,
                )
                db.execute(
                    "INSERT OR IGNORE INTO captures_v2 VALUES (?,?,?)",
                    (code, digest, json.dumps(result, ensure_ascii=False)),
                )
                db.commit()
            except Exception as exc:
                result.update(status="HELD_EXTRACTION_ERROR", error=f"{type(exc).__name__}: {exc}")
            results.append(result)
            write(OUT / "extraction_results.json", results)
            print(f"{code}: {result['status']} {result.get('selected_count', 0)}", flush=True)
            time.sleep(1)
    db.close()
    with (OUT / "ranked_titles.jsonl").open("w", encoding="utf-8") as f:
        for result in results:
            for row in result.get("selected_rows", []):
                f.write(
                    json.dumps(
                        dict(
                            country_code=result["country_code"],
                            source=result["source"],
                            observed_at=result["observed_at"],
                            source_published_at=result["source_published_at"],
                            period_scope=result["period_scope"],
                            annual_rank_certified=False,
                            **row,
                        ),
                        ensure_ascii=False,
                    )
                    + "\n"
                )


def verify_cached():
    results = json.loads((OUT / "extraction_results.json").read_text(encoding="utf-8"))
    directory = read("research/global_inventory/apple_country_chart_directory_20261108.json")
    labels = {t["country_code"]: t["provider_chart_label"] for t in directory["rows"]}
    verified = 0
    for result in results:
        if result["status"] != "CAPTURED_EVIDENCE_ONLY":
            continue
        raw = (RUNTIME / f"apple-{result['country_code']}-{result['sha256']}.html").read_bytes()
        if hashlib.sha256(raw).hexdigest() != result["sha256"]:
            raise ValueError("raw evidence hash mismatch")
        html = raw.decode("utf-8")
        parsed = (
            apple_ranking(
                html, labels[result["country_code"]], urlsplit(result["url"]).path.rsplit("/", 1)[1]
            )
            if result["source"] == "APPLE_NATIONAL_DAILY"
            else african_ranking(html, result["source"])
        )
        if parsed["rows"] != result["rows"] or parsed["annual_rank_certified"]:
            raise ValueError("stored evidence differs from validated extraction")
        verified += len(parsed["rows"])
    with sqlite3.connect(RUNTIME / "evidence.sqlite3") as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("evidence database integrity failure")
    report = dict(
        verified_rows=verified,
        verified_at=datetime.now(UTC).isoformat(),
        network_calls=0,
        paid_calls=0,
        status="PASS",
    )
    write(OUT / "cached_verification.json", report)
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collect", action="store_true")
    parser.add_argument("--verify-cached", action="store_true")
    parser.add_argument(
        "--retry-held",
        action="store_true",
        help="Resume without requesting successful captures again",
    )
    args = parser.parse_args()
    rows = build()
    print(
        f"Incorporated {len(rows)} countries/areas; "
        f"{sum(r['quota_per_year_main'] is not None for r in rows)} population quotas",
        flush=True,
    )
    if args.collect:
        collect(rows, retry_held=args.retry_held)
    if args.verify_cached:
        verify_cached()
