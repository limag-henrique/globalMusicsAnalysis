"""Strictly reassess a completed lyric recovery staging run.

The audit is read-only against the staging database and native metadata stores.
It never updates approval fields and never treats provider/source checks as
audio-to-transcription proof.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from recover_low_coverage_lyrics import load_baseline

from chart_observatory.lyrics.automated_validation import assess_lyric_identity_completeness
from chart_observatory.lyrics.quota_acquisition import identities_compatible
from chart_observatory.lyrics.text_quality import (
    prepare_lyric_derivative,
    recording_duration_mismatch,
)
from chart_observatory.runtime_status import publish_status

ROOT = Path(__file__).resolve().parents[1]


def latest_native_proofs(paths: list[Path], candidate_ids: set[str]):
    proofs = {}
    sources = []
    for path in paths:
        resolved = path.resolve()
        with sqlite3.connect(resolved.as_uri() + "?mode=ro", uri=True) as db:
            for candidate_id, raw in db.execute("SELECT candidate_id,proof FROM evidence"):
                if candidate_id not in candidate_ids:
                    continue
                proof = json.loads(raw)
                if proof.get("retrieved_at", "") > proofs.get(candidate_id, {}).get(
                    "retrieved_at", ""
                ):
                    proofs[candidate_id] = proof
        sources.append(
            dict(path=str(resolved), sha256=hashlib.sha256(resolved.read_bytes()).hexdigest())
        )
    return proofs, sources


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--metadata-db", action="append", type=Path, default=[])
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    paths = [args.staging, args.out, *args.metadata_db]
    if not all(path.resolve().is_relative_to(ROOT) for path in paths):
        raise ValueError("audit paths must remain within the project")
    if args.out.exists():
        raise FileExistsError(args.out)
    args.out.mkdir(parents=True)

    records, texts = load_baseline(args.staging, args.run_id)
    proofs, sources = latest_native_proofs(args.metadata_db, set(records))
    counts = Counter()
    flag_counts = Counter()
    decisions_path = args.out / "decisions.jsonl"
    with decisions_path.open("w", encoding="utf-8", newline="\n") as output:
        for candidate_id, record in sorted(records.items()):
            body = texts.get(record.get("text_sha256"))
            audit = record.setdefault("audit", {})
            flags = set(audit.get("text_quality_flags") or [])
            # Recompute native evidence flags from the selected proof snapshot.
            # The staged audit may still carry a prior "proof missing" flag even
            # after a later, exact native-ID fetch has been collected.
            flags.difference_update(
                {
                    "native_recording_proof_missing",
                    "native_title_disagreement",
                    "native_artist_disagreement",
                    "recording_duration_mismatch",
                }
            )
            if body is not None:
                flags.update(
                    prepare_lyric_derivative(
                        body, record["source_result"].get("source", "UNKNOWN")
                    ).flags
                )
            native = proofs.get(candidate_id) or {}
            metadata = native.get("metadata") or {}
            native_ok = (
                native.get("status") == 200
                and metadata.get("uri")
                == candidate_id.replace("SPOTIFY:", "spotify:track:")
                and native.get("source_url")
                == "https://open.spotify.com/embed/track/"
                + candidate_id.removeprefix("SPOTIFY:")
            )
            if native_ok:
                for field in ("title", "artist"):
                    if not identities_compatible(
                        record["payload"].get(field),
                        metadata.get(field),
                        is_artist=field == "artist",
                    ):
                        flags.add("native_" + field + "_disagreement")
                duration = metadata.get("duration_ms")
                if duration:
                    record["payload"].setdefault("metadata_resolution", {})[
                        "duration_ms"
                    ] = duration
                if recording_duration_mismatch(
                    duration,
                    (record["source_result"].get("source_metadata") or {}).get(
                        "duration_seconds"
                    ),
                ):
                    flags.add("recording_duration_mismatch")
            else:
                flags.add("native_recording_proof_missing")
            audit["text_quality_flags"] = sorted(flags)
            previous = audit.get("automated_validation") or {}
            integrity = previous.get("source_text_integrity") or {}
            evidence = previous.get("source_chain_evidence") or {}
            chain = dict(
                status=integrity.get("source_chain_status"),
                extracted_text_sha256=integrity.get("replayed_text_sha256"),
                exact_text_hash_match=integrity.get("exact_replay_hash_match"),
                evidence_sha256=integrity.get("raw_response_sha256"),
                source_url=evidence.get("source_url"),
            )
            decision = assess_lyric_identity_completeness(record, body, chain)
            native_conflicts = sorted(
                flag
                for flag in flags
                if flag.startswith("native_") or flag == "recording_duration_mismatch"
            )
            identity_supported = decision["identity"]["status"] == "passed" and not native_conflicts
            completeness_supported = decision["completeness"]["status"] == "passed"
            counts["candidates"] += 1
            counts["identity_supported"] += identity_supported
            counts["source_completeness_supported"] += completeness_supported
            counts["both_source_checks_supported"] += identity_supported and completeness_supported
            counts["recording_transcription_effectively_proven"] += 0
            flag_counts.update(flags)
            output.write(
                json.dumps(
                    dict(
                        candidate_id=candidate_id,
                        text_sha256=record.get("text_sha256"),
                        identity_supported=identity_supported,
                        source_completeness_supported=completeness_supported,
                        recording_transcription_proven=False,
                        native_conflicts=native_conflicts,
                        flags=sorted(flags),
                        decision=decision,
                    ),
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
            )
    summary = dict(
        schema_version="recovery-staging-strict-audit-v1",
        created_at=datetime.now(UTC).isoformat(),
        staging=str(args.staging.resolve()),
        staging_sha256=hashlib.sha256(args.staging.read_bytes()).hexdigest(),
        run_id=args.run_id,
        candidate_count=len(records),
        text_hashes_verified=len(texts),
        counts=dict(counts),
        percentages={
            name: (100 * counts[name] / len(records) if records else None)
            for name in (
                "identity_supported",
                "source_completeness_supported",
                "both_source_checks_supported",
            )
        },
        quality_flags=dict(flag_counts),
        native_metadata_sources=sources,
        recording_transcription_effectively_proven=0,
        scientific_approvals=0,
        classification_ready=0,
        note=(
            "These checks support lyric-provider identity and source-field completeness only; "
            "they do not prove that the transcription matches the identified recording."
        ),
    )
    publish_status(args.out / "summary.json", summary)


if __name__ == "__main__":
    main()
