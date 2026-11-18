"""Generate a candidate-level reconciliation dataset comparing canonical catalog vs v07 and v08."""

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_decisions(path: Path) -> dict[str, dict]:
    out = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                out[row["candidate_id"]] = row
    return out


def classify_disagreement(canon_pass: bool, v7: dict, v8: dict, canon_sha: str | None) -> tuple[str, list[str]]:
    v7_pass = bool(v7.get("provider_supported"))
    v8_pass = bool(v8.get("provider_supported"))
    reasons: list[str] = []
    if canon_sha != v7.get("text_sha256"):
        reasons.append("text_sha256_differs_v07")
    if canon_sha != v8.get("text_sha256"):
        reasons.append("text_sha256_differs_v08")

    if canon_pass == v7_pass == v8_pass:
        return ("agreed_pass" if canon_pass else "agreed_non_pass"), reasons

    flags = sorted((v8.get("audit") or {}).get("text_quality_flags") or [])
    val = v8.get("validation") or {}
    if not v8.get("native_supported"):
        reasons.append("native_recording_evidence_failed_or_missing")
    if (val.get("identity") or {}).get("status") != "passed":
        reasons.append(f"independent_identity_{(val.get('identity') or {}).get('status')}")
    if (val.get("completeness") or {}).get("status") != "passed":
        reasons.append(f"independent_completeness_{(val.get('completeness') or {}).get('status')}")
    if (val.get("source_text_integrity") or {}).get("status") != "passed":
        reasons.append(f"independent_source_integrity_{(val.get('source_text_integrity') or {}).get('status')}")
    for f in flags:
        reasons.append(f"flag:{f}")
    if not reasons:
        reasons.append("validator_strictness_difference")
    return "canonical_pass_independent_non_pass", reasons


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=Path("data/runtime/final-pipeline/catalog.sqlite"))
    parser.add_argument("--canon-report", type=Path, default=Path("data/runtime/final-pipeline/lyrics-report.json"))
    parser.add_argument("--canon-queue", type=Path, default=Path("data/runtime/final-pipeline/lyric-review-queue.jsonl"))
    parser.add_argument("--selection", type=Path, default=Path("data/derived/annual_revision/population-total-150k-2018-2026-20261116-v10-archives"))
    parser.add_argument("--v07", type=Path, default=Path("data/runtime/priority-full-verification-20261116-07-v10-native-complete"))
    parser.add_argument("--v08", type=Path, default=Path("data/runtime/priority-full-verification-20261117-08-v10-post-import"))
    parser.add_argument("--output", type=Path, default=Path("data/runtime/reconciliation-20261117-01"))
    args = parser.parse_args(argv)

    args.output.mkdir(parents=True, exist_ok=True)
    canon_report = json.loads(args.canon_report.read_text(encoding="utf-8"))
    canon_fail = {}
    with args.canon_queue.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                canon_fail[d["song_id"]] = d["assessment"]

    v07 = load_decisions(args.v07 / "decisions.jsonl")
    v08 = load_decisions(args.v08 / "decisions.jsonl")
    v07_inputs = json.loads((args.v07 / "inputs.json").read_text(encoding="utf-8"))
    v08_inputs = json.loads((args.v08 / "inputs.json").read_text(encoding="utf-8"))

    memberships: dict[str, list[dict]] = {}
    with (args.selection / "combined.jsonl").open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                m = json.loads(line)
                memberships.setdefault(m["candidate_id"], []).append(
                    {
                        "country_code": m["country_code"],
                        "year": m["year"],
                        "platform": m["platform"],
                        "position": m["position"],
                        "selection_status": m.get("selection_status"),
                    }
                )

    db = sqlite3.connect(args.catalog.resolve().as_uri() + "?mode=ro", uri=True)
    catalog_rows = {
        cid: (json.loads(payload), json.loads(result) if result else {})
        for cid, payload, result in db.execute("SELECT id, payload, result FROM songs")
    }
    db.close()

    category_counts = Counter()
    reason_counts = Counter()
    text_hash_diffs_v07 = 0
    text_hash_diffs_v08 = 0
    rep_record = None

    out_jsonl = args.output / "reconciliation.jsonl"
    with out_jsonl.open("w", encoding="utf-8") as out_f:
        for cid in sorted(memberships):
            payload, res = catalog_rows.get(cid, ({}, {}))
            canon_sha = res.get("text_sha256")
            canon_pass = cid not in canon_fail
            v7 = v07[cid]
            v8 = v08[cid]
            if canon_sha != v7.get("text_sha256"):
                text_hash_diffs_v07 += 1
            if canon_sha != v8.get("text_sha256"):
                text_hash_diffs_v08 += 1

            cat, reasons = classify_disagreement(canon_pass, v7, v8, canon_sha)
            category_counts[cat] += 1
            if cat == "canonical_pass_independent_non_pass":
                for r in reasons:
                    reason_counts[r] += 1

            v8_val = v8.get("validation") or {}
            record = {
                "candidate_id": cid,
                "memberships_count": len(memberships[cid]),
                "memberships": memberships[cid],
                "canonical_decision": {
                    "provider_integrity_passed": canon_pass,
                    "assessment_if_non_pass": canon_fail.get(cid),
                    "text_sha256": canon_sha,
                    "staging_reference": res.get("staging_reference"),
                    "source": res.get("source"),
                    "text_path": res.get("text_path"),
                },
                "v07_decision": {
                    "provider_supported": v7.get("provider_supported"),
                    "native_supported": v7.get("native_supported"),
                    "native_and_provider_supported": v7.get("native_and_provider_supported"),
                    "text_sha256": v7.get("text_sha256"),
                    "automated_overall": (v7.get("validation") or {}).get("automated_overall"),
                    "source": (v7.get("source_result") or {}).get("source"),
                },
                "v08_decision": {
                    "provider_supported": v8.get("provider_supported"),
                    "native_supported": v8.get("native_supported"),
                    "native_and_provider_supported": v8.get("native_and_provider_supported"),
                    "text_sha256": v8.get("text_sha256"),
                    "automated_overall": v8_val.get("automated_overall"),
                    "identity_status": (v8_val.get("identity") or {}).get("status"),
                    "completeness_status": (v8_val.get("completeness") or {}).get("status"),
                    "source_integrity_status": (v8_val.get("source_text_integrity") or {}).get("status"),
                    "native_recording_alignment": v8_val.get("native_recording_alignment"),
                    "text_quality_flags": (v8.get("audit") or {}).get("text_quality_flags"),
                    "source": (v8.get("source_result") or {}).get("source"),
                    "source_metadata": (v8.get("source_result") or {}).get("source_metadata"),
                },
                "reconciliation_category": cat,
                "disagreement_reasons": reasons,
            }
            if cid == "SPOTIFY:1feANd8EfcDP5UqSvbheM3":
                rep_record = record
            out_f.write(json.dumps(record, ensure_ascii=False) + "\n")

    summary = {
        "schema_version": "canonical-independent-reconciliation-v1",
        "generated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "inputs": {
            "catalog": str(args.catalog),
            "canon_report": str(args.canon_report),
            "canon_report_sha256": sha256_file(args.canon_report),
            "canon_implementation_sha256": canon_report.get("implementation_sha256"),
            "v07": str(args.v07),
            "v07_implementation_sha256": v07_inputs.get("implementation_sha256"),
            "v08": str(args.v08),
            "v08_implementation_sha256": v08_inputs.get("implementation_sha256"),
        },
        "total_candidates": len(memberships),
        "text_hash_diffs_vs_v07": text_hash_diffs_v07,
        "text_hash_diffs_vs_v08": text_hash_diffs_v08,
        "category_counts": dict(category_counts),
        "disagreement_reason_counts": dict(reason_counts.most_common()),
        "representative_candidate_SPOTIFY_1feANd8EfcDP5UqSvbheM3": rep_record,
        "output_jsonl": str(out_jsonl),
        "output_jsonl_sha256": sha256_file(out_jsonl),
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in summary.items() if k != "representative_candidate_SPOTIFY_1feANd8EfcDP5UqSvbheM3"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
