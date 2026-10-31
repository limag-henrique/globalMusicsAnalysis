"""Resolve missing display metadata only through exact native IDs in local sources."""

import json
import os
from collections import defaultdict
from pathlib import Path

os.environ.setdefault("POLARS_MAX_THREADS", "2")
import polars as pl

from chart_observatory.lyrics.quota_acquisition import identity

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/derived/annual_revision/audited-calendars-2018-2026-20261031"


def enrich():
    rows = [
        json.loads(line)
        for line in (BASE / "combined.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    wanted = {
        r["candidate_id"].removeprefix("SPOTIFY:")
        for r in rows
        if r["candidate_id"].startswith("SPOTIFY:")
        and (not r.get("title") or not r.get("artist") or r.get("original_display_metadata"))
    }
    matches = defaultdict(list)
    for name in ("mgd", "kaggle_spotify"):
        path = ROOT / f"data/normalized/{name}_observations.parquet"
        found = (
            pl.scan_parquet(path)
            .select(
                pl.col("native_id")
                .str.extract(r"([A-Za-z0-9]{22})(?:\?.*)?$", 1)
                .alias("native_id"),
                pl.col("track_title").alias("title"),
                pl.col("artist"),
            )
            .filter(pl.col("native_id").is_in(sorted(wanted)))
            .filter(
                pl.col("title").is_not_null()
                & (pl.col("title").str.strip_chars() != "")
                & pl.col("artist").is_not_null()
                & (pl.col("artist").str.strip_chars() != "")
            )
            .unique()
            .collect(engine="streaming")
        )
        for row in found.to_dicts():
            matches[row["native_id"]].append({**row, "source_artifact": str(path)})
    previous_path = BASE / "metadata-enrichment.json"
    previous = (
        json.loads(previous_path.read_text(encoding="utf-8")) if previous_path.exists() else {}
    )
    resolved, ambiguous = dict(previous.get("resolved", {})), {}
    for native, values in matches.items():
        signatures = {(identity(r["title"]), identity(r["artist"])) for r in values}
        if len(signatures) == 1:
            resolved["SPOTIFY:" + native] = dict(
                title=values[0]["title"],
                artist=values[0]["artist"],
                basis="exact_native_id_local_source",
                evidence=values,
                recording_and_text_validation=False,
            )
        else:
            ambiguous["SPOTIFY:" + native] = values
            resolved.pop("SPOTIFY:" + native, None)
    result = dict(
        resolved=resolved,
        ambiguous=ambiguous,
        unresolved=sorted(
            "SPOTIFY:" + value for value in wanted if "SPOTIFY:" + value not in resolved
        ),
    )
    (BASE / "metadata-enrichment.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return dict(
        requested=len(wanted),
        resolved=len(resolved),
        ambiguous=len(ambiguous),
        unresolved=len(result["unresolved"]),
    )


if __name__ == "__main__":
    print(json.dumps(enrich()))
