"""Audit preserved text hashes and native display disagreements without approving lyrics."""

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from recover_low_coverage_lyrics import availability, deficient, load_baseline

from chart_observatory.lyrics.quota_acquisition import identity
from chart_observatory.runtime_status import publish_status

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--metadata-db", action="append", type=Path, default=[])
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    paths = [args.staging, args.out, *args.metadata_db]
    if not all(path.resolve().is_relative_to(ROOT) for path in paths):
        raise ValueError("audit paths must remain inside the project")
    args.out.mkdir(parents=True, exist_ok=True)
    records, texts = load_baseline(args.staging, args.run_id)
    proofs, sources = {}, []
    for path in args.metadata_db:
        path = path.resolve()
        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
            for key, raw in db.execute("SELECT candidate_id,proof FROM evidence"):
                if key in records:
                    proof = json.loads(raw)
                    previous = proofs.get(key)
                    if previous is None or proof.get("retrieved_at", "") > previous.get(
                        "retrieved_at", ""
                    ):
                        proofs[key] = proof
        sources.append(dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    discrepancies, diagnostics = [], {}
    counts, flags = Counter(), Counter()
    for key, record in sorted(records.items()):
        audit, payload = record["audit"], record["payload"]
        counts["text_candidates"] += bool(record["text_sha256"])
        flags.update(audit.get("text_quality_flags", []))
        counts["candidates_with_quality_flags"] += bool(audit.get("text_quality_flags"))
        shared_collision = bool(
            set(audit.get("text_quality_flags", []))
            & {"same_text_different_titles", "same_text_different_performers"}
        )
        counts["candidates_with_shared_text_collision"] += shared_collision
        counts["source_quarantined_candidates"] += bool(audit.get("source_quarantined"))
        if audit.get("text_quality_flags") or shared_collision or audit.get("source_quarantined"):
            diagnostics[key] = dict(
                candidate_id=key,
                text_sha256=record["text_sha256"],
                native_display_disagreement=None,
                audit=audit,
                chart_bindings=payload["chart_bindings"],
            )
        if key not in proofs:
            counts["without_native_proof"] += 1
            continue
        proof = proofs[key]
        metadata = proof.get("metadata") or {}
        native = key.removeprefix("SPOTIFY:")
        if (
            not key.startswith("SPOTIFY:")
            or proof.get("status") != 200
            or metadata.get("uri") != f"spotify:track:{native}"
            or proof.get("source_url") != f"https://open.spotify.com/embed/track/{native}"
        ):
            counts["native_proof_unusable"] += 1
            continue
        differences = [
            field
            for field in ("title", "artist")
            if identity(payload.get(field)) != identity(metadata.get(field))
        ]
        counts["native_proof_valid"] += 1
        if differences:
            counts["native_display_disagreement_candidates"] += 1
            counts["native_display_disagreement_with_text"] += bool(record["text_sha256"])
            discrepancies.append(
                dict(
                    candidate_id=key,
                    text_sha256=record["text_sha256"],
                    frozen_display={field: payload.get(field) for field in ("title", "artist")},
                    native_display=metadata,
                    differing_fields=differences,
                    chart_bindings=payload["chart_bindings"],
                    proof=proof,
                    disposition="requires_native_display_and_edition_review",
                    identity_validated=False,
                    completeness_validated=False,
                )
            )
        else:
            counts["native_display_matches"] += 1
        if differences or key in diagnostics:
            diagnostics[key] = dict(
                candidate_id=key,
                text_sha256=record["text_sha256"],
                native_display_disagreement=bool(differences),
                audit=audit,
                chart_bindings=payload["chart_bindings"],
            )
    coverage = availability(records.values())
    gaps = deficient(coverage)
    artifacts = {}
    for name, values in (
        ("native-display-review.jsonl", discrepancies),
        ("quality-review.jsonl", list(diagnostics.values())),
        (
            "native-proof-inventory.jsonl",
            [dict(candidate_id=k, proof=v) for k, v in sorted(proofs.items())],
        ),
    ):
        raw = "".join(
            json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n" for value in values
        ).encode()
        (args.out / name).write_bytes(raw)
        artifacts[name] = dict(sha256=hashlib.sha256(raw).hexdigest(), rows=len(values))
    publish_status(
        args.out / "report.json",
        dict(
            created_at=datetime.now(UTC).isoformat(),
            source_staging=str(args.staging.resolve()),
            source_staging_sha256=hashlib.sha256(args.staging.read_bytes()).hexdigest(),
            source_run_id=args.run_id,
            candidate_count=len(records),
            text_hashes_verified=len(texts),
            candidate_counts=dict(counts),
            quality_flags=dict(flags),
            native_sources=sources,
            known_positions=sum(v["known_positions"] for v in coverage.values()),
            positions_with_text=sum(v["positions_with_text"] for v in coverage.values()),
            occupied_cells=len(coverage),
            cells_at_80_availability=len(coverage) - len(gaps),
            availability_position_deficit=sum(gaps.values()),
            artifacts=artifacts,
            scientific_approved_positions=0,
            approvals=0,
            paid_calls=0,
            native_metadata_agreement_is_not_lyric_identity_or_completeness_approval=True,
        ),
    )


if __name__ == "__main__":
    main()
