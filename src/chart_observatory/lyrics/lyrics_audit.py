"""Audit lyric insertions without modifying the append-only JSONL output."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq  # type: ignore[import-untyped]

from chart_observatory.lyrics.lyrics_backfill import (
    _load_tracks,
    is_valid_lyrics_record,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_TRACKS = _PROJECT_ROOT / "data" / "derived" / "track_master.parquet"
_DEFAULT_JSONL = _PROJECT_ROOT / "data" / "derived" / "lyrics" / "gemini_annotations.jsonl"
_DEFAULT_REPORT = _PROJECT_ROOT / "data" / "derived" / "lyrics" / "lyrics_audit.csv"
_DEFAULT_COUNTRY_REPORT = _PROJECT_ROOT / "data" / "derived" / "lyrics" / "lyrics_by_country.csv"


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


@dataclass(frozen=True)
class CountryAuditSummary:
    """Country-level retrieval outcomes computed from unique track observations."""

    countries: int
    total_tracks: int
    found: int
    failed: int
    not_attempted: int
    rows: list[dict[str, object]]


@dataclass
class _ObservedSong:
    rows: int = 0
    valid_rows: int = 0
    invalid_rows: int = 0
    valid_source: str = ""
    status_counts: Counter[str] = field(default_factory=Counter)


def _track_id_from_native_id(native_id: object) -> str:
    value = str(native_id or "").strip().rstrip("/")
    if value.startswith("spotify:track:"):
        return value.removeprefix("spotify:track:").split("?", 1)[0]
    return value.rsplit("/", 1)[-1].split("?", 1)[0]


def _load_lyrics_outcomes(output_path: Path) -> dict[str, str]:
    """Load one best outcome per song without retaining lyric text in memory."""
    outcomes: dict[str, str] = {}
    if not output_path.exists():
        return outcomes
    for line in output_path.open(encoding="utf-8"):
        if not line.strip():
            continue
        try:
            item: Any = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict):
            continue
        song_id = str(item.get("song_id") or "").strip()
        if not song_id:
            continue
        if is_valid_lyrics_record(item):
            outcomes[song_id] = "FOUND"
        elif str(item.get("lyrics_status") or "").upper() in {
            "FOUND",
            "MISSING",
            "PROVIDER_ERROR",
        }:
            outcomes.setdefault(song_id, "FAILED")
    return outcomes


def analyze_lyrics_by_country(
    observations_path: Path,
    output_path: Path,
    report_path: Path,
    batch_size: int = 50_000,
) -> CountryAuditSummary:
    """Write a memory-bounded country error report.

    The observations parquet is read in Arrow batches. Unique country/track pairs
    are kept in a temporary SQLite database, so a large source cannot expand the
    Python process proportionally to the number of chart observations.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    outcomes = _load_lyrics_outcomes(output_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "country_code",
        "total_tracks",
        "found",
        "failed",
        "not_attempted",
        "error_rate_attempted_pct",
        "share_of_project_tracks_pct",
        "share_of_all_errors_pct",
    ]

    with tempfile.TemporaryDirectory(prefix="lyrics-country-audit-") as temp_dir:
        database_path = Path(temp_dir) / "country_tracks.sqlite3"
        connection = sqlite3.connect(database_path)
        try:
            connection.execute("PRAGMA journal_mode=OFF")
            connection.execute("PRAGMA synchronous=OFF")
            connection.execute(
                "CREATE TABLE tracks (country_code TEXT NOT NULL, song_id TEXT NOT NULL, "
                "PRIMARY KEY (country_code, song_id))"
            )
            parquet_file = pq.ParquetFile(observations_path)
            names = set(parquet_file.schema_arrow.names)
            required = {"country_code", "native_id"}
            missing = sorted(required - names)
            if missing:
                raise ValueError(f"observations parquet is missing columns: {missing}")
            for batch in parquet_file.iter_batches(
                batch_size=batch_size,
                columns=["country_code", "native_id"],
            ):
                countries = batch.column(0).to_pylist()
                native_ids = batch.column(1).to_pylist()
                batch_rows = [
                    (str(country).strip().upper(), _track_id_from_native_id(native_id))
                    for country, native_id in zip(countries, native_ids, strict=True)
                    if str(country or "").strip() and _track_id_from_native_id(native_id)
                ]
                connection.executemany("INSERT OR IGNORE INTO tracks VALUES (?, ?)", batch_rows)
                connection.commit()

            connection.execute("CREATE TABLE outcomes (song_id TEXT PRIMARY KEY, outcome TEXT)")
            connection.executemany(
                "INSERT INTO outcomes VALUES (?, ?)", outcomes.items()
            )
            connection.commit()
            query = """
                SELECT
                    tracks.country_code,
                    COUNT(*) AS total_tracks,
                    COALESCE(SUM(outcomes.outcome = 'FOUND'), 0) AS found,
                    COALESCE(SUM(outcomes.outcome = 'FAILED'), 0) AS failed,
                    COALESCE(SUM(outcomes.outcome IS NULL), 0) AS not_attempted
                FROM tracks
                LEFT JOIN outcomes ON outcomes.song_id = tracks.song_id
                GROUP BY tracks.country_code
                ORDER BY tracks.country_code
            """
            raw_rows = connection.execute(query).fetchall()
        finally:
            connection.close()

    total_tracks = sum(int(row[1]) for row in raw_rows)
    found = sum(int(row[2]) for row in raw_rows)
    failed = sum(int(row[3]) for row in raw_rows)
    not_attempted = sum(int(row[4]) for row in raw_rows)
    report_rows: list[dict[str, object]] = []
    for country_code, total, country_found, country_failed, country_pending in raw_rows:
        attempted = int(country_found) + int(country_failed)
        report_rows.append(
            {
                "country_code": country_code,
                "total_tracks": int(total),
                "found": int(country_found),
                "failed": int(country_failed),
                "not_attempted": int(country_pending),
                "error_rate_attempted_pct": round(
                    int(country_failed) / attempted * 100, 2
                )
                if attempted
                else 0.0,
                "share_of_project_tracks_pct": round(int(total) / total_tracks * 100, 2)
                if total_tracks
                else 0.0,
                "share_of_all_errors_pct": round(int(country_failed) / failed * 100, 2)
                if failed
                else 0.0,
            }
        )

    with report_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(report_rows)
    return CountryAuditSummary(
        countries=len(report_rows),
        total_tracks=total_tracks,
        found=found,
        failed=failed,
        not_attempted=not_attempted,
        rows=report_rows,
    )


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
    parser.add_argument(
        "--country-observations",
        type=Path,
        help="Parquet with country_code/native_id for a memory-bounded country report",
    )
    parser.add_argument("--country-report", type=Path, default=_DEFAULT_COUNTRY_REPORT)
    parser.add_argument("--country-batch-size", type=int, default=50_000)
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
    if args.country_observations:
        country_summary = analyze_lyrics_by_country(
            observations_path=args.country_observations,
            output_path=args.output,
            report_path=args.country_report,
            batch_size=args.country_batch_size,
        )
        print(
            f"Country report: {country_summary.countries} countries, "
            f"{country_summary.total_tracks} unique country-track pairs, "
            f"{country_summary.failed} failed, {country_summary.not_attempted} not attempted"
        )
        print(f"Country report path: {args.country_report}")


if __name__ == "__main__":
    main()
