"""Read-only audit of the recovered corpus and chart linkage; no provider calls."""

import csv
import hashlib
import json
import unicodedata
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import polars as pl
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session, load_only

from chart_observatory.config import Settings
from chart_observatory.db.models.corpus import LyricClassificationSnapshot, LyricDocument
from chart_observatory.lyrics.identity_quarantine import (
    load_quarantine_entries,
    load_suspended_sources,
)
from chart_observatory.lyrics.scientific_selection import assess_classification


def normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output = root / "data/derived/research_quality/20261007"
    output.mkdir(parents=True, exist_ok=True)
    engine = create_engine(Settings.load(root).database_url)
    entries = {entry.lyric_document_id: entry for entry in load_quarantine_entries()}
    suspended = load_suspended_sources()
    report: dict[str, object] = {
        "audited_at": datetime.now(UTC).isoformat(),
        "provider_calls": 0,
        "selection_unit": "latest_snapshot_per_document_model_taxonomy_prompt",
        "population_share_identifiable": False,
    }
    with Session(engine) as session:
        report["table_counts"] = {
            name: session.scalar(text(f"SELECT count(*) FROM {name}"))
            for name in (
                "lyric_documents",
                "lyric_classification_snapshots",
                "canonical_tracks",
                "chart_entries",
                "chart_snapshots",
                "canonical_chart_entries",
                "coverage_cells",
                "platform_item_track_links",
            )
        }
        report["source_counts"] = dict(
            session.execute(
                select(LyricDocument.source, func.count()).group_by(LyricDocument.source)
            ).all()
        )
        report["missing_language_documents"] = session.scalar(
            select(func.count())
            .select_from(LyricDocument)
            .where(LyricDocument.language_code.is_(None))
        )
        s = LyricClassificationSnapshot
        ranked = select(
            s.id,
            func.row_number()
            .over(
                partition_by=(
                    s.lyric_document_id,
                    s.model_id,
                    s.taxonomy_version,
                    s.prompt_version,
                ),
                order_by=s.append_order.desc(),
            )
            .label("position"),
        ).subquery()
        query = (
            select(LyricDocument, s)
            .join(s, s.lyric_document_id == LyricDocument.id)
            .join(ranked, ranked.c.id == s.id)
            .where(ranked.c.position == 1)
            .options(
                load_only(
                    LyricDocument.id,
                    LyricDocument.canonical_track_id,
                    LyricDocument.content_sha256,
                    LyricDocument.source,
                    LyricDocument.rights_status,
                ),
                load_only(
                    s.id,
                    s.canonical_track_id,
                    s.lyrics_hash,
                    s.classification_status,
                    s.result_json,
                    s.model_id,
                    s.taxonomy_version,
                    s.prompt_version,
                ),
            )
            .execution_options(yield_per=1000)
        )
        counts: Counter[str] = Counter()
        reasons: Counter[str] = Counter()
        with (output / "snapshot_eligibility.csv").open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.writer(handle)
            writer.writerow(
                (
                    "document_id",
                    "track_id",
                    "snapshot_id",
                    "source",
                    "model_id",
                    "taxonomy_version",
                    "prompt_version",
                    "status",
                    "primary_identity_eligible",
                    "exploratory_eligible",
                    "reasons",
                    "chart_link_verified",
                )
            )
            for document, snapshot in session.execute(query):
                entry = entries.get(document.id)
                decision = assess_classification(
                    document,
                    snapshot,
                    entries=(entry,) if entry else (),
                    suspended_sources=suspended,
                )
                counts["selected_snapshots"] += 1
                counts[snapshot.classification_status] += 1
                counts["primary_identity_eligible"] += decision.primary_eligible
                counts["exploratory_eligible"] += decision.exploratory_eligible
                reasons.update(decision.reasons)
                writer.writerow(
                    (
                        document.id,
                        document.canonical_track_id,
                        snapshot.id,
                        document.source,
                        snapshot.model_id,
                        snapshot.taxonomy_version,
                        snapshot.prompt_version,
                        snapshot.classification_status,
                        decision.primary_eligible,
                        decision.exploratory_eligible,
                        "|".join(decision.reasons),
                        False,
                    )
                )
        report["latest_snapshot_counts"] = dict(counts)
        report["exclusion_reasons_nonexclusive"] = dict(reasons)
        tracks = session.execute(
            text(
                "SELECT t.id, t.title, string_agg(a.name, ', ' ORDER BY a.name) AS artists "
                "FROM canonical_tracks t JOIN track_artists ta ON ta.track_id=t.id "
                "JOIN artists a ON a.id=ta.artist_id GROUP BY t.id, t.title"
            )
        ).all()
        document_keys = {
            (str(track), source, digest): str(document_id)
            for document_id, track, source, digest in session.execute(
                select(
                    LyricDocument.id,
                    LyricDocument.canonical_track_id,
                    LyricDocument.source,
                    LyricDocument.content_sha256,
                )
            )
        }
    master = pl.read_parquet(root / "data/derived/track_master.parquet")
    candidates: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in master.iter_rows(named=True):
        if row["title"] and row["artist_names"]:
            candidates[(normalize(row["title"]), normalize(row["artist_names"]))].append(
                row["canonical_track_id"]
            )
    candidate_rows = []
    for track_id, title, artists in tracks:
        for chart_id in candidates.get((normalize(title), normalize(artists)), ()):
            candidate_rows.append(
                {
                    "lyric_track_id": str(track_id),
                    "chart_track_id": chart_id,
                    "title": title,
                    "artist": artists,
                    "evidence": "normalized_title_artist_exact",
                    "verified": False,
                    "use_in_primary_analysis": False,
                }
            )
    pl.DataFrame(
        candidate_rows,
        schema={
            "lyric_track_id": pl.String,
            "chart_track_id": pl.String,
            "title": pl.String,
            "artist": pl.String,
            "evidence": pl.String,
            "verified": pl.Boolean,
            "use_in_primary_analysis": pl.Boolean,
        },
    ).write_parquet(output / "identity_crosswalk_candidates.parquet")
    report["crosswalk_candidate_pairs"] = len(candidate_rows)
    report["verified_crosswalk_pairs"] = 0
    report["shared_track_ids_with_master"] = len(
        {str(row[0]) for row in tracks} & set(master["canonical_track_id"].to_list())
    )
    master_by_id = {row["canonical_track_id"]: row for row in master.iter_rows(named=True)}
    lineage_rows = []
    lineage_failures: Counter[str] = Counter()
    artifact = root / "data/derived/lyrics/gemini_annotations.jsonl"
    with artifact.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                lineage_failures["malformed_original_jsonl_record"] += 1
                continue
            if not isinstance(payload, dict):
                lineage_failures["nonobject_original_jsonl_record"] += 1
                continue
            master_row = master_by_id.get(payload.get("song_id"))
            if master_row is None:
                lineage_failures["original_song_id_missing_from_master"] += 1
                continue
            title, artist = (
                str(payload.get("title") or "").strip(),
                str(payload.get("artist") or "").strip(),
            )
            if (
                not title
                or not artist
                or normalize(title) != normalize(master_row["title"] or "")
                or normalize(artist) != normalize(master_row["artist_names"] or "")
            ):
                lineage_failures["original_song_id_metadata_mismatch"] += 1
                continue
            lyric = payload.get("original_lyrics")
            if not isinstance(lyric, str):
                continue
            digest = hashlib.sha256(lyric.encode("utf-8")).hexdigest()
            track_id = str(
                uuid5(
                    NAMESPACE_URL,
                    "chart-observatory:api-lyrics:track:v1:"
                    + normalize(artist)
                    + "\0"
                    + normalize(title),
                )
            )
            source = str(payload.get("lyrics_source") or "UNKNOWN_API").strip().upper()[:100]
            document_id = document_keys.get((track_id, source, digest))
            if document_id is None:
                lineage_failures["document_hash_source_not_found"] += 1
                continue
            lineage_rows.append(
                {
                    "document_id": document_id,
                    "lyric_track_id": track_id,
                    "chart_track_id": payload["song_id"],
                    "lyrics_hash": digest,
                    "source_artifact": str(artifact.relative_to(root)),
                    "source_row_number": line_number,
                    "metadata_lineage_verified": True,
                    "lyrics_identity_verified": False,
                    "use_in_primary_analysis": False,
                }
            )
    lineage_schema = {
        "document_id": pl.String,
        "lyric_track_id": pl.String,
        "chart_track_id": pl.String,
        "lyrics_hash": pl.String,
        "source_artifact": pl.String,
        "source_row_number": pl.Int64,
        "metadata_lineage_verified": pl.Boolean,
        "lyrics_identity_verified": pl.Boolean,
        "use_in_primary_analysis": pl.Boolean,
    }
    lineage = pl.DataFrame(lineage_rows, schema=lineage_schema).unique(
        subset=["document_id", "chart_track_id"]
    )
    lineage.write_parquet(output / "original_id_lineage.parquet")
    report["original_id_lineage_pairs"] = lineage.height
    report["original_id_lineage_documents"] = lineage["document_id"].n_unique()
    report["original_id_lineage_failures"] = dict(lineage_failures)
    eligible = pl.read_csv(output / "snapshot_eligibility.csv")
    sample = (
        eligible.filter(pl.col("status") == "classified")
        .with_columns(
            pl.col("document_id")
            .map_elements(
                lambda value: hashlib.sha256(("research-review-v1:" + value).encode()).hexdigest(),
                return_dtype=pl.String,
            )
            .alias("sampling_order")
        )
        .sort("source", "sampling_order")
        .group_by("source", maintain_order=True)
        .head(40)
    )
    sample.join(
        lineage.select("document_id", "chart_track_id", "source_artifact", "source_row_number"),
        on="document_id",
        how="left",
    ).with_columns(
        pl.lit("").alias("reviewer_1_identity_decision"),
        pl.lit("").alias("reviewer_2_identity_decision"),
        pl.lit("").alias("evidence_reference"),
        pl.lit("").alias("adjudication"),
    ).write_csv(output / "identity_review_sample.csv")
    report["identity_review_sample_rows"] = sample.height
    catalog = pl.scan_parquet(root / "data/normalized/source_catalog.parquet")
    catalog.group_by("provider", "origin_platform", "market_code", "chart_family").agg(
        pl.len().alias("observations"),
        pl.col("period_start").min().alias("first_period"),
        pl.col("period_end").max().alias("last_period"),
        pl.col("canonical_track_id").drop_nulls().n_unique().alias("resolved_tracks"),
    ).collect(engine="streaming").write_parquet(output / "ranking_inventory.parquet")
    report["chart_catalog_rows"] = catalog.select(pl.len()).collect().item()
    (output / "audit.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
