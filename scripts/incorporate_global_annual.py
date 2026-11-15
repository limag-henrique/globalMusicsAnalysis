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


def verify_zenodo_archive_inputs():
    """Verify local SHA sidecars and the checksums embedded in Zenodo record metadata."""
    record_path = RAW / "record.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    remote_files = {item["key"]: item for item in record.get("files", [])}
    checked = []
    targets = [
        RAW / f"{prefix}_positions_{year}.csv.gz"
        for year in range(2018, 2027)
        for prefix in ("spotify_top200", "youtube_top100")
    ]
    targets.append(RAW / "README.md")
    for path in targets:
        sidecar = path.with_name(path.name + ".sha256")
        if not path.is_file() or not sidecar.is_file():
            raise FileNotFoundError(f"Zenodo input or SHA-256 sidecar missing: {path.name}")
        expected_sha256 = sidecar.read_text(encoding="ascii").strip().split()[0].lower()
        if len(expected_sha256) != 64:
            raise ValueError(f"invalid SHA-256 sidecar: {sidecar.name}")
        with path.open("rb") as handle:
            actual_sha256 = hashlib.file_digest(handle, "sha256").hexdigest()
        if actual_sha256 != expected_sha256:
            raise ValueError(f"Zenodo SHA-256 sidecar mismatch: {path.name}")
        metadata = remote_files.get(path.name)
        if not metadata:
            raise ValueError(f"file absent from local Zenodo record metadata: {path.name}")
        if path.stat().st_size != metadata.get("size"):
            raise ValueError(f"Zenodo record size mismatch: {path.name}")
        with path.open("rb") as handle:
            actual_md5 = hashlib.file_digest(handle, "md5").hexdigest()
        if metadata.get("checksum") != f"md5:{actual_md5}":
            raise ValueError(f"Zenodo record checksum mismatch: {path.name}")
        checked.append(
            dict(
                file=path.name,
                sha256=actual_sha256,
                sidecar=sidecar.name,
                zenodo_record_md5=actual_md5,
                size=path.stat().st_size,
                sidecar_verified=True,
                record_metadata_checksum_verified=True,
            )
        )
    with record_path.open("rb") as handle:
        record_sha256 = hashlib.file_digest(handle, "sha256").hexdigest()
    with (RAW / "README.md").open("rb") as handle:
        readme_sha256 = hashlib.file_digest(handle, "sha256").hexdigest()
    return dict(
        record_id=record.get("id"),
        doi=record.get("doi"),
        title=record.get("metadata", {}).get("title"),
        record_json_sha256=record_sha256,
        readme_sha256=readme_sha256,
        checksum_method="local SHA-256 sidecars plus MD5/size from bundled Zenodo record metadata",
        record_metadata_independently_authenticated=False,
        scientifically_verified=False,
        checked_files=checked,
    )


def build(output, *, rebuild_all=False):
    """Build a versioned annual selection.

    ``rebuild_all`` is an exploratory rescan of every market with a declared
    quota. It never preserves legacy memberships and never marks the resulting
    positions scientifically verified; the normal build continues to preserve
    frozen memberships exactly as before.
    """
    if rebuild_all and output.exists() and any(output.iterdir()):
        raise FileExistsError("refusing to overwrite a non-empty exploratory selection")
    output.mkdir(parents=True, exist_ok=True)
    zenodo_provenance = verify_zenodo_archive_inputs()
    dump(output / "zenodo_provenance.json", zenodo_provenance)
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    countries = policy["countries"]
    assembly_countries = (
        [{**c, "legacy_frozen": False} for c in countries] if rebuild_all else countries
    )
    markets = {
        c["country_code"]
        for c in assembly_countries
        if c["quota_per_year_main"] is not None and not c["legacy_frozen"]
    }
    baseline = (
        []
        if rebuild_all
        else [
            json.loads(line)
            for line in (BASE / "combined.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    )
    rankings, coverage = [], []
    adjudication = []
    inputs = [POLICY, DAILY, RAW / "record.json", RAW / "README.md"]
    inputs.extend(
        RAW / f"{prefix}_positions_{year}.csv.gz.sha256"
        for year in range(2018, 2027)
        for prefix in ("spotify_top200", "youtube_top100")
    )
    if not rebuild_all:
        inputs.append(BASE / "combined.jsonl")
    implementation = [
        Path(__file__).resolve(),
        Path(annual_ranks.__code__.co_filename).resolve(),
        Path(assemble.__code__.co_filename).resolve(),
    ]
    implementation_hashes = {}
    for path in implementation:
        with path.open("rb") as f:
            implementation_hashes[str(path.relative_to(ROOT))] = hashlib.file_digest(
                f, "sha256"
            ).hexdigest()
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
                expected_depth=100 if platform == "YOUTUBE" else 200,
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
            expected_depth=200,
        )
        rankings, coverage = merge_sources(rankings, coverage, rows, cells)
    result = assemble(assembly_countries, baseline, rankings, coverage)
    # Keep the original policy metadata in the artifact. The temporary
    # legacy_frozen=False copies above only open an isolated recomputation path.
    result["countries"] = countries
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
    for path in implementation:
        with path.open("rb") as f:
            current_hash = hashlib.file_digest(f, "sha256").hexdigest()
        if current_hash != implementation_hashes[str(path.relative_to(ROOT))]:
            raise ValueError(f"implementation changed during build: {path}")
    membership_by_cell = {}
    for row in result["memberships"]:
        membership_by_cell.setdefault((row["country_code"], row["year"]), []).append(row)
    rankings_by_source_cell = {}
    for row in rankings:
        rankings_by_source_cell.setdefault(
            (row["country_code"], row["year"], row["platform"]), []
        ).append(row)
    tie_tasks = []
    for (country_code, year), rows in sorted(membership_by_cell.items()):
        quota = next(
            cell["quota"]
            for cell in result["cells"]
            if cell["country_code"] == country_code and cell["year"] == year
        )
        source_platform = rows[0]["platform"]
        ordered = sorted(
            rankings_by_source_cell.get((country_code, year, source_platform), []),
            key=lambda row: row["position"],
        )[: (quota or 0) + 1]
        for previous, current in zip(ordered, ordered[1:], strict=False):
            if previous.get("metric_value") == current.get("metric_value"):
                tie_tasks.append(
                    dict(
                        country_code=country_code,
                        year=year,
                        platform=current.get("platform"),
                        metric_value=current.get("metric_value"),
                        adjacent_positions=[previous["position"], current["position"]],
                        candidate_ids=[previous["candidate_id"], current["candidate_id"]],
                        status="ANNUAL_POSITION_TIE_REQUIRES_POLICY_REVIEW",
                        scientifically_verified=False,
                    )
                )
    jsonl(output / "position_tie_tasks.jsonl", tie_tasks)
    parent_manifest_hash = None
    parent_manifest_path = OUT / "manifest.json"
    if rebuild_all and parent_manifest_path.is_file():
        with parent_manifest_path.open("rb") as handle:
            parent_manifest_hash = hashlib.file_digest(handle, "sha256").hexdigest()
    manifest = dict(
        protocol="worldwide-annual-quotas-v1",
        selection_revision=("global-archive-rescan-v1" if rebuild_all else "legacy-preserving-v1"),
        parent_selection_manifest_sha256=parent_manifest_hash,
        scientifically_verified=False,
        position_tie_pairs_pending=len(tie_tasks),
        years=list(range(2018, 2027)),
        cutoff=CUTOFF.isoformat(),
        countries=len(countries),
        country_year_cells=len(result["cells"]),
        requested_positions=sum(c["quota"] or 0 for c in result["cells"]),
        preserved_legacy_memberships=len(baseline),
        exploratory_full_rebuild=rebuild_all,
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
        implementation_hashes=implementation_hashes,
        expected_source_depths={"YOUTUBE": 100, "SPOTIFY": 200},
        depth_policy="unique_native_tracks_per_period_with_rank_bounds-v2",
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
        "position_tie_tasks.jsonl",
        "zenodo_provenance.json",
    ]:
        with (output / name).open("rb") as f:
            manifest["output_hashes"][name] = hashlib.file_digest(f, "sha256").hexdigest()
    dump(output / "manifest.json", manifest)
    return manifest, result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument(
        "--rebuild-all",
        action="store_true",
        help="recompute all quota-defined markets in an isolated selection revision",
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    manifest, result = build(args.output, rebuild_all=args.rebuild_all)
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
