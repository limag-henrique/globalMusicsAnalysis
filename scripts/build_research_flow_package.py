"""Build a local, explicitly incomplete research preparation package without lyrics."""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from chart_observatory.pipeline_state import file_hash
from chart_observatory.research_flow import load_selection, verify_audit

ROOT = Path(__file__).resolve().parents[1]
AUDIT_FILES = (
    "report.json",
    "manifest.json",
    "gates.csv",
    "items.jsonl",
    "preparatory-table.csv",
    "ranking-recovery-queue.jsonl",
    "lyric-review-queue.jsonl",
    "local-statuses.json",
    "environment.json",
    "contract.json",
    "evidence-schema.json",
    "evidence-template.json",
)
SOURCES = (
    "pyproject.toml",
    "uv.lock",
    "CONTEXT.md",
    "scripts/incorporate_global_annual.py",
    "scripts/build_historical_backfill.py",
    "scripts/audit_missing_spotify_days.py",
    "scripts/ensure_research_postgres.ps1",
    "scripts/research_environment.ps1",
    "scripts/research_postgres_paths.ps1",
    "scripts/persist_frozen_research_selection.py",
    "scripts/run_research_postgres_tests.py",
    "scripts/recover_v4_lyric_delta.py",
    "scripts/recover_low_coverage_lyrics.py",
    "scripts/recover_worldwide_chart_history.py",
    "scripts/report_worldwide_chart_recovery.py",
    "scripts/resume_research_collectors.py",
    "scripts/run_native_mgd_evidence.py",
    "scripts/prepare_native_mgd_review.py",
    "scripts/audit_current_lyric_corpus.py",
    "scripts/verify_lyric_source_chains.py",
    "scripts/audit_lyric_db_local_mismatches.py",
    "scripts/import_new_global_lyrics.py",
    "scripts/import_validation_updates.py",
    "scripts/prepare_vertex_readiness.py",
    "scripts/finalize_vertex_dossier.py",
    "scripts/prepare_research_contract.py",
    "scripts/build_global_v3_archive_supplement_v2.py",
    "scripts/create_v4_archive_selection_0001.py",
    "src/chart_observatory/research_flow.py",
    "src/chart_observatory/research_flow_cli.py",
    "src/chart_observatory/research_rankings.py",
    "src/chart_observatory/research_chart_recovery.py",
    "src/chart_observatory/research_progress.py",
    "src/chart_observatory/research_progress_cli.py",
    "src/chart_observatory/research_validation.py",
    "src/chart_observatory/research_stage_ledger.py",
    "src/chart_observatory/research_classification_service.py",
    "src/chart_observatory/research_database_health.py",
    "src/chart_observatory/research_native_batch.py",
    "src/chart_observatory/research_native_review.py",
    "src/chart_observatory/research_source_projection.py",
    "src/chart_observatory/research_source_projection_cli.py",
    "src/chart_observatory/ingestion/global_annual.py",
    "src/chart_observatory/ingestion/historical_backfill.py",
    "src/chart_observatory/ingestion/import_quotas.py",
    "src/chart_observatory/ingestion/quota_boundary.py",
    "src/chart_observatory/ingestion/source_coverage.py",
    "src/chart_observatory/lyrics/research_contract.py",
    "src/chart_observatory/lyrics/research_vertex_payload.py",
    "src/chart_observatory/lyrics/review_protocol.py",
    "src/chart_observatory/lyrics/revision_protocol.py",
    "src/chart_observatory/lyrics/classification_gate.py",
    "src/chart_observatory/lyrics/global_import.py",
    "src/chart_observatory/lyrics/quota_acquisition.py",
    "src/chart_observatory/lyrics/web_comparison.py",
    "docs/operations/research-flow-20261110.md",
    "docs/operations/research-classification-contract-20261110.md",
    "docs/operations/research-flow-source-assessment-20261110.md",
    "docs/operations/research-flow-live-status-20261111.md",
    "docs/operations/research-source-availability-20261111.md",
    "docs/operations/global-annual-incorporation-20261108.md",
    "scripts/build_research_flow_package.py",
    "scripts/prepare_research_contract.py",
    "tests/unit/test_research_flow.py",
    "tests/unit/test_research_flow_cli.py",
    "tests/unit/test_research_classification_service.py",
    "tests/unit/test_research_rankings.py",
    "tests/unit/test_research_validation.py",
    "tests/unit/test_research_progress.py",
    "tests/unit/test_research_stage_ledger.py",
    "tests/unit/test_research_database_health.py",
    "tests/unit/test_research_postgres_paths.py",
    "tests/unit/test_persist_frozen_research_selection.py",
    "tests/unit/lyrics/test_research_vertex_payload.py",
    "tests/unit/test_research_native_batch.py",
    "tests/unit/test_research_native_review.py",
    "tests/unit/test_research_source_projection.py",
    "tests/unit/test_research_chart_recovery.py",
    "tests/unit/test_resume_research_collectors.py",
    "tests/unit/test_report_worldwide_chart_recovery.py",
    "tests/unit/test_build_research_flow_package.py",
    "tests/unit/lyrics/test_research_contract.py",
    "tests/unit/lyrics/test_classification_repository.py",
    "tests/unit/lyrics/test_global_lyric_import.py",
    "tests/unit/ingestion/test_global_annual.py",
    "tests/unit/ingestion/test_historical_backfill.py",
    "tests/unit/ingestion/test_archive_metadata.py",
    "tests/unit/ingestion/test_source_coverage.py",
    "tests/integration/research/test_research_flow.py",
)


SELECTION_FILES = (
    "combined.jsonl",
    "country_years.jsonl",
    "countries.json",
    "source_coverage.json",
    "position_tie_tasks.jsonl",
    "adjudication_tasks.jsonl",
    "zenodo_provenance.json",
)


def _selection_artifacts(selection):
    selection = Path(selection).resolve()
    if not selection.is_relative_to(ROOT / "data/derived"):
        raise ValueError("selection must be a local derived research artifact")
    # This validates the complete cell/membership universe and every output hash
    # declared in the selection manifest before any bytes enter the package.
    manifest, _cells, _memberships, _hashes = load_selection(selection)
    missing = [name for name in SELECTION_FILES if name not in manifest["output_hashes"]]
    if missing:
        raise ValueError("selection lacks required hashed artifacts: " + ", ".join(missing))
    artifacts = {f"selection/{name}": selection / name for name in SELECTION_FILES}
    artifacts["selection/manifest.json"] = selection / "manifest.json"

    source_hashes = manifest.get("source_hashes", {})
    metadata_files = {}
    for key, expected_hash in source_hashes.items():
        normalized = key.replace("\\", "/")
        if normalized.endswith("/zenodo-23645386/README.md"):
            metadata_files["selection/source/README.md"] = (key, expected_hash)
        elif normalized.endswith("/zenodo-23645386/record.json"):
            metadata_files["selection/source/record.json"] = (key, expected_hash)
    if set(metadata_files) != {
        "selection/source/README.md",
        "selection/source/record.json",
    }:
        raise ValueError("selection source hashes must identify Zenodo README.md and record.json")
    for archive_name, (source_name, expected_hash) in metadata_files.items():
        source = ROOT.joinpath(*source_name.replace("\\", "/").split("/"))
        if (
            not source.resolve().is_relative_to(ROOT)
            or not source.is_file()
            or file_hash(source) != expected_hash
        ):
            raise ValueError("selection source metadata hash mismatch: " + source_name)
        artifacts[archive_name] = source

    # A selection package carries metadata and audit queues only. Refuse lyric
    # payloads if an unexpected schema has been placed in the membership file.
    lyric_fields = {"lyrics", "raw_lyrics", "lyric_text", "raw_text", "full_text"}
    for line in (selection / "combined.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if lyric_fields.intersection(row):
            raise ValueError("selection membership contains lyric text; refusing package")
    return manifest, artifacts


def build(audit, output, validation_reports=(), selection=None):
    audit, output = Path(audit).resolve(), Path(output).resolve()
    if not audit.is_relative_to(ROOT / "data/runtime"):
        raise ValueError("audit must be in the private project runtime")
    if not output.is_relative_to(ROOT / "data/runtime") or output.exists():
        raise ValueError("use a new package file in the private project runtime")
    report = verify_audit(audit)
    artifacts = {f"audit/{name}": audit / name for name in AUDIT_FILES}
    artifacts.update({name: ROOT / name for name in SOURCES})
    selection_manifest = None
    selection_manifest_sha256 = None
    selection_relative_path = None
    selection_matches_audit = None
    if selection is not None:
        selection_path = Path(selection).resolve()
        selection_manifest, selection_artifacts = _selection_artifacts(selection_path)
        artifacts.update(selection_artifacts)
        selection_manifest_sha256 = file_hash(selection_path / "manifest.json")
        selection_relative_path = selection_path.relative_to(ROOT).as_posix()
        selection_matches_audit = selection_manifest_sha256 == report["selection_sha256"]
    for index, name in enumerate(validation_reports, 1):
        path = Path(name).resolve()
        if not path.is_relative_to(ROOT / "data/runtime") or path.suffix != ".xml":
            raise ValueError("validation reports must be local runtime JUnit XML")
        artifacts[f"validation/{index}-{path.name}"] = path
    hashes = {name: file_hash(path) for name, path in artifacts.items()}
    if any(value is None for value in hashes.values()):
        raise ValueError("a required package artifact is missing")
    all_gates_approved = bool(report.get("gates")) and all(
        gate.get("state") == "aprovado" for gate in report["gates"]
    )
    selection_scope_approved = selection_matches_audit is not False
    manifest = {
        "package_version": "research-preparation-package-v2",
        "status": (
            "approved_research"
            if report["research_ready"] and all_gates_approved and selection_scope_approved
            else "blocked_preparation"
        ),
        "selection_sha256": report["selection_sha256"],
        "audit_run_id": report["audit_run_id"],
        "research_ready": (
            report["research_ready"] and all_gates_approved and selection_scope_approved
        ),
        "audit_selection_sha256": report["selection_sha256"],
        "selection_matches_audit": selection_matches_audit,
        "gate_states": {gate["gate"]: gate["state"] for gate in report.get("gates", [])},
        "selection_path": selection_relative_path,
        "selection_revision": (
            selection_manifest.get("selection_revision") if selection_manifest else None
        ),
        "selection_manifest_sha256": selection_manifest_sha256,
        "artifacts": hashes,
        "raw_lyrics_included": False,
        "scope_limit": "Data references do not constitute source or human validation.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, path in artifacts.items():
            content = path.read_bytes()
            if hashlib.sha256(content).hexdigest() != hashes[name]:
                raise ValueError("input changed during packaging")
            archive.writestr(name, content)
        archive.writestr(
            "package-manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2)
        )
    return {
        "path": str(output),
        "sha256": file_hash(output),
        "status": manifest["status"],
        "files": len(artifacts) + 1,
        "raw_lyrics_included": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--validation-report", action="append", default=[], type=Path)
    parser.add_argument("--selection", type=Path, help="optional hashed annual selection directory")
    args = parser.parse_args()
    print(
        json.dumps(
            build(args.audit, args.output, args.validation_report, args.selection),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
