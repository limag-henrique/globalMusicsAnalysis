"""Incorporate every global country/year quota using audited historical archives.

Existing frozen selections are retained. Current daily snapshots are not inputs.
No network, lyrics acquisition or paid APIs. --apply adds separate PostgreSQL tables.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from datetime import date
from pathlib import Path

os.environ.setdefault("POLARS_MAX_THREADS", "2")
import polars as pl
from sqlalchemy import create_engine

from chart_observatory.config import Settings
from chart_observatory.ingestion.archive_metadata import apply_archive_repairs
from chart_observatory.ingestion.global_annual import assemble, persist
from chart_observatory.ingestion.historical_backfill import (
    annual_ranks,
    integer_metric,
    merge_sources,
)
from chart_observatory.ingestion.import_quotas import apply_native_display_metadata

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/derived/annual_revision/reconciled-russia-2018-2026-20261031"
POLICY = ROOT / "research/global_inventory/expansion_20261108/campaign.json"
RAW = ROOT / "data/raw/historical_backfill/20261030/zenodo-23645386"
DAILY = (
    ROOT / "data/derived/annual_revision/backfill-2018-2026-20261030/sources/kaggle_daily.parquet"
)
OUT = ROOT / "data/derived/annual_revision/global-2018-2026-20261108"
CUTOFF = date(2026, 10, 15)


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def jsonl(path, rows):
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def build(output):
    output.mkdir(parents=True, exist_ok=True)
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    countries = policy["countries"]
    markets = {
        c["country_code"]
        for c in countries
        if c["quota_per_year_main"] is not None and not c["legacy_frozen"]
    }
    baseline = [
        json.loads(line)
        for line in (BASE / "combined.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rankings, coverage = [], []
    adjudication = []
    inputs = [POLICY, BASE / "combined.jsonl", DAILY]
    for year in range(2018, 2027):
        for platform, prefix, metric, native in [
            ("SPOTIFY", "spotify_top200", "streams", "track_id"),
            ("YOUTUBE", "youtube_top100", "views", "key"),
        ]:
            path = RAW / f"{prefix}_positions_{year}.csv.gz"
            inputs.append(path)
            frame = (
                pl.read_csv(path, infer_schema=False)
                .select(
                    pl.col("cc").str.to_uppercase().alias("country_code"),
                    pl.col("week_end").str.to_date().alias("period_end"),
                    pl.col(native).alias("source_identifier"),
                    integer_metric("rank").alias("source_position"),
                    pl.when(
                        pl.col(native).str.contains(
                            r"^[A-Za-z0-9]{22}$"
                            if platform == "SPOTIFY"
                            else r"^(?:[A-Za-z0-9_-]{11}|T:.+)$"
                        )
                    )
                    .then(pl.col(native))
                    .otherwise(None)
                    .alias("native_id"),
                    pl.col("title"),
                    pl.col("artists").alias("artist"),
                    integer_metric(metric).alias("metric_value"),
                )
                .filter(pl.col("country_code").is_in(sorted(markets)))
            )
            conflicts = (
                frame.filter(pl.col("period_end").dt.year() == year)
                .filter(pl.col("period_end") <= CUTOFF)
                .group_by("country_code", "period_end", "native_id")
                .agg(
                    pl.col("metric_value").n_unique().alias("metric_variants"),
                    pl.struct(
                        "source_position", "source_identifier", "title", "artist", "metric_value"
                    ).alias("observations"),
                )
                .filter((pl.col("metric_variants") > 1) | pl.col("native_id").is_null())
            )
            for conflict in conflicts.to_dicts():
                conflict["period_end"] = conflict["period_end"].isoformat()
                adjudication.append(
                    dict(
                        source=str(path.relative_to(ROOT)),
                        platform=platform,
                        year=year,
                        paid_calls_authorized=False,
                        **conflict,
                    )
                )
            rows, cells = annual_ranks(
                frame,
                markets=markets,
                year=year,
                cutoff=CUTOFF,
                frequency="WEEKLY",
                platform=platform,
                provider=f"ZENODO_23645386_{platform}",
            )
            rankings, coverage = merge_sources(rankings, coverage, rows, cells)
        print(json.dumps(dict(stage="weekly", year=year, source_cells=len(coverage))), flush=True)
    daily = (
        pl.scan_parquet(DAILY)
        .filter(pl.col("country_code").is_in(sorted(markets)))
        .with_columns(
            pl.when(pl.col("native_id").str.contains(r"^[A-Za-z0-9]{22}$"))
            .then(pl.col("native_id"))
            .otherwise(None)
            .alias("native_id")
        )
        .collect(engine="streaming")
    )
    for year in range(2018, 2027):
        rows, cells = annual_ranks(
            daily.filter(pl.col("period_end").dt.year() == year),
            markets=markets,
            year=year,
            cutoff=CUTOFF,
            frequency="DAILY",
            platform="SPOTIFY",
            provider="KAGGLE_GONZALOPEZGIL_V151",
        )
        rankings, coverage = merge_sources(rankings, coverage, rows, cells)
    result = assemble(countries, baseline, rankings, coverage)
    adjudication.sort(
        key=lambda r: (
            r["country_code"],
            r["year"],
            r["platform"],
            r["period_end"],
            r["native_id"] or "",
        )
    )
    jsonl(output / "adjudication_tasks.jsonl", adjudication)
    display_refs = output / "native-display-metadata.json"
    if display_refs.exists():
        refs = json.loads(display_refs.read_text(encoding="utf-8"))
        new_rows = [r for r in result["memberships"] if r["country_code"] in markets]
        apply_native_display_metadata(new_rows, refs)
        inputs.append(display_refs)
    archive_refs = output / "archive-display-metadata.json"
    archive_repairs = 0
    if archive_refs.exists():
        archive_repairs = apply_archive_repairs(
            result["memberships"], json.loads(archive_refs.read_text(encoding="utf-8"))
        )
        inputs.append(archive_refs)
    pl.DataFrame(rankings).write_parquet(output / "new_market_rankings.parquet")
    dump(output / "source_coverage.json", coverage)
    jsonl(output / "combined.jsonl", result["memberships"])
    jsonl(
        output / "ranked_titles.jsonl",
        [
            {
                k: r.get(k)
                for k in (
                    "country_code",
                    "year",
                    "position",
                    "title",
                    "artist",
                    "platform",
                    "provider",
                    "candidate_id",
                    "metric_value",
                    "selection_status",
                    "identity_status",
                    "not_for_paid_submission",
                )
            }
            for r in result["memberships"]
        ],
    )
    jsonl(output / "country_years.jsonl", result["cells"])
    dump(output / "countries.json", countries)
    registry = json.loads(
        (ROOT / "research/global_inventory/source_registry_20261108.json").read_text(
            encoding="utf-8"
        )
    )["sources"]
    jsonl(
        output / "historical_requests.jsonl",
        [
            dict(
                country_code=c["country_code"],
                year=c["year"],
                quota=c["quota"],
                missing_positions=c["missing_positions"],
                status=c["status"],
                candidate_national_sources=[
                    dict(source_id=s["source_id"], url=s["evidence_url"], family=s["family"])
                    for s in registry
                    if c["country_code"] in s["countries"]
                    and s["scope"] in {"NATIONAL", "NATIONAL_PLATFORM_LABEL"}
                ],
                requires_complete_calendar=True,
                acquisition_paid_authorized=False,
            )
            for c in result["cells"]
        ],
    )
    with (output / "country_years.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(result["cells"][0]))
        writer.writeheader()
        writer.writerows(
            {k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in row.items()}
            for row in result["cells"]
        )
    input_hashes = {}
    for path in inputs:
        with path.open("rb") as f:
            input_hashes[str(path.relative_to(ROOT))] = hashlib.file_digest(f, "sha256").hexdigest()
    manifest = dict(
        protocol="worldwide-annual-quotas-v1",
        years=list(range(2018, 2027)),
        cutoff=CUTOFF.isoformat(),
        countries=len(countries),
        country_year_cells=len(result["cells"]),
        requested_positions=sum(c["quota"] or 0 for c in result["cells"]),
        preserved_legacy_memberships=len(baseline),
        memberships=len(result["memberships"]),
        new_definitive_memberships=result["new_definitive_memberships"],
        new_provisional_memberships=result["new_provisional_memberships"],
        candidate_identities=len({r["candidate_id"] for r in result["memberships"]}),
        countries_with_memberships=len({r["country_code"] for r in result["memberships"]}),
        cells_with_memberships=sum(bool(c["selected_positions"]) for c in result["cells"]),
        missing_positions=sum(c["missing_positions"] or 0 for c in result["cells"]),
        unresolved_population_countries=[
            c["country_code"] for c in countries if c["quota_per_year_main"] is None
        ],
        missing_complete_annual_positions=sum(
            c["missing_complete_annual_positions"] or 0 for c in result["cells"]
        ),
        network_calls=0,
        paid_calls=0,
        classification_ready=False,
        lyrics_acquisition_ready=False,
        current_snapshots_used_as_annual=False,
        candidate_limit_exceeded=len({r["candidate_id"] for r in result["memberships"]}) > 30000,
        missing_display_identity_memberships=sum(
            not r.get("title") or not r.get("artist") for r in result["memberships"]
        ),
        archive_display_metadata_repairs=archive_repairs,
        additional_missing_display_metadata=sum(
            not r.get("title") or not r.get("artist")
            for r in result["memberships"]
            if r["country_code"] in markets
        ),
        unresolved_source_conflicts=len(adjudication),
        source_hashes=input_hashes,
    )
    manifest["output_hashes"] = {}
    for name in [
        "combined.jsonl",
        "ranked_titles.jsonl",
        "country_years.jsonl",
        "countries.json",
        "source_coverage.json",
        "new_market_rankings.parquet",
        "historical_requests.jsonl",
        "adjudication_tasks.jsonl",
    ]:
        with (output / name).open("rb") as f:
            manifest["output_hashes"][name] = hashlib.file_digest(f, "sha256").hexdigest()
    dump(output / "manifest.json", manifest)
    return manifest, result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    manifest, result = build(args.output)
    # Durable local import supports inspection even without PostgreSQL access.
    engine = create_engine(f"sqlite:///{(args.output / 'global_annual.sqlite3').as_posix()}")
    try:
        local = persist(engine, manifest, result)
    finally:
        engine.dispose()
    dump(args.output / "local_import.json", local)
    if args.apply:
        engine = create_engine(Settings.load(ROOT).database_url)
        try:
            imported = persist(engine, manifest, result)
        finally:
            engine.dispose()
        dump(args.output / "postgres_import.json", imported)
    print(json.dumps(manifest, ensure_ascii=True, indent=2), flush=True)
