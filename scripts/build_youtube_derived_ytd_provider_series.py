"""Build a provisional YouTube year-to-date view-sum packet from weekly charts."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = ROOT / "data/raw/zenodo-23645386-youtube-audit-20261117"
DEFAULT_COVERAGE = ROOT / "data/derived/annual_revision/global-rescan-2018-2026-20261111/source_coverage.json"
DEFAULT_CAPTURE_MANIFEST = DEFAULT_SOURCE_DIR / "capture-manifest-additional-years-20261117-v1.json"
DEFAULT_OUTPUT = ROOT / "data/derived/annual_revision/provider_series/youtube-weekly-derived-ytd-20261117-01"

DATASET_DOI = "10.5281/zenodo.23645386"
ZENODO_RECORD_URL = "https://zenodo.org/records/23645386"
YOUTUBE_METHOD_URL = "https://support.google.com/youtube/answer/9014376?hl=en"
PROVIDER_CODE = "YOUTUBE"
PROVIDER_NAME = "YouTube Charts"
YEAR = 2026
CUTOFF = date(2026, 10, 15)
CANDIDATE_LIMIT = 500


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def md5_file(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def normalized_tiebreak(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def integral_source_value(value: str, *, field: str) -> int:
    try:
        number = Decimal(value)
    except (InvalidOperation, TypeError) as exc:
        raise ValueError(f"not a numeric source {field}: {value!r}") from exc
    if not number.is_finite() or number != number.to_integral_value():
        raise ValueError(f"source {field} is not a finite integer: {value!r}")
    return int(number)


def expected_thursdays(start: date, end: date) -> list[str]:
    day = start
    while day.weekday() != 3:
        day += timedelta(days=1)
    weeks = []
    while day <= end:
        weeks.append(day.isoformat())
        day += timedelta(days=7)
    return weeks


def source_artifact(path: Path, *, role: str, url: str | None = None) -> dict[str, Any]:
    artifact = {
        "local_path": path.relative_to(ROOT).as_posix(),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "role": role,
    }
    if url:
        artifact["url"] = url
    return artifact


def read_weekly_rows(path: Path, markets: set[str], weeks: set[str]) -> dict[tuple[str, str], list[dict[str, str]]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        required = {"cc", "week_end", "rank", "views", "key", "title", "artists"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"unexpected columns in {path.name}: {reader.fieldnames}")
        for row in reader:
            market = (row.get("cc") or "").upper()
            if market not in markets:
                continue
            week_end = row.get("week_end") or ""
            if week_end not in weeks:
                raise ValueError(f"unexpected source week for {market}: {week_end!r}")
            grouped[(market, week_end)].append(row)
    return grouped


def eligible_coverage_rows(coverage: list[dict[str, Any]], weeks: list[str]) -> list[dict[str, Any]]:
    eligible = []
    for row in coverage:
        if row.get("provider") != "ZENODO_23645386_YOUTUBE" or int(row.get("year") or 0) != YEAR:
            continue
        if row.get("coverage_status") != "COMPLETE":
            continue
        if int(row.get("expected_periods") or 0) != len(weeks):
            continue
        if int(row.get("collected_periods") or 0) != len(weeks):
            continue
        if any(int(row.get(field) or 0) for field in ("invalid_items", "conflicting_items", "duplicate_observations")):
            continue
        if (row.get("observed_start"), row.get("observed_end")) != (weeks[0], weeks[-1]):
            continue
        eligible.append(row)
    return sorted(eligible, key=lambda row: str(row["country_code"]).upper())


def build_market(
    *,
    market: str,
    coverage_row: dict[str, Any],
    expected_weeks: list[str],
    weekly_rows: dict[tuple[str, str], list[dict[str, str]]],
    source_path: Path,
    source_relpath: str,
    source_sha256: str,
    source_asset_url: str,
    source_retrieved_at: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    observed_weeks = {week for (code, week) in weekly_rows if code == market}
    if observed_weeks != set(expected_weeks):
        raise ValueError(
            f"{market} 2026 YTD calendar mismatch: "
            f"missing={sorted(set(expected_weeks) - observed_weeks)}, "
            f"unexpected={sorted(observed_weeks - set(expected_weeks))}"
        )

    totals: dict[str, dict[str, Any]] = {}
    metadata_variants: dict[str, set[tuple[str, str]]] = defaultdict(set)
    metadata_first: dict[str, tuple[str, str]] = {}
    weekly_rank_anomalies: list[dict[str, Any]] = []
    weekly_sizes: dict[str, int] = {}
    blank_title_observations = 0
    blank_artist_observations = 0

    for week_end in expected_weeks:
        rows = weekly_rows[(market, week_end)]
        weekly_sizes[week_end] = len(rows)
        if len(rows) < 100:
            raise ValueError(f"{market} {week_end} has only {len(rows)} weekly rows")

        seen_keys: set[str] = set()
        ranks: list[int] = []
        for row in rows:
            native_key = (row.get("key") or "").strip()
            if not native_key or native_key == "T:":
                raise ValueError(f"unresolved native chart key in {market} {week_end}: {native_key!r}")
            if native_key in seen_keys:
                raise ValueError(f"duplicate weekly native key {native_key} in {market} {week_end}")
            seen_keys.add(native_key)

            rank = integral_source_value(row.get("rank", ""), field="rank")
            views = integral_source_value(row.get("views", ""), field="views")
            if rank < 1 or views < 0:
                raise ValueError(f"invalid rank/views in {market} {week_end}: {row}")
            ranks.append(rank)

            title = row.get("title") or ""
            artist = row.get("artists") or ""
            blank_title_observations += not bool(title.strip())
            blank_artist_observations += not bool(artist.strip())
            metadata_variants[native_key].add((title, artist))
            metadata_first.setdefault(native_key, (title, artist))
            if native_key not in totals:
                totals[native_key] = {
                    "title": title,
                    "artist": artist,
                    "metric_value": 0,
                    "native_song_id": native_key,
                }
            totals[native_key]["metric_value"] += views

        rank_counts = Counter(ranks)
        repeated_ranks = sorted(rank for rank, count in rank_counts.items() if count > 1)
        missing_ranks = sorted(set(range(1, max(ranks) + 1)) - set(ranks))
        ranks_over_100 = sorted(rank for rank in set(ranks) if rank > 100)
        if len(rows) != 100 or repeated_ranks or missing_ranks or ranks_over_100:
            weekly_rank_anomalies.append(
                {
                    "week_end": week_end,
                    "row_count": len(rows),
                    "repeated_published_ranks": repeated_ranks,
                    "missing_rank_values": missing_ranks,
                    "rank_values_over_100": ranks_over_100,
                }
            )

    varied_keys = {key: values for key, values in metadata_variants.items() if len(values) > 1}
    if varied_keys:
        raise ValueError(f"source metadata varies for native keys in {market}: {list(varied_keys)[:5]}")
    if len(totals) < CANDIDATE_LIMIT:
        raise ValueError(f"only {len(totals)} unique native keys for {market} 2026 YTD")

    ranked = sorted(
        totals.values(),
        key=lambda item: (
            -item["metric_value"],
            normalized_tiebreak(item["title"]),
            normalized_tiebreak(item["artist"]),
            item["native_song_id"],
        ),
    )
    selected = ranked[:CANDIDATE_LIMIT]
    series_id = f"YOUTUBE_TOP_SONGS_DERIVED_YTD_2026_{market}"
    period_label = f"YouTube weekly Top Songs year-to-date view-sum through {expected_weeks[-1]} ({market}); derived, not published"
    ranking_basis = (
        f"Sum weekly YouTube Top Songs views by native chart key across the {len(expected_weeks)} "
        f"Thursday-ending charts from {expected_weeks[0]} through {expected_weeks[-1]}; sort by sum descending, "
        "then NFKC-normalized/case-folded title, artist credit, and native key. This is a year-to-date "
        "project derivation, not a completed annual ranking or a YouTube-published year-end chart."
    )
    ranking_rows = []
    for position, item in enumerate(selected, 1):
        ranking_rows.append(
            {
                "series_id": series_id,
                "provider_code": PROVIDER_CODE,
                "provider_name": PROVIDER_NAME,
                "chart_family": "Top Songs year-to-date view-sum (derived)",
                "chart_category": "derived_ytd_view_sum",
                "publisher_country_code": "US",
                "chart_market_code": market,
                "reporting_year": YEAR,
                "period_label": period_label,
                "period_start": expected_weeks[0],
                "period_end": expected_weeks[-1],
                "position": position,
                "published_rank": f"derived:{position}",
                "rank_kind": "derived_rank_not_publisher_published",
                "title": item["title"],
                "artist_credit": item["artist"],
                "native_id_namespace": "youtube_chart_key",
                "native_song_id": item["native_song_id"],
                "native_metric": "sum of weekly YouTube Top Songs views through 2026-10-15",
                "score": item["metric_value"],
                "source_url": ZENODO_RECORD_URL,
                "source_asset_url": source_asset_url,
                "source_artifact": source_relpath,
                "source_sha256": source_sha256,
                "source_retrieved_at_utc": source_retrieved_at,
                "ranking_basis": ranking_basis,
                "transcription_method": "recomputed_from_captured_weekly_top_songs_csv",
                "evidence_status": "derived_from_complete_primary_weekly_chart_source_through_cutoff",
                "merged_into_150k_spotify_youtube_selection": False,
            }
        )

    score_positions: dict[int, list[int]] = defaultdict(list)
    for position, item in enumerate(selected, 1):
        score_positions[item["metric_value"]].append(position)
    tie_groups = [
        {"sum_weekly_views": score, "derived_positions": positions}
        for score, positions in sorted(score_positions.items(), reverse=True)
        if len(positions) > 1
    ]

    series_manifest = {
        "series_id": series_id,
        "chart_category": "derived_ytd_view_sum",
        "reported_depth": None,
        "observed_ranked_entries": len(ranking_rows),
        "positions": list(range(1, len(ranking_rows) + 1)),
        "ties_or_gaps_as_published": [],
        "ranking_file": "rankings.jsonl",
        "ranking_basis": ranking_basis,
        "score_values_published": False,
        "period_label": period_label,
        "period_start": expected_weeks[0],
        "period_end": expected_weeks[-1],
        "source_url": ZENODO_RECORD_URL,
        "source_asset_url": source_asset_url,
        "expected_week_ends": expected_weeks,
        "source_coverage_status": coverage_row.get("coverage_status"),
        "source_coverage_periods": {
            "expected": coverage_row.get("expected_periods"),
            "collected": coverage_row.get("collected_periods"),
            "observed_start": coverage_row.get("observed_start"),
            "observed_end": coverage_row.get("observed_end"),
        },
        "weekly_chart_rows": sum(weekly_sizes.values()),
        "weekly_chart_rows_min": min(weekly_sizes.values()),
        "weekly_chart_rows_max": max(weekly_sizes.values()),
        "metadata_gaps": {
            "blank_title_source_observations": blank_title_observations,
            "blank_artist_source_observations": blank_artist_observations,
            "top500_blank_title_rows": sum(not metadata_first[item["native_song_id"]][0].strip() for item in selected),
            "top500_blank_artist_rows": sum(not metadata_first[item["native_song_id"]][1].strip() for item in selected),
            "blank source credits are preserved as blank; no title or artist is inferred": True,
        },
        "native_key_metadata_variant_count": len(varied_keys),
        "derived_view_sum_tie_groups_in_top500": tie_groups,
        "weekly_published_rank_anomalies": weekly_rank_anomalies,
        "status": "provisional_ytd_derived_from_complete_weekly_source",
        "annual_completeness": "incomplete_calendar_year_through_2026-10-15",
        "recovery_note": "Do not describe this as a final 2026 annual chart; later weeks can change the ranking.",
    }
    audit = {
        "series_id": series_id,
        "market": market,
        "source_week_count": len(expected_weeks),
        "source_rows": sum(weekly_sizes.values()),
        "unique_native_keys": len(totals),
        "duplicate_key_weeks": 0,
        "blank_or_unresolved_native_keys": 0,
        "invalid_rank_or_view_values": 0,
        "source_metadata_variants": 0,
        "weekly_rank_anomaly_count": len(weekly_rank_anomalies),
        "top500_blank_title_rows": series_manifest["metadata_gaps"]["top500_blank_title_rows"],
        "top500_blank_artist_rows": series_manifest["metadata_gaps"]["top500_blank_artist_rows"],
        "ranked_rows": len(ranking_rows),
    }
    return ranking_rows, {"series": series_manifest, "audit": audit}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--coverage", type=Path, default=DEFAULT_COVERAGE)
    parser.add_argument("--capture-manifest", type=Path, default=DEFAULT_CAPTURE_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    source_dir = args.source_dir if args.source_dir.is_absolute() else ROOT / args.source_dir
    coverage_path = args.coverage if args.coverage.is_absolute() else ROOT / args.coverage
    capture_path = args.capture_manifest if args.capture_manifest.is_absolute() else ROOT / args.capture_manifest
    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing packet: {output_dir}")

    source_path = source_dir / f"youtube_top100_positions_{YEAR}.csv.gz"
    capture = read_json(capture_path)
    capture_entry = next(
        (entry for entry in capture["files"] if entry.get("file_name") == source_path.name),
        None,
    )
    if capture_entry is None:
        raise ValueError(f"capture manifest does not contain {source_path.name}")
    source_sha256 = sha256_file(source_path)
    if md5_file(source_path) != capture_entry["expected_md5"]:
        raise ValueError("source MD5 does not match the Zenodo record metadata")
    if source_path.stat().st_size != capture_entry["expected_size_bytes"]:
        raise ValueError("source byte length does not match the Zenodo record metadata")
    if source_sha256 != capture_entry["sha256"]:
        raise ValueError("source SHA-256 does not match the local capture manifest")

    expected_weeks = expected_thursdays(date(YEAR, 1, 1), CUTOFF)
    coverage = read_json(coverage_path)
    if not isinstance(coverage, list):
        raise ValueError("source coverage must be a JSON list")
    targets = eligible_coverage_rows(coverage, expected_weeks)
    if len(targets) != 8:
        raise ValueError(f"expected 8 clean 2026 YTD coverage cells; found {len(targets)}")
    markets = {str(row["country_code"]).upper() for row in targets}
    grouped = read_weekly_rows(source_path, markets, set(expected_weeks))
    source_relpath = source_path.relative_to(ROOT).as_posix()
    source_asset_url = capture_entry["dataset_file_url"]
    all_rows: list[dict[str, Any]] = []
    series_audits = []
    for coverage_row in targets:
        market = str(coverage_row["country_code"]).upper()
        rows, audit = build_market(
            market=market,
            coverage_row=coverage_row,
            expected_weeks=expected_weeks,
            weekly_rows=grouped,
            source_path=source_path,
            source_relpath=source_relpath,
            source_sha256=source_sha256,
            source_asset_url=source_asset_url,
            source_retrieved_at=capture_entry["retrieved_at_utc"],
        )
        all_rows.extend(rows)
        series_audits.append(audit)

    ranking_bytes = "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
        for row in all_rows
    ).encode("utf-8")
    ranking_sha = hashlib.sha256(ranking_bytes).hexdigest()
    capture_sha = sha256_file(capture_path)
    readme_path = source_dir / "README.md"
    coverage_sha = sha256_file(coverage_path)
    ranking_basis = (
        "For each eligible market, sum the archived weekly view counts by native YouTube chart key "
        "over the 42 observed Thursday-ending charts from 2026-01-01 through 2026-10-15; sort by sum "
        "descending, then NFKC-normalized/case-folded title, artist credit, and native key. This is a "
        "project-derived year-to-date ranking, not a completed annual chart published by YouTube."
    )
    manifest = {
        "schema_version": "youtube-derived-ytd-series-v1",
        "provider_code": PROVIDER_CODE,
        "provider_name": PROVIDER_NAME,
        "publisher_country_code": "US",
        "publisher_jurisdiction_basis": "YouTube's official terms identify Google LLC as the YouTube service provider; the chart market is stored separately per series.",
        "chart_family": "Top Songs year-to-date view-sum (derived)",
        "chart_category": "derived_ytd_view_sum",
        "source_type": "derived_ranking_from_archived_primary_weekly_charts",
        "source_dataset_doi": DATASET_DOI,
        "source_dataset_version": "1.0.1",
        "source_dataset_license": "CC BY 4.0",
        "source_url": ZENODO_RECORD_URL,
        "provider_methodology_url": YOUTUBE_METHOD_URL,
        "source_capture_manifest": capture_path.relative_to(ROOT).as_posix(),
        "source_capture_manifest_sha256": capture_sha,
        "ranking_derivation": ranking_basis,
        "annual_chart_status": "Provisional 2026 year-to-date project derivation through 2026-10-15; not a completed or publisher-issued annual ranking.",
        "publisher_reported_annual_depth": None,
        "project_candidate_cap": CANDIDATE_LIMIT,
        "ranking_sha256": ranking_sha,
        "ranked_entry_count": len(all_rows),
        "series": [entry["series"] for entry in series_audits],
        "source_artifacts": [
            source_artifact(readme_path, role="Zenodo dataset README", url=ZENODO_RECORD_URL),
            source_artifact(capture_path, role="versioned source capture metadata", url=capture["record_api"]),
            source_artifact(source_path, role="archived weekly YouTube Top Songs source rows", url=source_asset_url),
            {
                "local_path": coverage_path.relative_to(ROOT).as_posix(),
                "sha256": coverage_sha,
                "bytes": coverage_path.stat().st_size,
                "role": "project source-coverage ledger used to select complete YTD cells",
            },
        ],
        "selection_policy": "Keep these YTD ranks as separate derived YOUTUBE provider series. Do not merge their positions into the 150,000-position Spotify/YouTube core or present them as completed 2026 annual ranks.",
        "retrieved_at_utc": capture_entry["retrieved_at_utc"],
        "packet_generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "coverage_ledger_reconciliation": {
            "coverage_path": coverage_path.relative_to(ROOT).as_posix(),
            "coverage_sha256": coverage_sha,
            "eligible_clean_market_cells": len(targets),
            "expected_week_ends": expected_weeks,
            "independent_source_row_validation": True,
            "ranked_rows_per_market": CANDIDATE_LIMIT,
            "audit_by_market": [entry["audit"] for entry in series_audits],
        },
        "ranking_file": "rankings.jsonl",
    }

    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "rankings.jsonl").write_bytes(ranking_bytes)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output_dir": output_dir.relative_to(ROOT).as_posix(),
                "series": len(targets),
                "ranked_entries": len(all_rows),
                "ranking_sha256": ranking_sha,
                "manifest_sha256": sha256_file(output_dir / "manifest.json"),
                "markets": [str(row["country_code"]).upper() for row in targets],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
