"""Build separate derived annual YouTube Top Songs series from a verified Zenodo archive.

The generated rankings are annual sums of weekly YouTube chart views. YouTube did not
publish these as year-end charts; the 500-position cap is a project extraction limit.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import unicodedata
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = Path("data/raw/zenodo-23645386-youtube-audit-20261117")
DEFAULT_COVERAGE = Path(
    "data/derived/annual_revision/global-rescan-2018-2026-20261111/source_coverage.json"
)
DEFAULT_RANKINGS = Path(
    "data/derived/annual_revision/global-rescan-2018-2026-20261111/new_market_rankings.parquet"
)
DEFAULT_CORE_SELECTION = Path(
    "data/derived/annual_revision/population-total-150k-2018-2026-20261116-v10-archives/combined.jsonl"
)
DEFAULT_OUTPUT = Path(
    "data/derived/annual_revision/provider_series/"
    "youtube-weekly-derived-annual-20261117-01"
)
ZENODO_RECORD_URL = "https://zenodo.org/records/23645386"
ZENODO_DOI_URL = "https://doi.org/10.5281/zenodo.23645386"
PROVIDER_CODE = "YOUTUBE"
PROVIDER_NAME = "YouTube Charts"
CHART_FAMILY = "Top Songs annual view-sum (derived)"
CHART_CATEGORY = "derived_annual_view_sum"
CANDIDATE_LIMIT = 500


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def expected_thursdays(year: int) -> list[str]:
    day = date(year, 1, 1)
    while day.weekday() != 3:
        day = date.fromordinal(day.toordinal() + 1)
    result = []
    while day.year == year:
        result.append(day.isoformat())
        day = date.fromordinal(day.toordinal() + 7)
    return result


def normalized_song_key(title: str, artist: str) -> tuple[str, str]:
    return tuple(
        " ".join(unicodedata.normalize("NFKC", value).casefold().split())
        for value in (title, artist)
    )


def integral_source_value(value: str) -> int:
    """Read integer metrics represented either as integers or integer-valued decimals."""
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"not a numeric source value: {value!r}") from exc
    if not number.is_finite() or number != number.to_integral_value():
        raise ValueError(f"source value is not an integer: {value!r}")
    return int(number)


def as_source_text(value: Any) -> str:
    """Preserve missing source text as blank rather than creating a replacement value."""
    if value is None or pd.isna(value):
        return ""
    return str(value)


def load_core_platforms(path: Path) -> dict[tuple[str, int], str]:
    platforms: dict[tuple[str, int], set[str]] = defaultdict(set)
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            cell = (str(row["country_code"]).upper(), int(row["year"]))
            platforms[cell].add(str(row["platform"]).upper())
    inconsistent = {cell: values for cell, values in platforms.items() if len(values) != 1}
    if inconsistent:
        raise ValueError(f"core selection has multiple platforms within cells: {inconsistent}")
    return {cell: next(iter(values)) for cell, values in platforms.items()}


def eligible_cells(
    coverage: list[dict[str, Any]],
    core_platforms: dict[tuple[str, int], str],
) -> list[dict[str, Any]]:
    eligible = []
    for row in coverage:
        if row.get("provider") != "ZENODO_23645386_YOUTUBE":
            continue
        year = int(row["year"])
        expected = expected_thursdays(year)
        if year < 2019 or year > 2025:
            continue
        if row.get("coverage_status") != "COMPLETE":
            continue
        if int(row.get("expected_periods") or 0) != len(expected):
            continue
        if int(row.get("collected_periods") or 0) != len(expected):
            continue
        if int(row.get("invalid_items") or 0) or int(row.get("conflicting_items") or 0):
            continue
        if int(row.get("duplicate_observations") or 0):
            continue
        if (row.get("observed_start"), row.get("observed_end")) != (
            expected[0],
            expected[-1],
        ):
            continue
        cell = (str(row["country_code"]).upper(), year)
        if core_platforms.get(cell) == "SPOTIFY":
            eligible.append({**row, "expected_week_ends": expected})
    return sorted(eligible, key=lambda item: (item["country_code"], item["year"]))


def read_year_rows(
    path: Path, year: int, target_markets: set[str]
) -> dict[tuple[str, str], list[dict[str, str]]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        required = {"cc", "week_end", "rank", "views", "key", "title", "artists"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"unexpected columns in {path.name}: {reader.fieldnames}")
        for row in reader:
            market = (row.get("cc") or "").upper()
            if market not in target_markets:
                continue
            week_end = row.get("week_end") or ""
            if len(week_end) != 10 or int(week_end[:4]) != year:
                continue
            grouped[(market, week_end)].append(row)
    return grouped


def build_cell(
    *,
    market: str,
    year: int,
    expected_weeks: list[str],
    coverage_row: dict[str, Any],
    weekly_rows: dict[tuple[str, str], list[dict[str, str]]],
    source_path: Path,
    source_sha256: str,
    source_asset_url: str,
    source_retrieved_at: str,
    core_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    week_set = {week for (code, week) in weekly_rows if code == market}
    if week_set != set(expected_weeks):
        raise ValueError(
            f"{market} {year} calendar mismatch: "
            f"missing={sorted(set(expected_weeks) - week_set)}, "
            f"unexpected={sorted(week_set - set(expected_weeks))}"
        )

    totals: dict[str, dict[str, Any]] = {}
    weekly_sizes: dict[str, int] = {}
    weekly_rank_anomalies = []
    blank_title_observations = 0
    blank_artist_observations = 0
    metadata_variants: dict[str, set[tuple[str, str]]] = defaultdict(set)

    for week_end in expected_weeks:
        rows = weekly_rows[(market, week_end)]
        weekly_sizes[week_end] = len(rows)
        if len(rows) < 100:
            raise ValueError(f"{market} {week_end} has only {len(rows)} weekly rows")
        seen_native_ids: set[str] = set()
        ranks: list[int] = []
        for row in rows:
            native_id = (row.get("key") or "").strip()
            if not native_id or native_id.startswith("web-derived:"):
                raise ValueError(f"missing native chart key in {market} {week_end}")
            if native_id in seen_native_ids:
                raise ValueError(f"duplicate weekly native key {native_id} in {market} {week_end}")
            seen_native_ids.add(native_id)
            try:
                rank = integral_source_value(row["rank"])
                views = integral_source_value(row["views"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid rank/views in {market} {week_end}: {row}") from exc
            if rank < 1 or views < 0:
                raise ValueError(f"negative or zero-invalid rank/views in {market} {week_end}")
            ranks.append(rank)
            title = row.get("title") or ""
            artist = row.get("artists") or ""
            blank_title_observations += not bool(title.strip())
            blank_artist_observations += not bool(artist.strip())
            metadata_variants[native_id].add((title, artist))
            if native_id not in totals:
                totals[native_id] = {
                    "title": title,
                    "artist": artist,
                    "metric_value": 0,
                    "native_song_id": native_id,
                }
            totals[native_id]["metric_value"] += views

        rank_counts = Counter(ranks)
        repeated_ranks = sorted(rank for rank, count in rank_counts.items() if count > 1)
        expected_ranks = set(range(1, max(ranks) + 1))
        missing_ranks = sorted(expected_ranks - set(ranks))
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

    if len(totals) < CANDIDATE_LIMIT:
        raise ValueError(f"only {len(totals)} unique songs for {market} {year}")
    all_ranked = sorted(
        totals.values(),
        key=lambda item: (
            -item["metric_value"],
            normalized_song_key(item["title"], item["artist"]),
            item["native_song_id"],
        ),
    )
    selected = all_ranked[:CANDIDATE_LIMIT]

    # Cross-check all five rank-bearing fields against the preserved rescan artifact.
    expected_core = sorted(core_rows, key=lambda item: int(item["position"]))
    if len(expected_core) != CANDIDATE_LIMIT:
        raise ValueError(f"rescan artifact has {len(expected_core)} candidates for {market} {year}")
    mismatches = []
    for position, (expected, actual) in enumerate(zip(expected_core, selected, strict=True), 1):
        actual_id = f"YOUTUBE:{actual['native_song_id']}"
        checks = {
            "position": (int(expected["position"]), position),
            "candidate_id": (str(expected["candidate_id"]), actual_id),
            "title": (as_source_text(expected.get("title")), actual["title"]),
            "artist": (as_source_text(expected.get("artist")), actual["artist"]),
            "metric_value": (int(expected["metric_value"]), actual["metric_value"]),
        }
        bad = {field: values for field, values in checks.items() if values[0] != values[1]}
        if bad:
            mismatches.append({"position": position, "fields": bad})
            if len(mismatches) >= 5:
                break
    if mismatches:
        raise ValueError(f"rescan reproduction mismatch for {market} {year}: {mismatches}")

    series_id = f"YOUTUBE_TOP_SONGS_DERIVED_ANNUAL_{market}_{year}"
    last_week_end = expected_weeks[-1]
    period_label = (
        f"YouTube weekly Top Songs view-sum ranking for {year} ({market}); derived, not published"
    )
    ranking_rows = []
    for position, item in enumerate(selected, 1):
        ranking_rows.append(
            {
                "series_id": series_id,
                "provider_code": PROVIDER_CODE,
                "provider_name": PROVIDER_NAME,
                "chart_family": CHART_FAMILY,
                "chart_category": CHART_CATEGORY,
                "publisher_country_code": "US",
                "chart_market_code": market,
                "reporting_year": year,
                "period_label": period_label,
                "period_start": None,
                "period_end": last_week_end,
                "position": position,
                "published_rank": f"derived:{position}",
                "rank_kind": "derived_rank_not_publisher_published",
                "title": item["title"],
                "artist_credit": item["artist"],
                "native_id_namespace": "youtube_chart_key_video_id",
                "native_song_id": item["native_song_id"],
                "native_metric": "sum of YouTube weekly Top Songs views",
                "score": item["metric_value"],
                "source_url": ZENODO_RECORD_URL,
                "source_asset_url": source_asset_url,
                "source_artifact": source_path.as_posix(),
                "source_sha256": source_sha256,
                "source_retrieved_at_utc": source_retrieved_at,
                "ranking_basis": (
                    "Computed by summing the archived weekly views for each native YouTube chart "
                    "key over every Thursday-ending chart whose week_end falls in the reporting "
                    "year; tie-breaks follow normalized NFKC case-folded title, artist credit, "
                    "then native key. This is not a publisher-issued annual chart."
                ),
                "transcription_method": "recomputed_from_captured_weekly_top_songs_csv",
                "evidence_status": "derived_from_complete_primary_weekly_chart_source",
                "merged_into_150k_spotify_youtube_selection": False,
            }
        )

    metric_positions: dict[int, list[int]] = defaultdict(list)
    for position, row in enumerate(selected, 1):
        metric_positions[row["metric_value"]].append(position)
    ties = [
        {"sum_weekly_views": metric, "derived_positions": positions}
        for metric, positions in sorted(metric_positions.items(), reverse=True)
        if len(positions) > 1
    ]
    metadata_conflict_keys = sorted(
        key for key, variants in metadata_variants.items() if len(variants) > 1
    )
    details = {
        "series_id": series_id,
        "country_code": market,
        "year": year,
        "core_selected_provider": "SPOTIFY",
        "source_provider": PROVIDER_CODE,
        "weekly_calendar_complete": True,
        "expected_week_end_count": len(expected_weeks),
        "expected_week_ends": expected_weeks,
        "weekly_chart_rows": sum(weekly_sizes.values()),
        "weekly_chart_rows_min": min(weekly_sizes.values()),
        "weekly_chart_rows_max": max(weekly_sizes.values()),
        "weekly_published_rank_anomalies": weekly_rank_anomalies,
        "unique_native_keys": len(totals),
        "duplicate_native_keys_within_week": 0,
        "invalid_or_missing_view_metrics": 0,
        "blank_title_source_observations": blank_title_observations,
        "blank_artist_source_observations": blank_artist_observations,
        "top500_blank_title_rows": sum(not row["title"].strip() for row in selected),
        "top500_blank_artist_rows": sum(not row["artist"].strip() for row in selected),
        "native_key_metadata_variant_count": len(metadata_conflict_keys),
        "native_key_metadata_variant_examples": metadata_conflict_keys[:10],
        "derived_view_sum_tie_groups_in_top500": ties,
        "observed_derived_positions": list(range(1, CANDIDATE_LIMIT + 1)),
        "publisher_reported_annual_depth": None,
        "project_candidate_cap": CANDIDATE_LIMIT,
        "exact_match_to_preserved_rescan_top500": True,
        "rescan_candidate_count": len(expected_core),
        "source_coverage_metadata_missing_observations": int(
            coverage_row.get("metadata_missing_observations") or 0
        ),
        "last_week_end": last_week_end,
        "source_sha256": source_sha256,
        "ranking_basis": "sum weekly chart views by native YouTube chart key",
    }
    series_manifest = {
        "series_id": series_id,
        "chart_category": CHART_CATEGORY,
        "reported_depth": None,
        "observed_ranked_entries": CANDIDATE_LIMIT,
        "positions": list(range(1, CANDIDATE_LIMIT + 1)),
        "ties_or_gaps_as_published": [],
        "status": "derived_from_complete_primary_weekly_chart_source",
        "ranking_file": "rankings.jsonl",
        "ranking_basis": (
            f"Sum weekly views across {len(expected_weeks)} complete Thursday-ending YouTube Top "
            f"Songs charts with week_end in {year}; project cap {CANDIDATE_LIMIT}. No official "
            "YouTube year-end chart depth or annual published ranks are asserted."
        ),
        "score_values_published": False,
        "period_label": period_label,
        "period_start": None,
        "period_end": last_week_end,
        "source_url": ZENODO_RECORD_URL,
        "source_asset_url": source_asset_url,
        "expected_week_ends": expected_weeks,
        "weekly_chart_rows": details["weekly_chart_rows"],
        "weekly_chart_rows_min": details["weekly_chart_rows_min"],
        "weekly_chart_rows_max": details["weekly_chart_rows_max"],
        "weekly_published_rank_anomalies": weekly_rank_anomalies,
        "metadata_gaps": {
            "blank_title_source_observations": blank_title_observations,
            "blank_artist_source_observations": blank_artist_observations,
            "top500_blank_title_rows": details["top500_blank_title_rows"],
            "top500_blank_artist_rows": details["top500_blank_artist_rows"],
            "blank source credits are preserved as blank; no title or artist is inferred": True,
        },
        "native_key_metadata_variant_count": len(metadata_conflict_keys),
        "derived_view_sum_tie_groups_in_top500": ties,
    }
    return ranking_rows, {"details": details, "series_manifest": series_manifest}


def source_artifact(path: Path, *, role: str, url: str | None = None) -> dict[str, Any]:
    absolute = path if path.is_absolute() else ROOT / path
    record: dict[str, Any] = {
        "local_path": path.as_posix(),
        "sha256": sha256_file(absolute),
        "bytes": absolute.stat().st_size,
        "role": role,
    }
    if url:
        record["url"] = url
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--coverage", type=Path, default=DEFAULT_COVERAGE)
    parser.add_argument("--candidate-rankings", type=Path, default=DEFAULT_RANKINGS)
    parser.add_argument("--core-selection", type=Path, default=DEFAULT_CORE_SELECTION)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    source_dir = args.source_dir if args.source_dir.is_absolute() else ROOT / args.source_dir
    coverage_path = args.coverage if args.coverage.is_absolute() else ROOT / args.coverage
    rankings_path = (
        args.candidate_rankings
        if args.candidate_rankings.is_absolute()
        else ROOT / args.candidate_rankings
    )
    core_path = args.core_selection if args.core_selection.is_absolute() else ROOT / args.core_selection
    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing packet: {output_dir}")

    capture_manifest_path = source_dir / "capture-manifest-annual-series-20261117-v2.json"
    original_capture_manifest_path = source_dir / "capture-manifest.json"
    coverage = read_json(coverage_path)
    if not isinstance(coverage, list):
        raise ValueError("source coverage must be a JSON list")
    capture_manifest = read_json(capture_manifest_path)
    original_capture = read_json(original_capture_manifest_path)
    if capture_manifest.get("dataset_doi") != "10.5281/zenodo.23645386":
        raise ValueError("unexpected source dataset DOI")

    readme_path = source_dir / "README.md"
    readme_expected = original_capture["files"]["README.md"]["expected_md5"]
    if md5_file(readme_path) != readme_expected:
        raise ValueError("Zenodo README checksum does not match captured record metadata")

    core_platforms = load_core_platforms(core_path)
    targets = eligible_cells(coverage, core_platforms)
    if len(targets) != 15:
        raise ValueError(f"expected 15 eligible full-year parallel series, found {len(targets)}")
    target_pairs = {(row["country_code"], int(row["year"])) for row in targets}
    current_rankings = pd.read_parquet(rankings_path)
    all_rows: list[dict[str, Any]] = []
    audit_series = []
    years = sorted({year for _, year in target_pairs})
    year_rows: dict[int, dict[tuple[str, str], list[dict[str, str]]]] = {}
    for year in years:
        filename = f"youtube_top100_positions_{year}.csv.gz"
        source_path = source_dir / filename
        captured = capture_manifest.get("files", {}).get(filename)
        if not captured:
            raise ValueError(f"missing captured checksum entry for {filename}")
        if md5_file(source_path) != captured.get("expected_md5"):
            raise ValueError(f"Zenodo MD5 verification failed for {filename}")
        if sha256_file(source_path) != captured.get("sha256"):
            raise ValueError(f"captured SHA-256 verification failed for {filename}")
        markets = {market for market, target_year in target_pairs if target_year == year}
        year_rows[year] = read_year_rows(source_path, year, markets)

    for target in targets:
        market = str(target["country_code"]).upper()
        year = int(target["year"])
        filename = f"youtube_top100_positions_{year}.csv.gz"
        source_path = source_dir / filename
        captured = capture_manifest["files"][filename]
        core_rows = current_rankings[
            (current_rankings.country_code == market)
            & (current_rankings.year == year)
            & (current_rankings.platform == "YOUTUBE")
        ].to_dict(orient="records")
        rows, audit = build_cell(
            market=market,
            year=year,
            expected_weeks=target["expected_week_ends"],
            coverage_row=target,
            weekly_rows=year_rows[year],
            source_path=Path("data/raw")
            / source_dir.relative_to(ROOT / "data/raw")
            / filename,
            source_sha256=captured["sha256"],
            source_asset_url=captured["url"],
            source_retrieved_at=capture_manifest["retrieved_at_utc"],
            core_rows=core_rows,
        )
        all_rows.extend(rows)
        audit_series.append(audit)

    ranking_bytes = "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
        for row in all_rows
    ).encode("utf-8")
    output_dir.mkdir(parents=True, exist_ok=False)
    ranking_path = output_dir / "rankings.jsonl"
    ranking_path.write_bytes(ranking_bytes)
    ranking_sha = hashlib.sha256(ranking_bytes).hexdigest()
    retrieved_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    source_artifacts = [
        source_artifact(
            Path("data/raw") / source_dir.relative_to(ROOT / "data/raw") / "README.md",
            role="Zenodo dataset readme",
            url=ZENODO_RECORD_URL,
        ),
        source_artifact(
            Path("data/raw")
            / source_dir.relative_to(ROOT / "data/raw")
            / "capture-manifest-annual-series-20261117-v2.json",
            role="download checksum capture manifest",
            url=ZENODO_RECORD_URL,
        ),
        source_artifact(
            Path("data/derived/annual_revision/global-rescan-2018-2026-20261111/source_coverage.json"),
            role="project source-coverage reconciliation input",
        ),
        source_artifact(
            Path("data/derived/annual_revision/global-rescan-2018-2026-20261111/new_market_rankings.parquet"),
            role="independent preserved candidate-ranking reconciliation input",
        ),
        source_artifact(
            Path(
                "data/derived/annual_revision/population-total-150k-2018-2026-20261116-v10-archives/combined.jsonl"
            ),
            role="core selection provider-separation reconciliation input",
        ),
    ]
    for year in years:
        filename = f"youtube_top100_positions_{year}.csv.gz"
        artifact_path = Path("data/raw") / source_dir.relative_to(ROOT / "data/raw") / filename
        source_artifacts.append(
            source_artifact(
                artifact_path,
                role="archived official weekly YouTube Top Songs chart rows",
                url=capture_manifest["files"][filename]["url"],
            )
        )

    manifest = {
        "schema_version": "youtube-derived-annual-series-v1",
        "provider_code": PROVIDER_CODE,
        "provider_name": PROVIDER_NAME,
        "publisher_country_code": "US",
        "publisher_jurisdiction_basis": (
            "YouTube's official terms identify Google LLC as the YouTube service provider and "
            "state that it is organized under Delaware, USA law."
        ),
        "chart_family": CHART_FAMILY,
        "chart_category": CHART_CATEGORY,
        "source_type": "derived_annual_ranking_from_archived_primary_weekly_charts",
        "source_dataset_doi": "10.5281/zenodo.23645386",
        "source_dataset_version": "1.0.1",
        "source_dataset_license": "CC BY 4.0",
        "source_url": ZENODO_RECORD_URL,
        "provider_methodology_url": "https://support.google.com/youtube/answer/9014376?hl=en",
        "ranking_derivation": (
            "For each complete calendar year, sum the weekly views of each native chart key for "
            "all Thursday-ending YouTube Top Songs charts whose week_end falls in that calendar "
            "year. Sort by summed views descending, then NFKC-normalized/case-folded title and "
            "artist credit, then native key ascending. Keep the first 500 positions."
        ),
        "annual_chart_status": (
            "Derived project ranking; YouTube did not publish these as year-end charts."
        ),
        "publisher_reported_annual_depth": None,
        "project_candidate_cap": CANDIDATE_LIMIT,
        "ranking_file": "rankings.jsonl",
        "ranking_sha256": ranking_sha,
        "ranked_entry_count": len(all_rows),
        "series": [audit["series_manifest"] for audit in audit_series],
        "source_artifacts": source_artifacts,
        "selection_policy": (
            "Keep each derived YouTube annual series as a separate provider series. Do not merge "
            "these positions into or use them to reduce the 150,000-position Spotify/YouTube "
            "core selection; that selection chose Spotify for every included country-year."
        ),
        "retrieved_at_utc": capture_manifest["retrieved_at_utc"],
        "packet_generated_at_utc": retrieved_at,
        "reconciliation": {
            "core_selection_path": DEFAULT_CORE_SELECTION.as_posix(),
            "candidate_rankings_path": DEFAULT_RANKINGS.as_posix(),
            "eligible_parallel_series": len(audit_series),
            "derived_positions": len(all_rows),
            "exact_candidate_rankings_reproduced": True,
            "core_selection_memberships_unchanged": True,
        },
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    audit_report = {
        "schema_version": "youtube-derived-annual-reproduction-audit-v1",
        "generated_at_utc": retrieved_at,
        "source_dataset_doi": "10.5281/zenodo.23645386",
        "source_dataset_version": "1.0.1",
        "ranking_file": "rankings.jsonl",
        "ranking_sha256": ranking_sha,
        "core_selection_path": DEFAULT_CORE_SELECTION.as_posix(),
        "core_selection_sha256": sha256_file(core_path),
        "candidate_rankings_path": DEFAULT_RANKINGS.as_posix(),
        "candidate_rankings_sha256": sha256_file(rankings_path),
        "eligible_parallel_series": len(audit_series),
        "derived_positions": len(all_rows),
        "all_top500_rows_exactly_match_preserved_candidate_rankings": True,
        "all_series_use_complete_week_end_calendars": True,
        "all_series_have_no_duplicate_native_keys_within_week": True,
        "all_series_have_complete_integer_view_metrics": True,
        "series": [audit["details"] for audit in audit_series],
    }
    audit_path = output_dir / "reproduction-audit.json"
    audit_path.write_text(
        json.dumps(audit_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    manifest["reproduction_audit_path"] = audit_path.name
    manifest["reproduction_audit_sha256"] = sha256_file(audit_path)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "packet": output_dir.as_posix(),
                "series": len(audit_series),
                "positions": len(all_rows),
                "rankings_sha256": ranking_sha,
                "reproduction_audit_sha256": sha256_file(audit_path),
                "series_ids": [audit["details"]["series_id"] for audit in audit_series],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
