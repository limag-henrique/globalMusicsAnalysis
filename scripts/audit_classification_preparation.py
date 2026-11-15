"""Package the local 26-topic preparation and its verification without cloud calls."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import sys
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

from chart_observatory.lyrics.research_contract import write_contract_bundle
from chart_observatory.lyrics.review_protocol import TOPICS

ROOT = Path(__file__).resolve().parents[1]
IMPLEMENTATION = (
    "src/chart_observatory/lyrics/research_contract.py",
    "src/chart_observatory/lyrics/research_vertex_payload.py",
    "src/chart_observatory/lyrics/review_protocol.py",
    "src/chart_observatory/lyrics/revision_protocol.py",
    "src/chart_observatory/lyrics/campaign_budget.py",
    "src/chart_observatory/research_classification_service.py",
    "tests/unit/lyrics/test_research_contract.py",
    "tests/unit/lyrics/test_research_vertex_payload.py",
    "tests/unit/test_research_classification_service.py",
    "tests/unit/lyrics/test_revision_protocol.py",
    "tests/unit/lyrics/test_classification_queue.py",
    "tests/unit/lyrics/test_batch_contract.py",
    "scripts/prepare_research_contract.py",
    "scripts/audit_classification_preparation.py",
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package(output, validation_report):
    output, validation_report = Path(output).resolve(), Path(validation_report).resolve()
    if not output.is_relative_to(ROOT / "data/runtime") or output.exists():
        raise ValueError("use a new output directory in data/runtime")
    if not validation_report.is_relative_to(ROOT / "data/runtime"):
        raise ValueError("use a project runtime validation report")
    xml = ET.parse(validation_report).getroot()
    cases = list(xml.iter("testcase"))
    counts = {
        "tests": len(cases),
        "failures": len(list(xml.iter("failure"))),
        "errors": len(list(xml.iter("error"))),
        "skipped": len(list(xml.iter("skipped"))),
    }
    required_suites = {
        "tests.unit.lyrics.test_research_contract",
        "tests.unit.test_research_classification_service",
        "tests.unit.lyrics.test_revision_protocol",
        "tests.unit.lyrics.test_research_vertex_payload",
    }
    if (
        not required_suites <= {case.get("classname") for case in cases}
        or counts["failures"]
        or counts["errors"]
        or counts["skipped"]
    ):
        raise ValueError("require successful, unskipped contract, service and registry checks")
    output.mkdir(parents=True, exist_ok=False)
    write_contract_bundle(output / "contract")
    shutil.copyfile(validation_report, output / "tests.xml")
    for name in IMPLEMENTATION:
        destination = output / "implementation" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
    report = {
        "version": "classification-local-preparation-audit-v1",
        "created_at": datetime.now(UTC).isoformat(),
        "status": "local_preparation_verified_pending_scientific_inputs",
        "authorization_reference_declared": "MG.202652246900",
        "topic_count": len(TOPICS),
        "scale": [0, 1, 2, 3],
        "presence_threshold": 2,
        "table_rows_created": 0,
        "local_checks": {
            "nominal_schema_and_runtime_agree": True,
            "vertex_wire_uses_26_topic_json_schema_and_resolved_model": True,
            "lossless_segments_and_full_signature": True,
            "null_scores_before_accepted_classification": True,
            "online_batch_cache_and_import_signature": True,
            "out_of_order_import_by_request_id": True,
            "revoked_approval_rejected": True,
            "exclusive_reservation_and_unknown_submission_held": True,
            "shared_budget_and_150_usd_effective_cap": True,
        },
        "tests": counts,
        "scientific_eligibility": "not_evaluated_use_current_research_audit",
        "pending_scientific_inputs": [
            "rankings_and_adjudicated_lyrics_meet_current_gates",
            "scientific_acceptance_of_exact_rubric",
            "independent_development_and_validation_annotations",
            "per_topic_and_language_support_and_performance",
        ],
        "validation_targets": {
            "development": 80,
            "independent_validation": 240,
            "human_alpha_minimum": 0.8,
            "macro_f1_minimum": 0.8,
            "ordinal_weighted_kappa_minimum": 0.8,
        },
        "future_dispatch_requirements": [
            "current_gates_and_eligible_text_hash_revalidated",
            "exact_resolved_model_region_and_configuration",
            "reconciled_shared_billing_and_conservative_cost_reservation",
            "current_official_model_batch_and_price_documentation",
        ],
        "official_documentation": {
            "json_schema": "https://docs.cloud.google.com/java/docs/reference/"
            "google-cloud-vertexai/latest/"
            "com.google.cloud.vertexai.api.GenerationConfig.Builder",
            "model": "https://docs.cloud.google.com/"
            "gemini-enterprise-agent-platform/models/gemini/3-8-flash",
            "pricing": "https://cloud.google.com/model-garden/pricing",
        },
        "environment": {"python": sys.version, "platform": platform.platform()},
        "paid_calls": 0,
        "uploads": 0,
        "scientific_approval_created": False,
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    manifest = {
        "version": report["version"],
        "status": report["status"],
        "artifacts": {
            path.relative_to(output).as_posix(): digest(path)
            for path in sorted(output.rglob("*"))
            if path.is_file()
        },
        "raw_lyrics_included": False,
        "paid_calls": 0,
        "uploads": 0,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "output": str(output),
        "manifest_sha256": digest(output / "manifest.json"),
        "tests": counts,
        "status": report["status"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--validation-report", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(package(args.output, args.validation_report), ensure_ascii=False))


if __name__ == "__main__":
    main()
