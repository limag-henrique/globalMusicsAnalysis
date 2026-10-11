"""Build versioned local quality derivatives; no database writes or provider calls."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from pydantic import ValidationError
from sqlalchemy import create_engine, text

from chart_observatory.config import Settings
from chart_observatory.lyrics.classification import LyricsClassification
from chart_observatory.lyrics.identity_quarantine import (
    load_quarantine_entries,
    load_suspended_sources,
)
from chart_observatory.lyrics.repository import AUTHORIZED_RIGHTS
from chart_observatory.lyrics.scientific_selection import assess_classification
from chart_observatory.lyrics.text_quality import TEXT_QUALITY_VERSION, prepare_lyric_derivative

ROOT = Path(__file__).resolve().parents[1]
BASE_SCHEMA = pa.schema([("record_json", pa.string())])
DERIVATIVE_SCHEMA = pa.schema(
    [
        (name, pa.string())
        for name in (
            "document_id",
            "track_id",
            "source",
            "rights_status",
            "original_sha256",
            "derivative_sha256",
            "version",
            "text",
        )
    ]
)
SELECTED_SCHEMA = pa.schema(
    [
        (name, pa.string())
        for name in (
            "document_id",
            "track_id",
            "snapshot_id",
            "original_sha256",
            "source",
            "model_id",
            "taxonomy_version",
            "prompt_version",
            "labels_json",
        )
    ]
    + [("confidence", pa.float64())]
)


class BufferedParquet:
    def __init__(self, path: Path, schema: pa.Schema):
        self.writer = pq.ParquetWriter(path, schema, compression="zstd")
        self.schema = schema
        self.rows: list[dict[str, Any]] = []

    def append(self, row: dict[str, Any]) -> None:
        self.rows.append(row)
        if len(self.rows) >= 1000:
            self.flush()

    def flush(self) -> None:
        if self.rows:
            self.writer.write_table(pa.Table.from_pylist(self.rows, schema=self.schema))
            self.rows.clear()

    def close(self) -> None:
        self.flush()
        self.writer.close()


def input_rows(path: Path | None, report: dict[str, Any]) -> Iterator[dict[str, Any]]:
    if path:
        report["input_mode"] = "local_fixture"
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)
        return
    engine = create_engine(Settings.load(ROOT).database_url)
    if engine.url.host != "127.0.0.1" or engine.url.port != 56433:
        raise ValueError("requires PostgreSQL 16 at 127.0.0.1:56433")
    try:
        with engine.connect() as conn:
            conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            version = int(conn.execute(text("SHOW server_version_num")).scalar_one())
            if not 160000 <= version < 170000:
                raise ValueError("requires PostgreSQL 16")
            report["snapshot_utc"] = str(
                conn.execute(text("SELECT transaction_timestamp()")).scalar()
            )
            report["input_mode"] = "postgresql_read_only"
            rows = (
                conn.execution_options(stream_results=True)
                .execute(
                    text("""
                WITH latest AS (
                  SELECT DISTINCT ON (lyric_document_id,model_id,taxonomy_version,prompt_version)
                    id,lyric_document_id,canonical_track_id,lyrics_hash,model_id,
                    taxonomy_version,prompt_version,classification_status,result_json,confidence,
                    input_tokens,output_tokens,estimated_cost_usd
                  FROM lyric_classification_snapshots
                  ORDER BY lyric_document_id,model_id,taxonomy_version,prompt_version,
                    append_order DESC
                )
                SELECT d.id AS document_id,d.canonical_track_id AS document_track_id,
                  d.text,d.content_sha256,d.source,d.rights_status,d.language_code,
                  s.id AS snapshot_id,s.canonical_track_id,s.lyrics_hash,s.model_id,
                  s.taxonomy_version,s.prompt_version,s.classification_status,s.result_json,
                  s.confidence,s.input_tokens,s.output_tokens,s.estimated_cost_usd
                FROM lyric_documents d LEFT JOIN latest s ON s.lyric_document_id=d.id
                ORDER BY d.id
            """)
                )
                .mappings()
            )
            for row in rows:
                yield dict(row)
            rows.close()
    finally:
        engine.dispose()


def run(input_path: Path | None, output: Path, minimum_confidence: float) -> dict[str, Any]:
    # Exclusive destination prevents accidental overwrite of evidence or corpus files.
    output.mkdir(parents=True, exist_ok=False)
    started = datetime.now(UTC)
    report: dict[str, Any] = {
        "version": TEXT_QUALITY_VERSION,
        "started_utc": started.isoformat(),
        "provider_calls": 0,
        "additional_api_cost_brl": "0",
        "evaluation_method": "automated_only",
        "human_evaluation_planned": False,
        "minimum_operational_confidence": minimum_confidence,
        "confidence_is_calibrated_accuracy": False,
        "derivatives_submitted_or_imported": False,
    }
    code_dir = output / "reproducibility"
    code_dir.mkdir()
    code_hashes = {}
    for source_path in (
        Path(__file__),
        ROOT / "src/chart_observatory/lyrics/text_quality.py",
        ROOT / "src/chart_observatory/lyrics/scientific_selection.py",
        ROOT / "src/chart_observatory/lyrics/classification.py",
        ROOT / "src/chart_observatory/lyrics/identity_quarantine.py",
        ROOT / "config/lyrics_identity_quarantine.json",
    ):
        content = source_path.read_bytes()
        (code_dir / source_path.name).write_bytes(content)
        code_hashes[source_path.name] = hashlib.sha256(content).hexdigest()
    report["reproducibility_sha256"] = code_hashes
    entries = {entry.lyric_document_id: entry for entry in load_quarantine_entries()}
    suspended = load_suspended_sources()
    counts: Counter[str] = Counter()
    transformations: Counter[str] = Counter()
    sources: dict[str, Counter[str]] = defaultdict(Counter)
    groups: dict[str, dict[str, Any]] = {}
    cleaned_groups: dict[str, set[str]] = defaultdict(set)
    base = BufferedParquet(output / "assessment-base.parquet", BASE_SCHEMA)
    derivatives = BufferedParquet(output / "text-derivatives.parquet", DERIVATIVE_SCHEMA)
    try:
        for row in input_rows(input_path, report):
            counts["documents"] += 1
            source = str(row["source"])
            sources[source]["documents"] += 1
            derivative = prepare_lyric_derivative(row.get("text") or "", source)
            reasons = list(derivative.flags)
            warnings: list[str] = []
            if row.get("language_code") is None:
                warnings.append("language_not_registered")
            if derivative.original_sha256 != row["content_sha256"]:
                reasons.append("stored_content_hash_mismatch")
            if row["rights_status"] not in AUTHORIZED_RIGHTS:
                reasons.append("rights_unauthorized")
            if "stored_content_hash_mismatch" not in reasons:
                cleaned_groups[derivative.derivative_sha256].add(str(row["document_track_id"]))
            if derivative.changed:
                reasons.append("classification_does_not_cover_derivative")
                counts["changed_documents"] += 1
                sources[source]["changed_documents"] += 1
                transformations.update(derivative.transformations)
                if not {"stored_content_hash_mismatch", "rights_unauthorized"}.intersection(
                    reasons
                ):
                    derivatives.append(
                        {
                            "document_id": str(row["document_id"]),
                            "track_id": str(row["document_track_id"]),
                            "source": source,
                            "rights_status": row["rights_status"],
                            "text": derivative.text,
                            "original_sha256": derivative.original_sha256,
                            "derivative_sha256": derivative.derivative_sha256,
                            "version": derivative.version,
                        }
                    )
                    counts["written_derivatives"] += 1
            document = SimpleNamespace(
                id=UUID(str(row["document_id"])),
                canonical_track_id=row["document_track_id"],
                content_sha256=row["content_sha256"],
                source=source,
                rights_status=row["rights_status"],
            )
            snapshot = SimpleNamespace(
                canonical_track_id=row.get("canonical_track_id"),
                lyrics_hash=row.get("lyrics_hash"),
                classification_status=row.get("classification_status"),
                result_json=row.get("result_json"),
            )
            entry = entries.get(document.id)
            eligibility = assess_classification(
                document, snapshot, entries=(entry,) if entry else (), suspended_sources=suspended
            )
            # Source suspension is scientific; the full-corpus authorization permits exploration.
            for reason in eligibility.reasons:
                (
                    warnings if reason in {"identity_unverified", "source_suspended"} else reasons
                ).append(reason)
            labels = None
            confidence = None
            group_key = None
            if row.get("classification_status") == "classified":
                counts["classified"] += 1
                try:
                    result = LyricsClassification.model_validate(row.get("result_json"))
                    confidence = result.confidence
                    labels = result.model_dump(
                        mode="json", exclude={"confidence", "romantic_summary"}
                    )
                    labels["gender_representation"]["representation_roles"].sort()
                    if confidence < minimum_confidence:
                        reasons.append("confidence_below_operational_threshold")
                    if (
                        row.get("confidence") is None
                        or abs(float(row["confidence"]) - confidence) > 1e-6
                    ):
                        reasons.append("confidence_metadata_mismatch")
                    if any(
                        row.get(name) is None
                        for name in (
                            "input_tokens",
                            "output_tokens",
                            "estimated_cost_usd",
                        )
                    ):
                        reasons.append("missing_usage_or_cost")
                    for coding in labels["antisocial"].values():
                        if coding["intensity"] == 0 and coding["stance"] != "neutral":
                            reasons.append("stance_without_intensity")
                    if not {
                        "stored_content_hash_mismatch",
                        "hash_mismatch",
                        "track_mismatch",
                    }.intersection(reasons):
                        group_key = json.dumps(
                            [
                                row["content_sha256"],
                                row.get("model_id"),
                                row.get("taxonomy_version"),
                                row.get("prompt_version"),
                            ]
                        )
                        signature = hashlib.sha256(
                            json.dumps(labels, sort_keys=True).encode()
                        ).hexdigest()
                        group = groups.setdefault(
                            group_key, {"tracks": set(), "signatures": set(), "count": 0}
                        )
                        group["tracks"].add(str(row["document_track_id"]))
                        group["signatures"].add(signature)
                        group["count"] += 1
                except ValidationError:
                    reasons.append("invalid_result")
            base.append(
                {
                    "record_json": json.dumps(
                        {
                            "document_id": str(row["document_id"]),
                            "track_id": str(row["document_track_id"]),
                            "snapshot_id": str(row["snapshot_id"])
                            if row.get("snapshot_id")
                            else None,
                            "source": source,
                            "rights_status": row["rights_status"],
                            "original_sha256": derivative.original_sha256,
                            "derivative_sha256": derivative.derivative_sha256,
                            "text_changed": derivative.changed,
                            "transformations": derivative.transformations,
                            "text_flags": derivative.flags,
                            "blocking_reasons": sorted(set(reasons) - {"short_text"}),
                            "warnings": sorted(
                                set(warnings)
                                | ({"short_text"} if "short_text" in reasons else set())
                            ),
                            "original_scientific_eligible": eligibility.primary_eligible,
                            "model_id": row.get("model_id"),
                            "taxonomy_version": row.get("taxonomy_version"),
                            "prompt_version": row.get("prompt_version"),
                            "confidence": confidence,
                            "labels": labels,
                            "group_key": group_key,
                        },
                        ensure_ascii=False,
                    )
                }
            )
    finally:
        base.close()
        derivatives.close()
    shared = {key: group for key, group in groups.items() if len(group["tracks"]) > 1}
    divergent = {key for key, group in shared.items() if len(group["signatures"]) > 1}
    report["duplicate_groups"] = len(shared)
    report["duplicate_groups_with_label_disagreement"] = len(divergent)
    cleaned_shared = {key for key, tracks in cleaned_groups.items() if len(tracks) > 1}
    report["cleaned_text_groups_across_tracks"] = len(cleaned_shared)
    blocked: Counter[str] = Counter()
    warning_counts: Counter[str] = Counter()
    selected = BufferedParquet(output / "operational-classifications.parquet", SELECTED_SCHEMA)
    try:
        with (output / "quality-manifest.jsonl").open("x", encoding="utf-8") as manifest:
            for batch in pq.ParquetFile(output / "assessment-base.parquet").iter_batches(
                batch_size=1000
            ):
                for raw in batch.column(0).to_pylist():
                    record = json.loads(raw)
                    labels = record.pop("labels")
                    group_key = record.pop("group_key")
                    if group_key in shared:
                        record["warnings"].append("identical_text_across_track_identities")
                    if record["derivative_sha256"] in cleaned_shared:
                        record["warnings"].append("cleaned_text_across_track_identities")
                    if group_key in divergent:
                        record["blocking_reasons"].append("duplicate_text_label_disagreement")
                    eligible = not record["blocking_reasons"]
                    record["automated_operational_eligible"] = eligible
                    record["version"] = TEXT_QUALITY_VERSION
                    record["evaluation_method"] = "automated_only"
                    manifest.write(json.dumps(record, ensure_ascii=False) + "\n")
                    blocked.update(record["blocking_reasons"])
                    warning_counts.update(record["warnings"])
                    counts["automated_operational_eligible"] += eligible
                    sources[record["source"]]["automated_operational_eligible"] += eligible
                    if eligible:
                        selected.append(
                            {
                                name: record[name]
                                for name in SELECTED_SCHEMA.names
                                if name != "labels_json"
                            }
                            | {"labels_json": json.dumps(labels, ensure_ascii=False)}
                        )
    finally:
        selected.close()
    report.update(
        counts=dict(counts),
        transformations=dict(transformations),
        blocking_reason_counts=dict(blocked),
        warning_counts=dict(warning_counts),
        source_counts={source: dict(values) for source, values in sources.items()},
        finished_utc=datetime.now(UTC).isoformat(),
        elapsed_seconds=(datetime.now(UTC) - started).total_seconds(),
    )
    (output / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-jsonl", type=Path, help="Local fixture; default is read-only PostgreSQL"
    )
    parser.add_argument("--output-dir", type=Path, required=True, help="New exclusive directory")
    parser.add_argument("--minimum-confidence", type=float, default=0.8)
    args = parser.parse_args()
    if not 0 <= args.minimum_confidence <= 1:
        parser.error("minimum confidence must be between zero and one")
    print(json.dumps(run(args.input_jsonl, args.output_dir, args.minimum_confidence), indent=2))


if __name__ == "__main__":
    main()
