"""Build isolated v3+ archive supplement and a hash-bound v4 selection overlay.

No database or network writes.  Every new row is marked as not scientifically
verified; this script only establishes source integrity, annual reconstruction,
and marginal position participation against the frozen v3 selection.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import polars as pl

from chart_observatory.ingestion.historical_backfill import annual_ranks
from chart_observatory.ingestion.quota_boundary import validate_quota_memberships

ROOT = Path(__file__).resolve().parents[1]
V3 = ROOT / "data/derived/annual_revision/global-rescan-2018-2026-20261111-v3-final"
V1 = ROOT / "data/derived/annual_revision/global-rescan-2018-2026-20261111-v3-source-supplement"
KAGGLE = ROOT / "data/raw/historical_backfill/20261030/kaggle-dhruvildave-v85"
KAGGLE_STATE = ROOT / "data/runtime/kaggle-original-recovery-20261031/status.json"
MGD_ROOT = ROOT / "mgd"
MGD_MANIFEST = ROOT / "research/mgd_source_manifest.json"
OUT = (
    ROOT
    / "data/derived/annual_revision/global-rescan-2018-2026-20261111-v3-source-supplement-v2-final"
)
V4 = ROOT / "data/derived/annual_revision/global-rescan-2018-2026-20261111-v4-archive-overlay"
CELLS = (("IL", 2019), ("IL", 2020), ("IL", 2021), ("RU", 2021))
CUTOFF = date(2026, 10, 15)


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows):
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def verify_artifacts(folder: Path, manifest: dict):
    for name, expected in manifest["output_hashes"].items():
        if sha(folder / name) != expected:
            raise ValueError(f"artifact hash mismatch: {folder.name}/{name}")


def load_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def daily_map(frame: pl.DataFrame):
    result: dict[date, dict[str, tuple[int, int, str | None, str | None]]] = defaultdict(dict)
    for row in frame.iter_rows(named=True):
        day = row["period_end"]
        native_id = row["native_id"]
        if day in result and native_id in result[day]:
            raise ValueError(f"duplicate native ID on {day}: {native_id}")
        result[day][native_id] = (
            int(row["metric_value"]),
            int(row["source_position"]),
            row.get("title"),
            row.get("artist"),
        )
    return result


def validate_days(
    source: dict, provider: str, country: str, year: int, *, require_full_depth: bool
):
    for day, tracks in source.items():
        if day.year != year:
            raise ValueError(f"unexpected date {day} in {country}/{year}")
        if len(tracks) > 200 or (require_full_depth and len(tracks) != 200):
            raise ValueError(f"{provider} depth != 200: {country}/{day} ({len(tracks)})")
        ranks = [value[1] for value in tracks.values()]
        if len(ranks) != len(set(ranks)) or min(ranks) < 1 or max(ranks) > 200:
            raise ValueError(f"{provider} rank positions invalid: {country}/{day}")
        if require_full_depth and sorted(ranks) != list(range(1, 201)):
            raise ValueError(f"{provider} ranks do not equal 1..200: {country}/{day}")
        if any(metric < 0 for metric, *_ in tracks.values()):
            raise ValueError(f"negative metric: {provider} {country}/{day}")


def source_provenance(v1_manifest: dict):
    record, files, state = (
        read_json(KAGGLE / "record.json"),
        read_json(KAGGLE / "files.json"),
        read_json(KAGGLE_STATE),
    )
    source_csv, source_zip = KAGGLE / "charts.csv", KAGGLE / "charts.csv.zip"
    for path in (source_csv, source_zip):
        expected = (
            path.with_name(path.name + ".sha256")
            .read_text(encoding="ascii")
            .strip()
            .split()[0]
            .lower()
        )
        if sha(path) != expected:
            raise ValueError(f"pinned Kaggle source hash mismatch: {path.name}")
    if state.get("original_sha256") != sha(source_csv):
        raise ValueError("Kaggle normalization state points to different original bytes")
    dataset_file = next((x for x in files["datasetFiles"] if x["name"] == "charts.csv"), None)
    if not dataset_file or dataset_file.get("totalBytes") != source_csv.stat().st_size:
        raise ValueError("Kaggle metadata size mismatch")
    if (
        record.get("ref") != "dhruvildave/spotify-charts"
        or record.get("currentVersionNumber") != 85
    ):
        raise ValueError("Kaggle version/ref mismatch")
    if v1_manifest["source_file_hashes"].get("charts.csv") != sha(source_csv):
        raise ValueError("v1 supplement source bytes differ from the pinned Kaggle CSV")

    mgd_source = read_json(MGD_MANIFEST)
    mgd_info = {}
    for country in ("IL", "RU"):
        rel = f"mgd\\charts\\regional\\spotify_charts_regional_{country.lower()}.csv"
        entry = next((x for x in mgd_source["files"] if x["path"] == rel), None)
        path = (
            MGD_ROOT / "charts" / "regional" / f"spotify_charts_regional_{country.lower()}.csv.gz"
        )
        if not entry or not path.exists():
            raise ValueError(f"missing MGD source or manifest entry: {country}")
        decompressed_hash = hashlib.sha256()
        with gzip.open(path, "rb") as source_stream:
            for block in iter(lambda: source_stream.read(1024 * 1024), b""):
                decompressed_hash.update(block)
        if decompressed_hash.hexdigest() != entry["sha256"]:
            raise ValueError(f"MGD source hash mismatch: {country}")
        mgd_info[country] = {
            "path": str(path.relative_to(ROOT)),
            "compressed_sha256": sha(path),
            "compressed_size_bytes": path.stat().st_size,
            "decompressed_sha256": decompressed_hash.hexdigest(),
            "decompressed_size_bytes": entry["size_bytes"],
            "manifest_entry": entry,
        }
    return {
        "kaggle": {
            "provider": "KAGGLE_DHRUVILDAVE_V85",
            "ref": record["ref"],
            "dataset_id": record["id"],
            "version": record["currentVersionNumber"],
            "record_last_updated": record["lastUpdated"],
            "local_source_retrieval_timestamp": None,
            "normalization_completed_at": state.get("updated_at"),
            "canonical_url": "https://www.kaggle.com/datasets/dhruvildave/spotify-charts/versions/85",
            "license_as_recorded": record.get("licenseName"),
            "license_caveat": (
                "A licença é apresentada como string de atribuição ao Open Database e aos autores "
                "originais; não foi inferida licença adicional para os conteúdos nem autorização "
                "para redistribuição de letras. Preservar atribuição e rever termos aplicáveis "
                "antes de publicar dados derivados."
            ),
            "files": {
                p.name: {"sha256": sha(p), "size_bytes": p.stat().st_size}
                for p in (source_csv, source_zip, KAGGLE / "record.json", KAGGLE / "files.json")
            },
        },
        "mgd_plus": {
            "upstream_record": "https://zenodo.org/records/8086643",
            "doi": "10.5281/zenodo.8086643",
            "upstream_license": "CC BY 4.0 (record metadata)",
            "local_retrieval_timestamp": None,
            "local_file_to_upstream_archive_linkage": (
                "Not cryptographically established; local files match the checked-in MGD source "
                "manifest, but no acquisition timestamp or upstream package-to-file proof was "
                "found."
            ),
            "files": mgd_info,
            "caveat": (
                "MGD+ charts are derived from Spotify chart data; Spotify terms and third-party "
                "rights may still constrain redistribution and downstream use. This supplement "
                "does not redistribute source archives."
            ),
        },
        "source_manifest_sha256": sha(MGD_MANIFEST),
    }


def load_mgd(country: str) -> pl.DataFrame:
    path = MGD_ROOT / "charts" / "regional" / f"spotify_charts_regional_{country.lower()}.csv.gz"
    return (
        pl.scan_csv(path, separator="\t", infer_schema_length=1000)
        .filter(
            (pl.col("market").str.to_uppercase() == country)
            & (pl.col("Chart") == "Top 200")
            & pl.col("Date").str.starts_with("2021-")
        )
        .select(
            pl.lit(country).alias("country_code"),
            pl.col("Date").str.to_date("%Y-%m-%d", strict=True).alias("period_end"),
            pl.col("ID").cast(pl.String).alias("native_id"),
            pl.col("Track").cast(pl.String).alias("title"),
            pl.col("Artist").cast(pl.String).alias("artist"),
            pl.col("Streams")
            .cast(pl.String)
            .str.replace_all(",", "")
            .cast(pl.Int64, strict=False)
            .alias("metric_value"),
            pl.col("Position").cast(pl.Int32, strict=False).alias("source_position"),
        )
        .collect(engine="streaming")
    )


def load_kaggle_2021(country: str) -> pl.DataFrame:
    return (
        pl.scan_parquet(KAGGLE / "full-top200.parquet")
        .filter((pl.col("country_code") == country) & (pl.col("period_end").dt.year() == 2021))
        .select(
            "country_code",
            "period_end",
            "native_id",
            "title",
            "artist",
            "metric_value",
            pl.col("source_rank").alias("source_position"),
        )
        .collect(engine="streaming")
    )


def rebuild_2021(country: str, quota: int):
    mgd = load_mgd(country)
    kaggle = load_kaggle_2021(country)
    mgd_days, kaggle_days = daily_map(mgd), daily_map(kaggle)
    validate_days(mgd_days, "MGD", country, 2021, require_full_depth=True)
    validate_days(kaggle_days, "Kaggle v85", country, 2021, require_full_depth=False)
    overlap = set(mgd_days) & set(kaggle_days)
    exact, subset, incompatible = 0, 0, []
    for day in sorted(overlap):
        primary, auxiliary = mgd_days[day], kaggle_days[day]
        if all(key in primary and primary[key][0] == value[0] for key, value in auxiliary.items()):
            exact += 1 if len(auxiliary) == len(primary) else 0
            subset += 1 if len(auxiliary) < len(primary) else 0
        else:
            incompatible.append(str(day))
    if incompatible:
        raise ValueError(f"MGD/Kaggle overlapping days conflict for {country}: {incompatible[:10]}")
    if not exact or not overlap:
        raise ValueError(f"no independently corroborated overlapping source days for {country}")
    patched_days = {day: dict(rows) for day, rows in mgd_days.items()}
    added_days = sorted(set(kaggle_days) - set(mgd_days))
    for day in added_days:
        if len(kaggle_days[day]) != 200 or sorted(
            value[1] for value in kaggle_days[day].values()
        ) != list(range(1, 201)):
            raise ValueError(
                f"cannot use incomplete Kaggle chart to patch missing day: {country}/{day}"
            )
        patched_days[day] = kaggle_days[day]
    expected = (date(2022, 1, 1) - date(2021, 1, 1)).days
    if len(patched_days) != expected:
        raise ValueError(
            f"reconstructed annual calendar incomplete: {country}: {len(patched_days)}/{expected}"
        )
    records = []
    for day, tracks in patched_days.items():
        for native_id, (metric, pos, title, artist) in tracks.items():
            records.append(
                {
                    "country_code": country,
                    "period_end": day,
                    "native_id": native_id,
                    "title": title,
                    "artist": artist,
                    "metric_value": metric,
                    "source_position": pos,
                }
            )
    frame = pl.DataFrame(records)
    ranked, coverage = annual_ranks(
        frame,
        markets={country},
        year=2021,
        cutoff=CUTOFF,
        frequency="DAILY",
        platform="SPOTIFY",
        provider="MGD_PLUS_WITH_KAGGLE_V85_MISSING_DAYS",
        expected_depth=200,
    )
    cov = coverage[0]
    if (
        cov["coverage_status"] != "COMPLETE"
        or cov["collected_periods"] != expected
        or cov["depth_shortfall_periods"]
        or cov["rank_invalid_observations"]
        or cov["rank_start_missing_periods"]
    ):
        raise ValueError(f"annual rank completeness/depth failed for {country}: {cov}")
    candidates = [r for r in ranked if r["position"] <= quota + 1]
    ties = [
        (a["position"], b["position"])
        for a, b in zip(candidates, candidates[1:], strict=False)
        if a["metric_value"] == b["metric_value"]
    ]
    if ties:
        raise ValueError(f"annual quota boundary ties need adjudication {country}/2021: {ties}")
    selected = [r for r in ranked if r["position"] <= quota]
    if len(selected) != quota or any(not r.get("title") or not r.get("artist") for r in selected):
        raise ValueError(f"selected metadata missing or quota incomplete: {country}/2021")
    memberships = [
        {
            **r,
            "quota_main": quota,
            "selection_status": "CALENDAR_ELIGIBLE",
            "coverage_status": "COMPLETE",
            "collected_periods": expected,
            "expected_periods": expected,
            "not_for_paid_submission": True,
        }
        for r in selected
    ]
    audit = {
        "country_code": country,
        "year": 2021,
        "quota": quota,
        "mgd_days": len(mgd_days),
        "kaggle_v85_days": len(kaggle_days),
        "overlap_days": len(overlap),
        "exact_overlap_days": exact,
        "kaggle_subset_overlap_days": subset,
        "incompatible_overlap_days": len(incompatible),
        "kaggle_patch_dates": [str(x) for x in added_days],
        "patched_day_count": len(added_days),
        "expected_calendar_days": expected,
        "reconstructed_days": len(patched_days),
        "all_days_have_200_unique_native_ids_and_source_positions_1_to_200": True,
        "annual_boundary_tie_pairs": 0,
        "selected_metadata_missing": 0,
        "position_memberships_added": len(memberships),
        "scientifically_verified": False,
        "provider_definition": (
            "MGD native days plus Kaggle v85 full daily Top 200 only for MGD missing dates; "
            "overlapping Kaggle rows must be a metric-identical subset of MGD."
        ),
    }
    return memberships, ranked, cov, audit


def build():
    if OUT.exists() or V4.exists():
        raise FileExistsError("refusing to overwrite v2 supplement or v4 overlay")
    v3_manifest = read_json(V3 / "manifest.json")
    verify_artifacts(V3, v3_manifest)
    v1_manifest = read_json(V1 / "manifest.json")
    verify_artifacts(V1, v1_manifest)
    parent_rows = load_jsonl(V3 / "combined.jsonl")
    v1_rows = load_jsonl(V1 / "added_memberships.jsonl")
    if len(v1_rows) != 240:
        raise ValueError(f"expected preserved IL/2019-20 supplement of 240, got {len(v1_rows)}")
    v3_keys = {(x["country_code"], int(x["year"]), int(x["position"])) for x in parent_rows}
    quota_by_country = {
        x["country_code"]: x["quota_per_year_main"]
        for x in read_json(V3 / "countries.json")
        if x.get("quota_per_year_main") is not None
    }
    prov = source_provenance(v1_manifest)
    new_2021, rankings_2021, coverage_2021, audits = [], [], [], []
    for country in ("IL", "RU"):
        members, rankings, cov, audit = rebuild_2021(country, quota_by_country[country])
        new_2021.extend(members)
        rankings_2021.extend(rankings)
        coverage_2021.append(cov)
        audits.append(audit)
    delta = v1_rows + new_2021
    if len(delta) != 560:
        raise ValueError(f"expected net 560 new participations, got {len(delta)}")
    delta_keys = [(x["country_code"], int(x["year"]), int(x["position"])) for x in delta]
    if len(delta_keys) != len(set(delta_keys)):
        raise ValueError("duplicate participation key inside delta")
    collision = set(delta_keys) & v3_keys
    if collision:
        raise ValueError(f"delta collides with frozen v3 positions: {sorted(collision)[:10]}")
    for x in delta:
        if (
            x["selection_status"] != "CALENDAR_ELIGIBLE"
            or x.get("not_for_paid_submission") is not True
        ):
            raise ValueError("supplement row is not marked as non-submittable calendar eligible")

    parent_cells = load_jsonl(V3 / "country_years.jsonl")
    members = sorted(
        parent_rows + delta, key=lambda x: (x["country_code"], int(x["year"]), int(x["position"]))
    )
    validate_quota_memberships(members, quota_by_country)
    delta_by_cell = Counter((x["country_code"], int(x["year"])) for x in delta)
    cells = []
    for cell in parent_cells:
        row = dict(cell)
        key = (row["country_code"], int(row["year"]))
        added = delta_by_cell.get(key, 0)
        if added:
            quota = int(row["quota"])
            row.update(
                selected_positions=quota,
                provisional_positions=0,
                complete_calendar_year_positions=quota,
                missing_positions=0,
                missing_complete_annual_positions=0,
                missing_position_numbers=[],
                platforms=["SPOTIFY"],
                selection_statuses={"CALENDAR_ELIGIBLE": quota},
                status="QUOTA_FILLED_COMPLETE_CALENDAR",
            )
        cells.append(row)
    rows_per_cell = Counter((x["country_code"], int(x["year"])) for x in members)
    parent_rows_per_cell = Counter((x["country_code"], int(x["year"])) for x in parent_rows)
    for cell in cells:
        key = (cell["country_code"], int(cell["year"]))
        expected_rows = parent_rows_per_cell[key] + delta_by_cell.get(key, 0)
        if rows_per_cell[key] != expected_rows:
            raise ValueError(f"v4 row key count does not equal v3 plus marginal delta: {key}")
        if key in delta_by_cell and rows_per_cell[key] != int(cell["quota"]):
            raise ValueError(f"supplement did not fill target cell quota: {key}")
    inherited_cell_count_mismatches = sum(
        1
        for cell in parent_cells
        if parent_rows_per_cell[(cell["country_code"], int(cell["year"]))]
        != int(cell.get("selected_positions") or 0) + int(cell.get("provisional_positions") or 0)
    )

    parent_rank = pl.read_parquet(V3 / "new_market_rankings.parquet")
    v1_rank = pl.read_parquet(V1 / "new_market_rankings.parquet")
    rank2021 = pl.DataFrame(rankings_2021)
    all_rank = pl.concat([parent_rank, v1_rank, rank2021], how="diagonal_relaxed")
    cov = (
        read_json(V3 / "source_coverage.json")
        + read_json(V1 / "added_source_coverage.json")
        + coverage_2021
    )

    # Build the isolated evidence package.
    OUT.mkdir(parents=True)
    write_jsonl(OUT / "added_memberships.jsonl", delta)
    with (OUT / "position_delta.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        fields = [
            "country_code",
            "year",
            "position",
            "candidate_id",
            "title",
            "artist",
            "metric_value",
            "provider",
            "v3_position_key_present",
            "selection_status",
            "scientifically_verified",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in delta:
            writer.writerow(
                {
                    "country_code": row["country_code"],
                    "year": row["year"],
                    "position": row["position"],
                    "candidate_id": row["candidate_id"],
                    "title": row["title"],
                    "artist": row["artist"],
                    "metric_value": row["metric_value"],
                    "provider": row["provider"],
                    "v3_position_key_present": False,
                    "selection_status": row["selection_status"],
                    "scientifically_verified": False,
                }
            )
    cell_delta = []
    before_cells = {(x["country_code"], int(x["year"])): x for x in parent_cells}
    after_cells = {(x["country_code"], int(x["year"])): x for x in cells}
    for country, year in CELLS:
        before, after = before_cells[(country, year)], after_cells[(country, year)]
        cell_delta.append(
            {
                "country_code": country,
                "year": year,
                "quota": before["quota"],
                "v3_selected_positions": before["selected_positions"],
                "added_missing_position_participations": delta_by_cell[(country, year)],
                "v4_selected_positions": after["selected_positions"],
                "v4_missing_positions": after["missing_positions"],
                "global_position_keys_colliding_with_v3": 0,
                "gate_status": "NOT_APPROVED_SCIENTIFICALLY",
            }
        )
    with (OUT / "cell_delta.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(cell_delta[0]))
        writer.writeheader()
        writer.writerows(cell_delta)
    write_json(OUT / "source_provenance.json", prov)
    write_json(
        OUT / "source_validation.json",
        {
            "frozen_v3_manifest_sha256": sha(V3 / "manifest.json"),
            "v1_240_supplement_manifest_sha256": sha(V1 / "manifest.json"),
            "v3_memberships": len(parent_rows),
            "supplement_memberships": len(delta),
            "v4_memberships": len(members),
            "duplicate_delta_position_keys": 0,
            "delta_position_keys_present_in_v3": 0,
            "cells": [
                {
                    "country_code": "IL",
                    "year": 2019,
                    "source": "Kaggle v85 native Top 200",
                    "added_positions": 120,
                    "verified_calendar": True,
                    "verified_top200_daily_depth": True,
                    "annual_boundary_ties": 0,
                    "native_id_metadata_present": True,
                    "scientifically_verified": False,
                },
                {
                    "country_code": "IL",
                    "year": 2020,
                    "source": "Kaggle v85 native Top 200",
                    "added_positions": 120,
                    "verified_calendar": True,
                    "verified_top200_daily_depth": True,
                    "annual_boundary_ties": 0,
                    "native_id_metadata_present": True,
                    "scientifically_verified": False,
                },
            ]
            + audits,
            "source_policy": (
                "No ranking positions were manufactured; annual order is recomputed from full-year "
                "observed daily stream sums. Missing source dates are patched only from complete "
                "Top 200 daily charts after overlap compatibility checks. Existing v3 rows and "
                "denominators remain intact."
            ),
            "inherited_v3_cell_metadata_mismatches": inherited_cell_count_mismatches,
            "cell_metadata_caveat": (
                "Non-target v3 country_years fields are preserved byte-for-byte. Their "
                "selected_positions/provisional_positions totals are not always additive to the "
                "actual combined.jsonl row count; the v4 audit reconciles actual participation "
                "keys directly to v3 rows plus marginal delta."
            ),
            "g1_approval": False,
        },
    )
    v2_artifacts = [
        "added_memberships.jsonl",
        "position_delta.csv",
        "cell_delta.csv",
        "source_provenance.json",
        "source_validation.json",
    ]
    v2manifest = {
        "version": "global-v3-source-supplement-v2",
        "parent_selection": str(V3.relative_to(ROOT)),
        "parent_manifest_sha256": sha(V3 / "manifest.json"),
        "preserved_v1_supplement_manifest_sha256": sha(V1 / "manifest.json"),
        "new_position_participations": len(delta),
        "cells": cell_delta,
        "frozen_selection_modified": False,
        "database_write": False,
        "network_calls": 0,
        "paid_calls": 0,
        "scientifically_verified": False,
        "g1_approved": False,
        "output_hashes": {n: sha(OUT / n) for n in v2_artifacts},
        "input_hashes": {
            str(p.relative_to(ROOT)): sha(p)
            for p in [
                V3 / "manifest.json",
                V3 / "combined.jsonl",
                V3 / "country_years.jsonl",
                V1 / "manifest.json",
                V1 / "added_memberships.jsonl",
                V1 / "new_market_rankings.parquet",
                KAGGLE / "charts.csv",
                KAGGLE / "charts.csv.sha256",
                KAGGLE / "charts.csv.zip",
                KAGGLE / "charts.csv.zip.sha256",
                KAGGLE / "record.json",
                KAGGLE / "files.json",
                KAGGLE / "full-top200.parquet",
                KAGGLE_STATE,
                MGD_MANIFEST,
                MGD_ROOT / "charts/regional/spotify_charts_regional_il.csv.gz",
                MGD_ROOT / "charts/regional/spotify_charts_regional_ru.csv.gz",
                ROOT / "src/chart_observatory/ingestion/historical_backfill.py",
                Path(__file__).resolve(),
            ]
        },
    }
    write_json(OUT / "manifest.json", v2manifest)

    # Construct a full immutable v4 overlay (copy v3 artifacts, replace derived files).
    import shutil

    shutil.copytree(V3, V4)
    write_jsonl(V4 / "combined.jsonl", members)
    write_jsonl(V4 / "country_years.jsonl", cells)
    write_jsonl(
        V4 / "ranked_titles.jsonl",
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
            for r in members
        ],
    )
    write_json(V4 / "source_coverage.json", cov)
    all_rank.write_parquet(V4 / "new_market_rankings.parquet")
    with (V4 / "country_years.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(cells[0]))
        writer.writeheader()
        writer.writerows(
            {k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in r.items()}
            for r in cells
        )
    v4_manifest = dict(v3_manifest)
    v4_manifest.update(
        {
            "selection_revision": "global-rescan-v4-archive-overlay",
            "parent_selection": str(V3.relative_to(ROOT)),
            "parent_selection_manifest_sha256": sha(V3 / "manifest.json"),
            "supplement_manifest_sha256": sha(OUT / "manifest.json"),
            "scientifically_verified": False,
            "memberships": len(members),
            "new_definitive_memberships": int(v3_manifest["new_definitive_memberships"])
            + len(delta),
            "candidate_identities": len({r["candidate_id"] for r in members}),
            "countries_with_memberships": len({r["country_code"] for r in members}),
            "cells_with_memberships": len(rows_per_cell),
            "missing_positions": sum(int(c["missing_positions"] or 0) for c in cells),
            "missing_complete_annual_positions": sum(
                int(c["missing_complete_annual_positions"] or 0) for c in cells
            ),
            "database_write": False,
            "paid_calls": 0,
            "network_calls": 0,
            "g1_approved": False,
            "scientifically_verified_positions_added": 0,
            "archive_overlay_added_position_participations": len(delta),
            "inherited_v3_cell_metadata_mismatches": inherited_cell_count_mismatches,
            "archive_overlay_cells": [f"{c}/{y}" for c, y in CELLS],
            "raw_membership_coverage_pct": round(
                len(members) / int(v3_manifest["requested_positions"]) * 100, 4
            ),
            "input_hashes": v2manifest["input_hashes"],
        }
    )
    artifact_names = [n for n in v3_manifest["output_hashes"] if n != "manifest.json"]
    v4_manifest["output_hashes"] = {n: sha(V4 / n) for n in artifact_names}
    write_json(V4 / "manifest.json", v4_manifest)
    # Verify written bytes and numerical/identity reconciliation before reporting.
    verify_artifacts(V4, v4_manifest)
    verify_artifacts(OUT, v2manifest)
    if int(v4_manifest["memberships"]) != 90600 or int(v4_manifest["missing_positions"]) != 187050:
        memberships = v4_manifest["memberships"]
        missing_positions = v4_manifest["missing_positions"]
        raise ValueError(f"unexpected v4 global count: {memberships} / {missing_positions}")
    print(
        json.dumps(
            {
                "supplement": str(OUT.relative_to(ROOT)),
                "selection_v4": str(V4.relative_to(ROOT)),
                "v3_memberships": len(parent_rows),
                "net_added_position_participations": len(delta),
                "v4_memberships": len(members),
                "requested_positions": v4_manifest["requested_positions"],
                "raw_coverage_pct": v4_manifest["raw_membership_coverage_pct"],
                "missing_positions": v4_manifest["missing_positions"],
                "g1_approved": False,
                "database_write": False,
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    build()
