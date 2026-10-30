"""Summarize a live recovery ledger without loading lyric bodies into the report."""

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path


def summarize(targets: Path, ledger: Path):
    expected = set()
    identities = {}
    for line in targets.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        key = (row["document_id"], row["lyrics_hash"])
        expected.add(key)
        identities[key] = (row.get("track_id") or row["document_id"], row["lyrics_hash"])
    latest = {}
    incomplete_tail = False
    if ledger.exists():
        with ledger.open("rb") as handle:
            for line in handle:
                if not line.endswith(b"\n"):
                    incomplete_tail = True
                    break
                if not line.strip():
                    continue
                row = json.loads(line)
                bindings = row.get("original_bindings") or [{
                    "document_id": row["original_document_id"],
                    "lyrics_hash": row["original_lyrics_hash"],
                }]
                record = {
                    "status": row["status"], "variants": len(row.get("variants", [])),
                    "agreement": row.get("cross_source_text_agreement"),
                }
                for binding in bindings:
                    key = (binding["document_id"], binding["lyrics_hash"])
                    if key in expected:
                        latest[key] = record
    statuses = Counter(row["status"] for row in latest.values())
    processed = sum(row["status"] != "http_error" for row in latest.values())
    recordings = {identities[key]: row for key, row in latest.items()}
    return {
        "observed_at": datetime.now(UTC).isoformat(),
        "target_documents": len(expected), "observed_documents": len(latest),
        "processed_documents": processed, "pending_documents": len(expected) - processed,
        "status_counts_by_document": dict(statuses),
        "observed_recording_signatures": len(recordings),
        "candidate_variants_by_recording": sum(row["variants"] for row in recordings.values()),
        "multi_source_recordings": sum(row["variants"] > 1 for row in recordings.values()),
        "word_sequence_agreements": sum(row["agreement"] is True for row in recordings.values()),
        "word_sequence_disagreements": sum(
            row["agreement"] is False for row in recordings.values()
        ),
        "incomplete_tail_observed": incomplete_tail,
        "collection_complete": processed == len(expected) and not incomplete_tail,
        "candidate_is_validated": False, "article_regenerated": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = summarize(args.targets, args.ledger)
    if args.output:
        temporary = args.output.with_suffix(".tmp")
        temporary.write_text(json.dumps(result, indent=2), encoding="utf-8")
        temporary.replace(args.output)
    print(json.dumps(result, indent=2))
