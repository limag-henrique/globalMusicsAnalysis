"""Audit lyric insertions without modifying the append-only JSONL output."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from chart_observatory.lyrics.lyrics_backfill import (
    _load_tracks,
    is_valid_lyrics_record,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_TRACKS = _PROJECT_ROOT / "data" / "derived" / "track_master.parquet"
_DEFAULT_JSONL = _PROJECT_ROOT / "data" / "derived" / "lyrics" / "gemini_annotations.jsonl"
_DEFAULT_REPORT = _PROJECT_ROOT / "data" / "derived" / "lyrics" / "lyrics_audit.csv"


@dataclass(frozen=True)
class AuditSummary:
    catalog_tracks: int
    valid_found: int
    pending: int
    valid_rows: int
    malformed_lines: int
    duplicate_ids: int
    orphan_valid: int
    status_counts: dict[str, int]


@dataclass
class _ObservedSong:
    rows: int = 0
    valid_rows: int = 0
    invalid_rows: int = 0
    valid_source: str = ""
    status_counts: Counter[str] = field(default_factory=Counter)


def _read_output(output_path: Path) -> tuple[dict[str, _ObservedSong], int, Counter[str]]:
    observed: dict[str, _ObservedSong] = defaultdict(_ObservedSong)
    malformed_lines = 0
    status_counts: Counter[str] = Counter()
    if not output_path.exists():
        return {}, 0, status_counts

    with output_path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                item: Any = json.loads(line)
            except json.JSONDecodeError:
                malformed_lines += 1
                continue
            if not isinstance(item, dict):
                malformed_lines += 1
                continue
            song_id = str(item.get("song_id") or "").strip()
            if not song_id:
                malformed_lines += 1
                continue

            status = str(item.get("lyrics_status") or "UNKNOWN").upper()
            status_counts[status] += 1
            entry = observed[song_id]
            entry.rows += 1
            entry.status_counts[status] += 1
            if is_valid_lyrics_record(item):
                entry.valid_rows += 1
                if not entry.valid_source:
                    entry.valid_source = str(item["lyrics_source"]).upper()
            else:
                entry.invalid_rows += 1

    return dict(observed), malformed_lines, status_counts


def analyze_lyrics_output(
    catalog_path: Path,
    output_path: Path,
    report_path: Path,
    include_all: bool = True,
) -> AuditSummary:
    """Classify catalog songs and write an auditable CSV report."""
    observed, malformed_lines, status_counts = _read_output(output_path)
    tracks = _load_tracks(
        tracks_path=catalog_path,
        include_all=include_all,
        completed_ids=set(),
        completed_keys=set(),
    )
    catalog_ids = {track["song_id"] for track in tracks}
    report_path.parent.mkdir(parents=True, exist_ok=True)

    valid_found = 0
    pending = 0
    valid_rows = 0
    with report_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "song_id",
                "title",
                "artist",
                "classification",
                "valid_source",
                "valid_row_count",
                "invalid_row_count",
                "observed_statuses",
            ],
        )
        writer.writeheader()
        for track in tracks:
            entry = observed.get(track["song_id"], _ObservedSong())
            if entry.valid_rows:
                classification = "FOUND_VALID"
                valid_found += 1
                valid_rows += entry.valid_rows
            else:
                classification = "PENDING_RETRY"
                pending += 1
            writer.writerow(
                {
                    "song_id": track["song_id"],
                    "title": track["title"],
                    "artist": track["artist"],
                    "classification": classification,
                    "valid_source": entry.valid_source,
                    "valid_row_count": entry.valid_rows,
                    "invalid_row_count": entry.invalid_rows,
                    "observed_statuses": ";".join(
                        f"{status}:{count}"
                        for status, count in sorted(entry.status_counts.items())
                    ),
                }
            )

    duplicate_ids = sum(entry.rows > 1 for entry in observed.values())
    orphan_valid = sum(
        entry.valid_rows
        for song_id, entry in observed.items()
        if song_id not in catalog_ids
    )
    return AuditSummary(
        catalog_tracks=len(tracks),
        valid_found=valid_found,
        pending=pending,
        valid_rows=valid_rows,
        malformed_lines=malformed_lines,
        duplicate_ids=duplicate_ids,
        orphan_valid=orphan_valid,
        status_counts=dict(status_counts),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit lyrics inserted from approved sources.")
    parser.add_argument("--catalog", type=Path, default=_DEFAULT_TRACKS)
    parser.add_argument("--output", type=Path, default=_DEFAULT_JSONL)
    parser.add_argument("--report", type=Path, default=_DEFAULT_REPORT)
    parser.add_argument("--master-only", action="store_false", dest="include_all")
    args = parser.parse_args()

    summary = analyze_lyrics_output(
        catalog_path=args.catalog,
        output_path=args.output,
        report_path=args.report,
        include_all=args.include_all,
    )
    print(f"Catalog tracks: {summary.catalog_tracks}")
    print(f"Valid lyric insertions: {summary.valid_found} ({summary.valid_rows} rows)")
    print(f"Pending retry: {summary.pending}")
    print(f"Duplicate IDs: {summary.duplicate_ids}")
    print(f"Malformed lines: {summary.malformed_lines}")
    print(f"Orphan valid rows: {summary.orphan_valid}")
    print(f"Report: {args.report}")


if __name__ == "__main__":
    main()
