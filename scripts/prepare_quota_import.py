"""Prepare quota-based import and lyric targets from audited local annual rankings.

No database writes, network, paid classification or legacy Top 80 replacement.
Rebuild annual ranks after collecting missing periods before rerunning this tool.
"""

import argparse
import csv
import hashlib
import json
from pathlib import Path

import polars as pl

from chart_observatory.ingestion.import_quotas import (
    load_quotas,
    recovery_targets,
    select_quota_candidates,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/derived/research_quality/import-quotas-20261030"


def prepare(source, output, *, start_year=2017, end_year=2026, metadata_only_overflow=False):
    quotas = load_quotas(source / "country_quotas.csv")
    with (source / "source_coverage.csv").open(encoding="utf-8-sig", newline="") as handle:
        coverage = list(csv.DictReader(handle))
    rankings = pl.read_parquet(source / "rankings.parquet").to_dicts()
    result = select_quota_candidates(rankings, coverage, quotas,
                                     years=range(start_year, end_year + 1))
    targets = recovery_targets(result["selections"])
    if len(targets) > 30000 and not metadata_only_overflow:
        raise ValueError("candidate union exceeds 30000; recalibrate before acquisition")
    output.mkdir(parents=True, exist_ok=False)
    for name, rows in {"selected": result["selections"], "coverage": result["coverage"],
                       "recovery-targets": targets}.items():
        with (output / f"{name}.jsonl").open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    source_hashes = {}
    for name in ("country_quotas.csv", "source_coverage.csv", "rankings.parquet"):
        with (source / name).open("rb") as handle:
            source_hashes[name] = hashlib.file_digest(handle, "sha256").hexdigest()
    manifest = dict(
        protocol="country-year-quotas-20261030-v1", markets=len(quotas),
        cells=len(result["coverage"]), selected_memberships=len(result["selections"]),
        candidate_identities=len(targets), budget_ceiling_usd=150,
        paid_calls=0, database_writes=0, classification_ready=False,
        classification_blockers=["database and expense reconciliation", "recording identity",
                                 "text integrity", "complete protocol signature", "pilot"],
        source_hashes=source_hashes,
        years=[start_year, end_year], candidate_limit_exceeded=len(targets) > 30000,
        acquisition_ready=len(targets) <= 30000,
    )
    manifest["output_hashes"] = {}
    for name in ("selected.jsonl", "coverage.jsonl", "recovery-targets.jsonl"):
        with (output / name).open("rb") as handle:
            manifest["output_hashes"][name] = hashlib.file_digest(handle, "sha256").hexdigest()
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--apply", action="store_true",
                        help="Persist a separate immutable snapshot in the configured database")
    parser.add_argument("--prepared", action="store_true",
                        help="Reuse and verify an existing output directory before persistence")
    parser.add_argument("--start-year", type=int, choices=range(2017, 2027), default=2017)
    parser.add_argument("--end-year", type=int, choices=range(2017, 2027), default=2026)
    parser.add_argument("--metadata-only-overflow", action="store_true",
                        help="Allow metadata above 30000; keep lyric acquisition blocked")
    args = parser.parse_args()
    if args.prepared:
        manifest = json.loads((args.output / "manifest.json").read_text(encoding="utf-8"))
        for name, expected in manifest["source_hashes"].items():
            with (args.source / name).open("rb") as handle:
                if hashlib.file_digest(handle, "sha256").hexdigest() != expected:
                    raise ValueError("prepared source changed; build a fresh snapshot")
        for name, expected in manifest["output_hashes"].items():
            with (args.output / name).open("rb") as handle:
                if hashlib.file_digest(handle, "sha256").hexdigest() != expected:
                    raise ValueError("prepared output changed; build a fresh snapshot")
    else:
        if args.start_year > args.end_year:
            parser.error("start-year cannot exceed end-year")
        manifest = prepare(
            args.source, args.output, start_year=args.start_year, end_year=args.end_year,
            metadata_only_overflow=args.metadata_only_overflow,
        )
    if args.apply:
        from sqlalchemy import create_engine

        from chart_observatory.config import Settings
        from chart_observatory.ingestion.quota_repository import persist_snapshot

        with (args.output / "selected.jsonl").open(encoding="utf-8") as handle:
            rows = [json.loads(line) for line in handle if line.strip()]
        engine = create_engine(Settings.load(ROOT).database_url)
        try:
            persisted = persist_snapshot(engine, manifest, rows)
        finally:
            engine.dispose()
        print(json.dumps(persisted))
    print(json.dumps(manifest))
