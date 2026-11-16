"""Reassess frozen candidates with native proofs; never reuse a prior pass verdict."""

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path

from chart_observatory.lyrics.automated_validation import assess_lyric_identity_completeness
from chart_observatory.lyrics.quota_acquisition import identities_compatible
from chart_observatory.lyrics.text_quality import (
    prepare_lyric_derivative,
    recording_duration_mismatch,
)

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT / "data/runtime/antigravity-collaboration-20261115/pipeline-run-20261116-remediated"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, default=CAMPAIGN)
    parser.add_argument("--output-subdir", default="tech-remediation-strict-v3")
    parser.add_argument("--checkpoint-suffix", default="verified")
    args = parser.parse_args()
    campaign = args.campaign_dir.resolve()
    if not campaign.is_relative_to(ROOT):
        raise ValueError("campaign_dir must remain inside repository")
    output = campaign / args.output_subdir
    output.mkdir(exist_ok=True)
    proofs = {}
    for path in sorted((ROOT / "data/raw/metadata_resolution").glob("*/native-metadata.sqlite")):
        with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5.0) as db:
            for cid, raw in db.execute("SELECT candidate_id,proof FROM evidence"):
                proof = json.loads(raw)
                if proof.get("retrieved_at", "") > proofs.get(cid, {}).get("retrieved_at", ""):
                    proofs[cid] = proof
    summary = {}
    for scope in ("v4", "v5"):
        input_path = campaign / f"checkpoints/{scope}_{args.checkpoint_suffix}.json"
        with input_path.open(encoding="utf-8") as file:
            snapshot = json.load(file)
        counts = Counter()
        with (output / f"{scope}-strict-decisions.jsonl").open("w", encoding="utf-8") as file:
            for cid, rec in snapshot["records"].items():
                body = snapshot["texts"].get(rec.get("text_sha256"))
                audit = rec.setdefault("audit", {})
                flags = set(audit.get("text_quality_flags") or [])
                if body is not None:
                    flags.update(
                        prepare_lyric_derivative(
                            body, rec["source_result"].get("source", "UNKNOWN")
                        ).flags
                    )
                native = proofs.get(cid) or {}
                meta = native.get("metadata") or {}
                native_ok = (
                    native.get("status") == 200
                    and meta.get("uri") == cid.replace("SPOTIFY:", "spotify:track:")
                    and native.get("source_url")
                    == "https://open.spotify.com/embed/track/" + cid.removeprefix("SPOTIFY:")
                )
                if native_ok:
                    for field in ("title", "artist"):
                        if not identities_compatible(
                            rec["payload"].get(field), meta.get(field), is_artist=field == "artist"
                        ):
                            flags.add("native_" + field + "_disagreement")
                    duration = meta.get("duration_ms")
                    if duration:
                        rec["payload"].setdefault("metadata_resolution", {})["duration_ms"] = (
                            duration
                        )
                    if recording_duration_mismatch(
                        duration,
                        (rec["source_result"].get("source_metadata") or {}).get("duration_seconds"),
                    ):
                        flags.add("recording_duration_mismatch")
                else:
                    flags.add("native_recording_proof_missing")
                audit["text_quality_flags"] = sorted(flags)
                old = audit.get("automated_validation") or {}
                integrity = old.get("source_text_integrity") or {}
                evidence = old.get("source_chain_evidence") or {}
                chain = dict(
                    status=integrity.get("source_chain_status"),
                    extracted_text_sha256=integrity.get("replayed_text_sha256"),
                    exact_text_hash_match=integrity.get("exact_replay_hash_match"),
                    evidence_sha256=integrity.get("raw_response_sha256"),
                    source_url=evidence.get("source_url"),
                )
                result = assess_lyric_identity_completeness(rec, body, chain)
                native_conflicts = sorted(
                    f
                    for f in flags
                    if f.startswith("native_") or f == "recording_duration_mismatch"
                )
                identity_supported = (
                    result["identity"]["status"] == "passed" and not native_conflicts
                )
                complete_source = result["completeness"]["status"] == "passed"
                counts["candidates"] += 1
                counts["identity_supported"] += identity_supported
                counts["source_complete_supported"] += complete_source
                counts["both_source_checks_supported"] += identity_supported and complete_source
                counts["recording_and_transcription_effectively_proven"] += 0
                counts.update(flags)
                file.write(
                    json.dumps(
                        dict(
                            candidate_id=cid,
                            text_sha256=rec.get("text_sha256"),
                            identity_supported=identity_supported,
                            source_completeness_supported=complete_source,
                            recording_transcription_proven=False,
                            native_conflicts=native_conflicts,
                            flags=sorted(flags),
                            decision=result,
                        ),
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        summary[scope] = dict(counts)
        summary[scope]["input_sha256"] = hashlib.sha256(input_path.read_bytes()).hexdigest()
        del snapshot
    summary["limitations"] = (
        "Reassesses saved raw-evidence replay results; no fresh source replay or audio comparison. "
        "Prior 80% claims are not accepted as recording-transcription proof."
    )
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
