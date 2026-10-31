"""Export a read-only, scoped review inventory; never approve or alter source data."""

import argparse
import hashlib
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from chart_observatory.ingestion.import_quotas import (
    apply_native_display_metadata,
    load_quotas,
    recovery_targets,
)
from chart_observatory.lyrics.quota_acquisition import identity
from chart_observatory.lyrics.quota_discovery import audit_saved_result
from chart_observatory.lyrics.quota_eligibility import prepare_quota_review

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/derived/annual_revision/audited-calendars-2018-2026-20261031"
STORE = ROOT / "data/derived/lyrics/quota-20261030"


def read_rows(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def export():
    selected = read_rows(BASE / "combined.jsonl")
    enriched = json.loads((BASE / "metadata-enrichment.json").read_text(encoding="utf-8"))
    for row in selected:
        metadata = enriched.get("resolved", {}).get(row["candidate_id"])
        if metadata:
            for field in ("title", "artist"):
                if not row.get(field):
                    row[field] = metadata[field]
            row["metadata_resolution"] = metadata
    display_path = BASE / "native-display-metadata.json"
    if display_path.exists():
        apply_native_display_metadata(
            selected, json.loads(display_path.read_text(encoding="utf-8"))
        )
    targets = recovery_targets(selected)
    native = {
        row["candidate_id"]: row
        for row in read_rows(BASE / "youtube-native-evidence/native-identity-map.jsonl")
    }
    changed_credits = defaultdict(list)
    for row in read_rows(BASE / "youtube-changed-credits/pending-credit-review.jsonl"):
        changed_credits[row["candidate_id"]].append(row)
    with sqlite3.connect(
        f"file:{(STORE / 'acquisition.sqlite').as_posix()}?mode=ro", uri=True
    ) as db:
        stored = {
            key: (json.loads(payload), state, json.loads(result) if result else {})
            for key, payload, state, result in db.execute(
                "SELECT identity,payload,status,result FROM tasks"
            )
        }
    output = STORE / "review-inventory"
    output.mkdir(exist_ok=True)
    # This inventory has no adjudicated recording/document bindings. Never infer
    # one from a successful scrape or legacy title/artist equality.
    quotas = load_quotas(BASE / "sources/country_quotas.csv")
    expected_cells = [
        dict(country_code=country, year=year, quota_main=quota)
        for country, quota in quotas.items()
        for year in range(2018, 2027)
    ]
    gate = prepare_quota_review(selected, [], current_documents={}, expected_cells=expected_cells)
    gate_summary = {
        key: gate[key]
        for key in ("coverage", "classification_ready", "paid_calls", "remaining_gates")
    }
    gate_summary.update(
        selection_root=str(BASE),
        validation_records_loaded=0,
        positions_evaluated=len(gate["ranked_positions"]),
        prepared_candidates=len(gate["prepared_candidates"]),
    )
    part = output / "review-gate-summary.part"
    part.write_text(json.dumps(gate_summary, indent=2), encoding="utf-8")
    part.replace(output / "review-gate-summary.json")
    del gate
    verified_blobs, digests, records = {}, defaultdict(list), []
    for payload in targets:
        key = payload["recording_id"]
        prior, state, result = stored.get(key, ({}, "not_enqueued", {}))
        audit = audit_saved_result(payload, result)
        flags = list(audit.get("text_quality_flags", []))
        if audit["source_quarantined"]:
            flags.append("source_quarantined")
        for field in ("title", "artist"):
            if prior and identity(prior.get(field)) != identity(payload.get(field)):
                flags.append(f"stored_{field}_requires_reconciliation")
        digest, filename = result.get("text_sha256"), result.get("text_path")
        integrity = False
        if filename and digest:
            if (filename, digest) not in verified_blobs:
                path = Path(filename)
                verified_blobs[filename, digest] = (
                    path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == digest
                )
            integrity = verified_blobs[filename, digest]
            if not integrity:
                flags.append("text_blob_missing_or_hash_mismatch")
        else:
            flags.append("no_text_blob")
        record = dict(
            candidate_id=key,
            title=payload.get("title"),
            artist=payload.get("artist"),
            chart_bindings=payload["chart_bindings"],
            acquisition_status=state,
            metadata_resolution=payload.get("metadata_resolution"),
            chart_video_evidence=native.get(key),
            changed_chart_credit_evidence=changed_credits.get(key, []),
            text_result=result,
            blob_integrity_verified=integrity,
            review_flags=flags,
            identity_validated=False,
            completeness_validated=False,
            classification_ready=False,
        )
        records.append(record)
        if digest:
            digests[digest].append(record)
    for group in digests.values():
        if len({identity(row["title"]) for row in group}) > 1:
            for row in group:
                row["review_flags"].append("same_text_different_titles")
    part = output / "candidates.part"
    with part.open("w", encoding="utf-8") as handle:
        for row in records:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    part.replace(output / "candidates.jsonl")
    summary = dict(
        exported_at=datetime.now(UTC).isoformat(),
        ranking_metric_basis="sum_observed_chart_metrics",
        full_annual_stream_order_certified=False,
        selection_root=str(BASE),
        unique_candidates=len(records),
        memberships=len(selected),
        statuses=dict(Counter(r["acquisition_status"] for r in records)),
        texts_with_verified_blob=sum(r["blob_integrity_verified"] for r in records),
        flags=dict(Counter(flag for r in records for flag in r["review_flags"])),
        database_snapshot_does_not_include_later_writes=True,
        classification_ready=False,
    )
    part = output / "summary.part"
    part.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    part.replace(output / "summary.json")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-root", type=Path)
    args = parser.parse_args()
    if args.base_root:
        BASE = args.base_root.resolve()
    print(json.dumps(export()))
