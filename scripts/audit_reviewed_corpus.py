"""Read-only corpus audit anchored to human reports and the frozen article selection."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from sqlalchemy import create_engine, text

from chart_observatory.config import Settings
from chart_observatory.lyrics.review_evidence import import_comparison_export
from chart_observatory.lyrics.text_quality import prepare_lyric_derivative

ROOT = Path(__file__).resolve().parents[1]


def run(reviews: Path, selection: Path, output: Path) -> dict:
    evidence = import_comparison_export(reviews)
    output.mkdir(parents=True, exist_ok=False)
    (output / "original-reviews.json").write_bytes(reviews.read_bytes())
    selected = {}
    with selection.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            selected[row["document_id"]] = row
    reports = {row["document_id"]: row for row in evidence}
    counts, flags, sources = Counter(), Counter(), Counter()
    hashes = defaultdict(list)
    traces, batch = [], []
    schema = pa.schema([
        ("document_id", pa.string()), ("track_id", pa.string()),
        ("source", pa.string()), ("lyrics_hash", pa.string()),
        ("article_selected", pa.bool_()), ("article_hash_matches", pa.bool_()),
        ("characters", pa.int64()), ("flags", pa.list_(pa.string())),
        ("human_report", pa.bool_()),
    ])
    engine = create_engine(Settings.load(ROOT).database_url, connect_args={"connect_timeout": 5})
    with (
        pq.ParquetWriter(output / "document-audit.parquet", schema) as writer,
        (output / "recovery-targets.jsonl").open("w", encoding="utf-8") as targets,
        engine.connect() as conn,
    ):
        conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        observed_at = str(conn.execute(text("SELECT transaction_timestamp()")).scalar_one())
        rows = conn.execution_options(stream_results=True).execute(text("""
            SELECT d.id, d.canonical_track_id, d.source, d.source_version,
                   d.content_sha256, d.text, d.metadata_json, d.retrieved_at,
                   d.language_code, t.title
            FROM lyric_documents d JOIN canonical_tracks t ON t.id=d.canonical_track_id
        """)).mappings()
        for row in rows:
            doc_id, track_id = str(row["id"]), str(row["canonical_track_id"])
            value = row["text"] or ""
            derivative = prepare_lyric_derivative(value, row["source"])
            reasons = list(derivative.flags)
            actual_hash = hashlib.sha256(value.encode()).hexdigest()
            if actual_hash != row["content_sha256"]:
                reasons.append("stored_hash_mismatch")
            article = selected.get(doc_id)
            matches = article is not None and article["lyrics_hash"] == actual_hash
            if article and not matches:
                reasons.append("article_hash_mismatch")
            human = reports.get(doc_id)
            bound = human is not None and human["lyrics_hash"] == actual_hash
            if bound:
                reasons.append("human_report_pending_adjudication")
            hashes[actual_hash].append((doc_id, track_id))
            counts["documents"] += 1
            counts["article_selected"] += article is not None
            counts["documents_with_signals"] += bool(reasons)
            counts["article_documents_with_signals"] += bool(article and reasons)
            counts["human_reports_bound"] += bound
            sources[row["source"]] += 1
            flags.update(reasons)
            batch.append({
                "document_id": doc_id, "track_id": track_id, "source": row["source"],
                "lyrics_hash": actual_hash, "article_selected": article is not None,
                "article_hash_matches": matches, "characters": len(value),
                "flags": reasons, "human_report": bound,
            })
            if len(batch) >= 1000:
                writer.write_table(pa.Table.from_pylist(batch, schema=schema))
                batch.clear()
            if reasons:
                targets.write(json.dumps({
                    "document_id": doc_id, "track_id": track_id,
                    "title": row["title"],
                    "artist": human["artist"] if human else None,
                    "lyrics_hash": actual_hash, "source": row["source"],
                    "language": row["language_code"], "reasons": reasons,
                    "article_selected": article is not None,
                }, ensure_ascii=False) + "\n")
            if human:
                snapshot_id = human["provenance"].get("snapshot_id")
                snapshot = conn.execute(text("""
                    SELECT lyrics_hash, canonical_track_id, model_id, prompt_version,
                           taxonomy_version, classification_status
                    FROM lyric_classification_snapshots WHERE id=CAST(:id AS uuid)
                """), {"id": snapshot_id}).mappings().first() if snapshot_id else None
                traces.append({
                    **human, "database_hash": actual_hash, "report_hash_matches": bound,
                    "stored_hash_matches": actual_hash == row["content_sha256"],
                    "article_selected": article is not None, "article_hash_matches": matches,
                    "article_snapshot_id": article.get("snapshot_id") if article else None,
                    "portal_snapshot": dict(snapshot) if snapshot else None,
                    "portal_snapshot_hash_matches": bool(
                        snapshot and snapshot["lyrics_hash"] == actual_hash),
                    "source_version": row["source_version"],
                    "source_metadata": row["metadata_json"],
                    "retrieved_at": str(row["retrieved_at"]),
                    "stored_text": value, "characters": len(value),
                    "disposition": "pending_recovery_and_adjudication",
                    "raw_source_comparison": "not_established",
                    "portal_rendered_text_comparison": "not_available_in_review_export",
                })
        if batch:
            writer.write_table(pa.Table.from_pylist(batch, schema=schema))
    engine.dispose()
    duplicates = [
        {"lyrics_hash": key, "documents": values}
        for key, values in hashes.items() if len({track for _, track in values}) > 1
    ]
    (output / "cross-identity-texts.json").write_text(
        json.dumps(duplicates, indent=2), encoding="utf-8")
    (output / "review-traces.json").write_text(
        json.dumps(traces, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    report = {
        "version": "reviewed-corpus-audit-v1", "database_observed_at": observed_at,
        "finished_at": datetime.now(UTC).isoformat(), "counts": dict(counts),
        "signals": dict(flags), "sources": dict(sources),
        "cross_identity_hash_groups": len(duplicates), "review_count": len(evidence),
        "ai_exposed_reviews": sum(row["ai_exposed"] is True for row in evidence),
        "missing_review_documents": sorted(set(reports) - {r["document_id"] for r in traces}),
        "selection_sha256": hashlib.sha256(selection.read_bytes()).hexdigest(),
        "signals_establish_incompleteness": False, "provider_calls": 0,
        "article_validated": False, "human_adjudication_pending": True,
    }
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviews", type=Path, required=True)
    parser.add_argument(
        "--selection", type=Path,
        default=ROOT / "research/article/analysis-final/selected-classifications.csv",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.reviews, args.selection, args.output_dir), indent=2))
