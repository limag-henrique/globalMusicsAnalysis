"""Recheck cached lyric evidence, classify identity/completeness, and persist results."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine

from chart_observatory.config import Settings
from chart_observatory.lyrics.automated_validation import (
    VALIDATION_VERSION,
    assess_lyric_identity_completeness,
)
from chart_observatory.lyrics.inventory_export import rebuild_inventory_outputs
from chart_observatory.lyrics.quota_discovery import audit_saved_result
from chart_observatory.lyrics.recovery_pipeline import (
    fetch_postgres_cohort_metrics,
    load_sqlite_staging_snapshot,
    persist_verified_staging,
)
from chart_observatory.lyrics.source_chain import verify_source_chain

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT / "data/runtime/antigravity-collaboration-20261115/pipeline-run-20261115"
V4_SELECTION = ROOT / "data/derived/annual_revision/global-rescan-2018-2026-20261111-v4-final-0002"
V5_SELECTION = (
    ROOT
    / "data/derived/annual_revision/global-rescan-2018-2026-20261115-v5-published-provisional-0003"
)
OUTPUT_DIR = ROOT / "outputs/inventario-musicas-pais-ano-20261115"


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _save_checkpoint(path: Path, records: dict[str, dict], texts: dict[str, str]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    digest = hashlib.sha256()
    with tmp.open("w", encoding="utf-8", newline="") as file:
        for chunk in json.JSONEncoder(ensure_ascii=False, separators=(",", ":")).iterencode(
            {"records": records, "texts": texts}
        ):
            file.write(chunk)
            digest.update(chunk.encode("utf-8"))
    tmp.replace(path)
    return digest.hexdigest()


def _verify_one(record: dict[str, Any], text: str | None) -> dict[str, Any]:
    if text is None:
        return {"status": "unavailable"}
    result = record.get("source_result") or {}
    if not result.get("http_evidence"):
        return {"status": "no_http_evidence_recorded"}
    try:
        return verify_source_chain(
            record.get("payload") or {}, result, text, record.get("text_sha256"), ROOT
        )
    except Exception as error:  # Preserve a per-record failure instead of dropping the cohort.
        return {"status": "validator_error", "error_type": type(error).__name__}


def _assess_scope(
    *,
    scope: str,
    input_path: Path,
    checkpoint_path: Path,
    evidence_path: Path,
    workers: int,
) -> tuple[dict[str, dict], dict[str, str], dict[str, Any]]:
    if checkpoint_path.exists() and evidence_path.exists():
        data = _load_json(checkpoint_path)
        records: dict[str, dict] = data["records"]
        texts: dict[str, str] = data["texts"]
        if any(
            ((record.get("audit") or {}).get("automated_validation") or {}).get("schema_version")
            != VALIDATION_VERSION
            for record in records.values()
        ):
            raise ValueError(
                "Incompatible validation checkpoint; preserve it and run a fresh versioned campaign"
            )
        identity_counts: Counter[str] = Counter()
        completeness_counts: Counter[str] = Counter()
        overall_counts: Counter[str] = Counter()
        integrity_counts: Counter[str] = Counter()
        provider_counts: Counter[str] = Counter()
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        with evidence_path.open("w", encoding="utf-8", newline="") as evidence_file:
            for candidate_id in sorted(records):
                record = records[candidate_id]
                audit = record.setdefault("audit", {})
                previous = audit.get("automated_validation") or {}
                previous_integrity = previous.get("source_text_integrity") or {}
                previous_evidence = previous.get("source_chain_evidence") or {}
                chain = {
                    "status": previous_integrity.get("source_chain_status", "unavailable"),
                    "extracted_text_sha256": previous_integrity.get("replayed_text_sha256"),
                    "exact_text_hash_match": previous_integrity.get("exact_replay_hash_match")
                    is True,
                    "evidence_sha256": previous_integrity.get("raw_response_sha256"),
                    "source_url": previous_evidence.get("source_url"),
                    "errors": previous_evidence.get("errors", []),
                    "error_type": previous_evidence.get("validator_error_type"),
                }
                digest = record.get("text_sha256")
                body = texts.get(digest) if digest else None
                validation = assess_lyric_identity_completeness(record, body, chain)
                validation["assessed_at"] = (
                    previous.get("assessed_at") or datetime.now(UTC).isoformat()
                )
                validation["source_chain_evidence"] = previous_evidence
                audit["automated_validation"] = validation
                identity_counts[validation["identity"]["status"]] += 1
                completeness_counts[validation["completeness"]["status"]] += 1
                overall_counts[validation["automated_overall"]] += 1
                integrity_counts[validation["source_text_integrity"]["status"]] += 1
                provider = (record.get("source_result") or {}).get("source") or "UNKNOWN"
                provider_counts[provider] += 1
                evidence_file.write(
                    json.dumps(
                        {
                            "scope": scope,
                            "candidate_id": candidate_id,
                            "title": (record.get("payload") or {}).get("title"),
                            "artist": (record.get("payload") or {}).get("artist"),
                            "source": provider,
                            "text_sha256": digest,
                            "validation": validation,
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    + "\n"
                )
        checkpoint_sha256 = _save_checkpoint(checkpoint_path, records, texts)
        summary = {
            "scope": scope,
            "validation_schema": VALIDATION_VERSION,
            "assessed_at": datetime.now(UTC).isoformat(),
            "candidate_count": len(records),
            "candidate_count_with_text": sum(bool(r.get("text_sha256")) for r in records.values()),
            "identity_passed": identity_counts["passed"],
            "identity_pending": identity_counts["pending"],
            "identity_failed": identity_counts["failed"],
            "completeness_passed": completeness_counts["passed"],
            "completeness_pending": completeness_counts["pending"],
            "completeness_failed": completeness_counts["failed"],
            "both_passed": overall_counts["passed"],
            "integrity_passed": integrity_counts["passed"],
            "providers": dict(provider_counts),
            "checkpoint_path": str(checkpoint_path),
            "checkpoint_sha256": checkpoint_sha256,
            "record_evidence_jsonl": str(evidence_path),
            "record_evidence_sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
            "resumed_without_reextracting": True,
            "reclassified_using_cached_raw_evidence": True,
        }
        return records, texts, summary

    data = _load_json(input_path)
    records: dict[str, dict] = data["records"]
    texts: dict[str, str] = data["texts"]
    ids = sorted(records)
    counts: Counter[str] = Counter()
    provider_counts: Counter[str] = Counter()
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC).isoformat()

    def jobs():
        for candidate_id in ids:
            record = records[candidate_id]
            digest = record.get("text_sha256")
            yield record, texts.get(digest) if digest else None

    with (
        evidence_path.open("w", encoding="utf-8", newline="") as evidence_file,
        ThreadPoolExecutor(max_workers=workers, thread_name_prefix="lyric-evidence") as pool,
    ):
        for index, ((candidate_id, record), chain) in enumerate(
            zip(
                ((cid, records[cid]) for cid in ids),
                pool.map(lambda pair: _verify_one(*pair), jobs()),
                strict=True,
            ),
            start=1,
        ):
            body = texts.get(record.get("text_sha256")) if record.get("text_sha256") else None
            audit = record.setdefault("audit", {})
            saved_audit = audit_saved_result(
                record.get("payload") or {}, record.get("source_result") or {}
            )
            flags = sorted(
                set(audit.get("text_quality_flags") or [])
                | set(saved_audit.get("text_quality_flags") or [])
            )
            audit["text_quality_flags"] = flags
            audit["source_quarantined"] = bool(
                audit.get("source_quarantined") or saved_audit.get("source_quarantined")
            )
            assessment = assess_lyric_identity_completeness(record, body, chain)
            assessment["assessed_at"] = now
            assessment["source_chain_evidence"] = {
                "source_url": chain.get("source_url"),
                "errors": chain.get("errors", []),
                "validator_error_type": chain.get("error_type"),
            }
            audit["automated_validation"] = assessment
            provider = (record.get("source_result") or {}).get("source") or "UNKNOWN"
            provider_counts[provider] += 1
            counts[f"identity_{assessment['identity']['status']}"] += 1
            counts[f"completeness_{assessment['completeness']['status']}"] += 1
            counts[f"overall_{assessment['automated_overall']}"] += 1
            counts[f"integrity_{assessment['source_text_integrity']['status']}"] += 1
            if record.get("text_sha256"):
                counts["candidates_with_text"] += 1
            counts["candidates_total"] += 1
            evidence_file.write(
                json.dumps(
                    {
                        "scope": scope,
                        "candidate_id": candidate_id,
                        "title": (record.get("payload") or {}).get("title"),
                        "artist": (record.get("payload") or {}).get("artist"),
                        "source": provider,
                        "text_sha256": record.get("text_sha256"),
                        "validation": assessment,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n"
            )
            if index % 5000 == 0:
                print(f"{scope}: assessed {index:,}/{len(ids):,}", flush=True)

    checkpoint_sha256 = _save_checkpoint(checkpoint_path, records, texts)
    counts["candidates_total"] = len(records)
    counts["candidates_with_text"] = sum(bool(r.get("text_sha256")) for r in records.values())
    summary = {
        "scope": scope,
        "validation_schema": VALIDATION_VERSION,
        "assessed_at": now,
        "candidate_count": len(records),
        "candidate_count_with_text": counts["candidates_with_text"],
        "identity_passed": counts["identity_passed"],
        "identity_pending": counts["identity_pending"],
        "identity_failed": counts["identity_failed"],
        "completeness_passed": counts["completeness_passed"],
        "completeness_pending": counts["completeness_pending"],
        "completeness_failed": counts["completeness_failed"],
        "both_passed": counts["overall_passed"],
        "integrity_passed": counts["integrity_passed"],
        "providers": dict(provider_counts),
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_sha256": checkpoint_sha256,
        "record_evidence_jsonl": str(evidence_path),
        "record_evidence_sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
    }
    return records, texts, summary


def _verify_mirror(sqlite_path: Path, run_id: str, output_path: Path) -> dict[str, Any]:
    command = [
        sys.executable,
        str(ROOT / "scripts/verify_lyric_staging_mirror.py"),
        "--local-staging",
        str(sqlite_path),
        "--run-id",
        run_id,
        "--out",
        str(output_path),
    ]
    subprocess.run(command, cwd=ROOT, check=True, env=os.environ.copy())
    return _load_json(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, default=CAMPAIGN)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--workers", type=int, default=8, choices=range(1, 17))
    args = parser.parse_args()
    # BaseSettings reads .env relative to the process working directory.
    os.chdir(ROOT)
    campaign = args.campaign_dir.resolve()
    output_dir = args.output_dir.resolve()
    if not campaign.is_relative_to(ROOT) or not output_dir.is_relative_to(ROOT):
        raise ValueError("output paths must remain inside the repository")
    checkpoint_dir = campaign / "checkpoints"
    run_dir = campaign / "automated-validation-v1"
    run_dir.mkdir(parents=True, exist_ok=True)

    v4_records, v4_texts, v4_summary = _assess_scope(
        scope="v4",
        input_path=checkpoint_dir / "v4_verified.json",
        checkpoint_path=checkpoint_dir / "v4_automated_validated.json",
        evidence_path=run_dir / "v4-record-validations.jsonl",
        workers=args.workers,
    )
    v5_records, v5_texts, v5_summary = _assess_scope(
        scope="v5",
        input_path=checkpoint_dir / "v5_verified.json",
        checkpoint_path=checkpoint_dir / "v5_automated_validated.json",
        evidence_path=run_dir / "v5-record-validations.jsonl",
        workers=args.workers,
    )

    engine = create_engine(Settings.load(ROOT).database_url, connect_args={"connect_timeout": 15})
    try:
        v4_manifest = _load_json(V4_SELECTION / "manifest.json")
        v5_manifest = _load_json(V5_SELECTION / "manifest.json")
        v4_persist = persist_verified_staging(
            list(v4_records.values()),
            v4_texts,
            selection_dir=V4_SELECTION,
            local_sqlite_path=run_dir / "staging-v4/pending-staging.sqlite",
            pg_engine=engine,
            phase=VALIDATION_VERSION + "-v4",
            memberships_count=v4_manifest["memberships"],
            extra_manifest={
                "updated_at": datetime.now(UTC).isoformat(),
                "selection_version": "v4-final-0002",
                "automated_validation_schema": VALIDATION_VERSION,
                "automated_identity_passed": v4_summary["identity_passed"],
                "automated_completeness_passed": v4_summary["completeness_passed"],
                "automated_both_passed": v4_summary["both_passed"],
            },
        )
        v5_persist = persist_verified_staging(
            list(v5_records.values()),
            v5_texts,
            selection_dir=V5_SELECTION,
            local_sqlite_path=run_dir / "staging-v5/pending-staging.sqlite",
            pg_engine=engine,
            phase=VALIDATION_VERSION + "-v5-provisional",
            memberships_count=v5_manifest["memberships"],
            extra_manifest={
                "updated_at": datetime.now(UTC).isoformat(),
                "selection_version": "v5-published-provisional-0003",
                "automated_validation_schema": VALIDATION_VERSION,
                "automated_identity_passed": v5_summary["identity_passed"],
                "automated_completeness_passed": v5_summary["completeness_passed"],
                "automated_both_passed": v5_summary["both_passed"],
            },
        )
        v4_mirror = _verify_mirror(
            Path(v4_persist["local_sqlite"]),
            v4_persist["run_id"],
            run_dir / "v4-mirror-verification.json",
        )
        v5_mirror = _verify_mirror(
            Path(v5_persist["local_sqlite"]),
            v5_persist["run_id"],
            run_dir / "v5-mirror-verification.json",
        )
        cohort_metrics = fetch_postgres_cohort_metrics(engine)
        _, snapshot_created_at, _, _ = load_sqlite_staging_snapshot(
            Path(v4_persist["local_sqlite"]), v4_persist["run_id"]
        )
        inventory = rebuild_inventory_outputs(
            output_dir,
            v4_selection_dir=V4_SELECTION,
            v5_selection_dir=V5_SELECTION,
            v4_run_id=v4_persist["run_id"],
            v5_run_id=v5_persist["run_id"],
            snapshot_created_at=snapshot_created_at,
            v4_records_by_id=v4_records,
            v5_records_by_id=v5_records,
            cohort_metrics=cohort_metrics,
        )
    finally:
        engine.dispose()

    summary = {
        "schema_version": "automated-lyrics-validation-run-v1",
        "validation_schema": VALIDATION_VERSION,
        "assessed_at": datetime.now(UTC).isoformat(),
        "method": {
            "network_requests": 0,
            "raw_http_evidence_replayed_from_cache": True,
            "automated_identity_scope": "provider song title and billed performer credits",
            "automated_completeness_scope": "provider full lyrics field/container replay",
            "scientific_g2_approval": False,
            "recording_audio_identity_proven": False,
            "rights_cleared": False,
            "vertex_ready": False,
        },
        "v4": v4_summary,
        "v5": v5_summary,
        "staging": {
            "v4_run_id": v4_persist["run_id"],
            "v5_run_id": v5_persist["run_id"],
            "v4_mirror": v4_mirror,
            "v5_mirror": v5_mirror,
        },
        "inventory": inventory,
    }
    summary_path = run_dir / "validation-summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    copilot_handoff = {
        "schema_version": "copilot-automated-lyrics-validation-handoff-v1",
        "created_at": summary["assessed_at"],
        "handoff_peer": "GitHub Copilot (versioned file handoff; no direct IPC)",
        "summary_path": str(summary_path),
        "validation_schema": VALIDATION_VERSION,
        "v4": v4_summary,
        "v5": v5_summary,
        "staging_runs": summary["staging"],
        "required_review": [
            "Check the automated identity/completeness criteria and their failure queues.",
            "Keep G2 separate; staging identity_validated/completeness_validated remain false.",
            "Do not label source-field replay as audio-to-recording transcription verification.",
        ],
    }
    handoff_path = run_dir / "copilot-handoff-automated-validation.json"
    handoff_path.write_text(
        json.dumps(copilot_handoff, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
