"""Reproducible end-to-end lyrics recovery, verification, and PG reconciliation pipeline."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine

from chart_observatory import research_database_health as db_health
from chart_observatory.config import Settings
from chart_observatory.lyrics.automated_validation import VALIDATION_VERSION
from chart_observatory.lyrics.corpus_quality import QUALITY_AUDIT_VERSION
from chart_observatory.lyrics.inventory_export import (
    PARSER_VERSION,
    rebuild_inventory_outputs,
    write_queues_and_change_ledger,
)
from chart_observatory.lyrics.quota_acquisition import identity
from chart_observatory.lyrics.recovery_pipeline import (
    apply_pg_v1_clean_fallback,
    build_v5_records,
    fetch_postgres_cohort_metrics,
    load_sqlite_staging_snapshot,
    persist_verified_staging,
    reconcile_v4_staging_runs,
    replay_sqlite_staging_runs,
    run_bounded_live_recovery,
    run_offline_store_and_cache_pass,
    verify_all_candidates,
)
from chart_observatory.lyrics.revision_protocol import NORMALIZATION_VERSION
from chart_observatory.lyrics.text_quality import TEXT_QUALITY_VERSION
from chart_observatory.research_flow import file_hash, load_selection
from chart_observatory.runtime_status import publish_status

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_V4_SELECTION = (
    ROOT / "data/derived/annual_revision/global-rescan-2018-2026-20261111-v4-final-0002"
)
DEFAULT_V5_SELECTION = (
    ROOT
    / "data/derived/annual_revision/global-rescan-2018-2026-20261115-v5-published-provisional-0003"
)
DEFAULT_CAMPAIGN_DIR = (
    ROOT / "data/runtime/antigravity-collaboration-20261115/pipeline-run-20261116-remediated"
)
DEFAULT_OUTPUT_DIR = ROOT / "outputs/inventario-musicas-pais-ano-20261115"
DEFAULT_COLLAB_DIR = ROOT / "data/runtime/antigravity-collaboration-20261115"

MILESTONE_SQLITE_SPECS: list[tuple[Path, list[str]]] = [
    (
        ROOT / "data/runtime/research-resume-20261114/v4-delta-0002/pending-staging.sqlite",
        ["bdbac1a192608b13ec3e818e576f943278c35936cdd5120cb0aaaea8f3ab5199"],
    ),
    (
        ROOT
        / "data/runtime/research-resume-20261115/low-coverage-native-0002/pending-staging.sqlite",
        ["f59314e586e0027f0554345cec5bcdc86c3e613302b0e1cf19f379aea40dbf85"],
    ),
    (
        ROOT
        / "data/runtime/research-resume-20261115/low-coverage-native-0003/pending-staging.sqlite",
        ["15da38539e2aafa9dc2de0b55caa5325f9e7296d8f37efd47ba0be5b563f6776"],
    ),
    (
        ROOT
        / "data/runtime/research-resume-20261115"
        / "low-coverage-native-agy-0001/pending-staging.sqlite",
        ["a80851163fd00c69ddfd80fe9d6aab30fd691f39a9d792859d8a506e4eb33af1"],
    ),
    (
        ROOT
        / "data/runtime/research-resume-20261115"
        / "low-coverage-native-agy-0002/pending-staging.sqlite",
        ["b85c4d84d1e36ffd744c6279b090120457011f8361329e762fc8f25bf14d4114"],
    ),
]

LEGACY_STORES = [
    ROOT / "data/derived/lyrics/global-20261108",
    ROOT / "data/derived/lyrics/v4-delta-20261114",
    ROOT / "data/derived/lyrics/low-coverage-20261115",
    ROOT / "data/derived/lyrics/low-coverage-native-20261115",
    ROOT / "data/derived/lyrics/low-coverage-native-agy-20261115",
    ROOT / "data/derived/lyrics/quota-20261030",
    ROOT / "data/runtime/antigravity-collaboration-20261115/pipeline-run-20261115/store-v4",
    ROOT / "data/runtime/antigravity-collaboration-20261115/pipeline-run-20261115/store-v5",
    ROOT
    / "data/runtime/antigravity-collaboration-20261115/full-corpus-acquisition-20261116/v4-store",
    ROOT
    / "data/runtime/antigravity-collaboration-20261115/full-corpus-acquisition-20261116/v5-store",
]

EXTRA_CACHE_SOURCES = (
    ROOT / "data/runtime/antigravity-collaboration-20261115/pipeline-run-20261115/offline-cache-v4",
    ROOT / "data/runtime/antigravity-collaboration-20261115/pipeline-run-20261115/offline-cache-v5",
    ROOT
    / "data/runtime/antigravity-collaboration-20261115/pipeline-run-20261115/store-v4/http-cache",
    ROOT
    / "data/runtime/antigravity-collaboration-20261115/pipeline-run-20261115/store-v5/http-cache",
    ROOT
    / "data/runtime/antigravity-collaboration-20261115/full-corpus-acquisition-20261116"
    / "v4-store/http-cache",
    ROOT
    / "data/runtime/antigravity-collaboration-20261115/full-corpus-acquisition-20261116"
    / "v5-store/http-cache",
)

NATIVE_METADATA_DBS = [
    ROOT / "data/raw/metadata_resolution/20261031/native-metadata.sqlite",
    ROOT / "data/raw/metadata_resolution/global-20261108/native-metadata.sqlite",
]


def _write_coordination_record(
    collab_dir: Path,
    *,
    campaign_dir: Path,
    v4_selection: Path,
    v5_selection: Path,
    stage: str,
) -> Path:
    path = collab_dir / "coordination-ownership-20261115.json"
    record = {
        "schema_version": "coordination-ownership-20261115-v1",
        "updated_at": datetime.now(UTC).isoformat(),
        "coordinator": "Antigravity (execution session c5b2b4cc-3ad0-4b66-981d-3900bcb8f978)",
        "handoff_peer": "OpenAI Codex (versioned file handoff only; no direct IPC)",
        "current_stage": stage,
        "store_ownership": {
            str((campaign_dir / "store-v4").resolve()): "exclusive_lock:owner.lock (v4 pipeline)",
            str(
                (campaign_dir / "store-v5").resolve()
            ): "exclusive_lock:owner.lock (v5 SI pipeline)",
            str(
                (campaign_dir / "staging-v4/pending-staging.sqlite").resolve()
            ): "pipeline_v4_staging",
            str(
                (campaign_dir / "staging-v5/pending-staging.sqlite").resolve()
            ): "pipeline_v5_staging",
            "postgresql:chart_observatory_recovery_20261007:quota_lyric_staging_*": (
                "advisory_xact_lock:2026103101"
            ),
            "outputs/inventario-musicas-pais-ano-20261115/*": "pipeline_refreshed_inventory",
        },
        "input_hashes": {
            "v4_manifest_sha256": file_hash(v4_selection / "manifest.json"),
            "v5_manifest_sha256": file_hash(v5_selection / "manifest.json"),
            "pipeline_module_sha256": file_hash(
                ROOT / "src/chart_observatory/lyrics/recovery_pipeline.py"
            ),
            "inventory_export_sha256": file_hash(
                ROOT / "src/chart_observatory/lyrics/inventory_export.py"
            ),
            "runner_script_sha256": file_hash(Path(__file__)),
        },
    }
    publish_status(path, record)
    return path


def _export_review_packets(
    review_dir: Path,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Emit quality-review.jsonl and native-display-review.jsonl from verified records."""
    review_dir.mkdir(parents=True, exist_ok=True)
    proofs: dict[str, dict[str, Any]] = {}
    for db_path in NATIVE_METADATA_DBS:
        if not db_path.exists():
            continue
        with sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True) as db:
            for key, raw in db.execute("SELECT candidate_id, proof FROM evidence"):
                proof = json.loads(raw)
                prev = proofs.get(key)
                if prev is None or proof.get("retrieved_at", "") > prev.get("retrieved_at", ""):
                    proofs[key] = proof

    quality_rows: list[dict[str, Any]] = []
    discrepancies: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for rec in records:
        cid = rec["candidate_id"]
        audit = rec.get("audit") or {}
        payload = rec.get("payload") or {}
        has_flags = bool(audit.get("text_quality_flags")) or bool(audit.get("source_quarantined"))
        native_diff = False
        if cid in proofs:
            proof = proofs[cid]
            meta = proof.get("metadata") or {}
            native = cid.removeprefix("SPOTIFY:")
            if (
                cid.startswith("SPOTIFY:")
                and proof.get("status") == 200
                and meta.get("uri") == f"spotify:track:{native}"
                and proof.get("source_url") == f"https://open.spotify.com/embed/track/{native}"
            ):
                diffs = [
                    f
                    for f in ("title", "artist")
                    if identity(payload.get(f)) != identity(meta.get(f))
                ]
                counts["native_proof_valid"] += 1
                if diffs:
                    native_diff = True
                    counts["native_display_disagreement"] += 1
                    discrepancies.append(
                        {
                            "candidate_id": cid,
                            "text_sha256": rec.get("text_sha256"),
                            "frozen_display": {f: payload.get(f) for f in ("title", "artist")},
                            "native_display": meta,
                            "differing_fields": diffs,
                            "chart_bindings": payload.get("chart_bindings", []),
                            "disposition": "requires_native_display_and_edition_review",
                            "identity_validated": False,
                            "completeness_validated": False,
                        }
                    )
        if has_flags or native_diff:
            counts["quality_review_rows"] += 1
            quality_rows.append(
                {
                    "candidate_id": cid,
                    "text_sha256": rec.get("text_sha256"),
                    "native_display_disagreement": native_diff,
                    "audit": audit,
                    "chart_bindings": payload.get("chart_bindings", []),
                }
            )

    q_path = review_dir / "quality-review.jsonl"
    n_path = review_dir / "native-display-review.jsonl"
    q_bytes = "".join(
        json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in quality_rows
    ).encode()
    n_bytes = "".join(
        json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in discrepancies
    ).encode()
    q_path.write_bytes(q_bytes)
    n_path.write_bytes(n_bytes)
    return {
        "counts": dict(counts),
        "quality_review_jsonl": str(q_path),
        "quality_review_sha256": hashlib.sha256(q_bytes).hexdigest(),
        "native_display_review_jsonl": str(n_path),
        "native_display_review_sha256": hashlib.sha256(n_bytes).hexdigest(),
    }


def _checkpoint_code_contract(
    v4_selection: Path | None = None,
    v5_selection: Path | None = None,
) -> dict[str, Any]:
    paths = [
        Path(__file__),
        ROOT / "scripts/validate_lyric_identity_completeness.py",
        ROOT / "scripts/verify_lyric_staging_mirror.py",
        *sorted((ROOT / "src/chart_observatory/lyrics").glob("*.py")),
    ]
    git_head = None
    try:
        git_head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except (OSError, subprocess.SubprocessError):
        git_head = None
    native_hashes = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in NATIVE_METADATA_DBS
        if p.is_file()
    }
    selection_hashes: dict[str, str] = {}
    for label, sel_dir in (("v4", v4_selection), ("v5", v5_selection)):
        if sel_dir is None:
            continue
        for fname in ("manifest.json", "combined.jsonl", "countries.json"):
            fpath = sel_dir / fname
            if fpath.is_file():
                selection_hashes[f"{label}/{fname}"] = hashlib.sha256(
                    fpath.read_bytes()
                ).hexdigest()
    return {
        "git_head": git_head,
        "versions": {
            "parser_version": PARSER_VERSION,
            "quality_audit_version": QUALITY_AUDIT_VERSION,
            "text_quality_version": TEXT_QUALITY_VERSION,
            "validation_version": VALIDATION_VERSION,
            "normalization_version": NORMALIZATION_VERSION,
        },
        "files": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths
            if path.is_file()
        },
        "native_evidence_dbs": native_hashes,
        "selection_manifests": selection_hashes,
    }


def _save_stage_checkpoint(
    checkpoint_dir: Path,
    name: str,
    records: dict[str, dict[str, Any]],
    texts: dict[str, str],
    *,
    code_contract: dict[str, Any] | None = None,
    upstream_sha256: str | None = None,
) -> Path:
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    path = checkpoint_dir / f"{name}.json"
    tmp = path.with_suffix(".part")
    payload = {
        "records": records,
        "texts": texts,
        "code_contract": code_contract or _checkpoint_code_contract(),
        "upstream_sha256": upstream_sha256,
    }
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    return path


def _load_stage_checkpoint(
    path: Path,
    *,
    code_contract: dict[str, Any] | None = None,
    expected_upstream_sha256: str | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    expected = code_contract or _checkpoint_code_contract()
    if data.get("code_contract") != expected:
        raise ValueError(
            "Checkpoint code/input contract missing or changed; rebuild dependent stages: "
            + str(path)
        )
    if (
        expected_upstream_sha256 is not None
        and data.get("upstream_sha256") != expected_upstream_sha256
    ):
        raise ValueError(
            "Checkpoint upstream lineage changed; rebuild dependent stages: " + str(path)
        )
    return data["records"], data["texts"]


def _archive_invalidated_checkpoints(
    campaign_dir: Path,
    checkpoint_paths: list[Path],
    *,
    reason: str,
    expected_upstream: dict[str, str],
) -> Path:
    """Preserve stale dependent checkpoints before a safe rebuild overwrites them."""
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    archive_dir = campaign_dir / "checkpoints" / "invalidated" / f"{stamp}-technical-verification"
    archive_dir.mkdir(parents=True, exist_ok=False)
    archived: list[dict[str, str]] = []
    for path in checkpoint_paths:
        if not path.is_file():
            continue
        destination = archive_dir / path.name
        shutil.copy2(path, destination)
        archived.append(
            {"source": str(path), "archive": str(destination), "sha256": file_hash(path)}
        )
    publish_status(
        archive_dir / "invalidation.json",
        {
            "schema_version": "pipeline-checkpoint-invalidation-v1",
            "created_at": datetime.now(UTC).isoformat(),
            "reason": reason,
            "expected_upstream_sha256": expected_upstream,
            "archived_files": archived,
            "action": "dependent stages rebuilt from current in-memory acquisition checkpoints",
        },
    )
    return archive_dir


def _verify_mirror_subprocess(sqlite_path: Path, run_id: str, out_json: Path) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(ROOT / "scripts/verify_lyric_staging_mirror.py"),
        "--local-staging",
        str(sqlite_path),
        "--run-id",
        run_id,
        "--out",
        str(out_json),
    ]
    subprocess.run(cmd, cwd=ROOT, check=True)
    return json.loads(out_json.read_text(encoding="utf-8"))


def _write_completion_reports(
    *,
    collab_dir: Path,
    campaign_dir: Path,
    output_dir: Path,
    reconciliation: dict[str, Any],
    acquisition_stats: dict[str, Any],
    v4_verification: dict[str, Any],
    v5_verification: dict[str, Any],
    queue_result: dict[str, Any],
    v4_persist: dict[str, Any],
    v5_persist: dict[str, Any],
    v4_mirror: dict[str, Any],
    v5_mirror: dict[str, Any],
    pg_inventory: dict[str, Any],
    inventory_export: dict[str, Any],
    cohort_metrics: dict[str, Any],
) -> tuple[Path, Path]:
    report_json = collab_dir / "completion-report-20261115.json"
    handoff_md = collab_dir / "copilot-frozen-handoff-20261115.md"
    v4_res = inventory_export["v4_resumo"]
    v5_res = inventory_export["v5_resumo"]

    payload = {
        "schema_version": "lyrics-recovery-completion-report-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "policy": "complete-rankings-lyrics80-v1",
        "campaign_dir": str(campaign_dir.resolve()),
        "reconciliation": reconciliation,
        "acquisition": acquisition_stats,
        "technical_verification": {"v4": v4_verification, "v5": v5_verification},
        "queues_and_change_ledger": {
            "pending_queue_jsonl": queue_result["pending_queue_jsonl"],
            "pending_queue_summary": queue_result["pending_queue_summary"],
            "change_ledger_jsonl": queue_result["change_ledger_jsonl"],
            "change_ledger_summary": queue_result["change_ledger_summary"],
            "review_interface_html": queue_result["review_interface_html"],
        },
        "persistence": {
            "v4_run_id": v4_persist["run_id"],
            "v5_run_id": v5_persist["run_id"],
            "v4_mirror_verified": v4_mirror,
            "v5_mirror_verified": v5_mirror,
            "postgres_current_inventory_v4": pg_inventory,
        },
        "cohort_vs_research_scope": {
            "imported_song_cohort": cohort_metrics,
            "v4_research_scope": v4_res,
            "v5_research_scope_with_slovenia_provisional": v5_res,
        },
        "outputs": {
            "inventario_completo_json": inventory_export["inventario_json"],
            "inventario_completo_json_sha256": inventory_export["inventario_json_sha256"],
            "inventario_html": inventory_export["inventario_html"],
            "inventario_html_sha256": inventory_export["inventario_html_sha256"],
        },
        "scientific_gates": {
            "G1": {"state": "reprovado", "approved": 0, "denominator": 277650, "required": 1.0},
            "G2": {"state": "pendente", "approved": 0, "denominator": 90600, "required": 0.8},
            "G3": {"state": "pendente", "prepared": 0, "required": 1.0},
            "G4": {"state": "pendente", "independent_scientific_validation": True},
            "G5": {"state": "pendente", "accepted_results": 0, "required": 0.8},
            "research_ready": False,
            "classification_ready": False,
            "paid_calls": 0,
        },
    }
    publish_status(report_json, payload)

    q_bytes = queue_result["pending_queue_summary"]["pending_queue_sha256"]
    q_rows = queue_result["pending_queue_summary"]["total_rows"]
    l_bytes = queue_result["change_ledger_summary"]["ledger_sha256"]
    l_rows = queue_result["change_ledger_summary"]["total_entries"]
    r_f593 = reconciliation["runs"]["f59314e5"]
    r_15da = reconciliation["runs"]["15da3853"]
    r_b85c = reconciliation["runs"]["b85c4d84"]
    v4_ok = (
        v4_mirror["local_postgresql_candidates_equal"]
        and v4_mirror["local_postgresql_bodies_equal"]
    )
    v5_ok = (
        v5_mirror["local_postgresql_candidates_equal"]
        and v5_mirror["local_postgresql_bodies_equal"]
    )
    handoff_lines = [
        "# Frozen Handoff to Copilot — Lyrics Recovery, Verification & Reconciliation (2026-11-15)",
        "",
        f"- **Generated At**: `{payload['generated_at']}`",
        (
            "- **Policy**: `complete-rankings-lyrics80-v1` "
            "(`research_ready: false`, `classification_ready: false`, `paid_calls: 0`)"
        ),
        (
            "- **PostgreSQL Cluster**: `127.0.0.1:55433/chart_observatory_recovery_20261007` "
            "(v4 & v5 selections + staging runs persisted and SHA-256 verified)"
        ),
        "",
        "## 1. Staging Lineage Reconciliation (`85,476` vs `85,523` vs `86,452` vs Current)",
        "",
        (
            f"- `f59314e586e0` (`low-coverage-native-0002`, `inventario-completo.json` baseline): "
            f"`{r_f593['candidates_with_text']}` unique candidates / "
            f"`{r_f593['position_linked_texts']}` position-linked texts."
        ),
        (
            f"- `15da38539e2a` (`low-coverage-native-0003` final): "
            f"`{r_15da['candidates_with_text']}` unique candidates / "
            f"`{r_15da['position_linked_texts']}` position-linked texts."
        ),
        (
            f"- `b85c4d84d1e3` (`low-coverage-native-agy-0002` final): "
            f"`{r_b85c['candidates_with_text']}` unique candidates / "
            f"`{r_b85c['position_linked_texts']}` position-linked texts."
        ),
        (
            f"- Reconciled across `15da3853` & `b85c4d84` (`0` hash conflicts; "
            f"`+{reconciliation['adopted_from_15da3853']}` verified LRCLIB candidates adopted -> "
            f"`{reconciliation['reconciled_v4_candidates_with_text']}` candidates / "
            f"`{reconciliation['reconciled_v4_position_linked_texts']}` memberships "
            "before subsequent recovery passes)."
        ),
        "",
        "## 2. Final Reconciled & Recovered Counts (Unique Candidates vs Memberships)",
        "",
        (
            "| Cohort / Scope | Unique Candidates | With Text | Missing Text | "
            "Memberships | Position Texts | Clean Unverified (Pending G2) | "
            "Flagged | Quarantined | Sci Approved |"
        ),
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        (
            f"| **Imported Historical Cohort (`canonical_tracks`)** | "
            f"`{cohort_metrics['canonical_tracks']}` | `{cohort_metrics['tracks_with_text']}` | "
            f"`{cohort_metrics['canonical_tracks'] - cohort_metrics['tracks_with_text']}` | "
            f"`N/A` | `{cohort_metrics['lyric_documents']}` docs | "
            "`N/A` | `N/A` | `26,540` LETRAS docs | `0` |"
        ),
        (
            f"| **Frozen Research `v4` (`global-rescan-...-v4-final-0002`)** | "
            f"`{v4_res['candidatos_unicos']}` | `{v4_res['candidatos_com_texto']}` | "
            f"`{v4_res['candidatos_sem_texto']}` | `{v4_res['participacoes']}` | "
            f"`{v4_res['participacoes_com_texto']}` | "
            f"`{v4_res['candidatos_limpos_nao_aprovados']}` | "
            f"`{v4_res['candidatos_com_alertas']}` | "
            f"`{v4_res['candidatos_quarentena']}` | `{v4_res['prontas_vertex']}` |"
        ),
        (
            f"| **Provisional Research `v5` (`...-v5-published-provisional-0003`)** | "
            f"`{v5_res['candidatos_unicos']}` | `{v5_res['candidatos_com_texto']}` | "
            f"`{v5_res['candidatos_sem_texto']}` | `{v5_res['participacoes']}` | "
            f"`{v5_res['participacoes_com_texto']}` | "
            f"`{v5_res['candidatos_limpos_nao_aprovados']}` | "
            f"`{v5_res['candidatos_com_alertas']}` | "
            f"`{v5_res['candidatos_quarentena']}` | `{v5_res['prontas_vertex']}` |"
        ),
        "",
        (
            f"- **Cells >=80% Raw Text Availability (`v4`)**: "
            f"`{v4_res['celulas_com_texto_80_pct']} / {v4_res['celulas_ocupadas']}` occupied cells "
            f"(`{v4_res['celulas_deficientes']}` deficient cells)."
        ),
        (
            f"- **v4 Staging Run ID**: `{v4_persist['run_id']}` "
            f"(SQLite & PG mirror verified: `{v4_ok}`)"
        ),
        (
            f"- **v5 Staging Run ID**: `{v5_persist['run_id']}` "
            f"(SQLite & PG mirror verified: `{v5_ok}`)"
        ),
        "",
        "## 3. Deliverables & Output Hashes",
        "",
        (
            "- `outputs/inventario-musicas-pais-ano-20261115/inventario-completo.json`: "
            f"SHA256 `{inventory_export['inventario_json_sha256']}`"
        ),
        (
            "- `outputs/inventario-musicas-pais-ano-20261115/inventario.html`: "
            f"SHA256 `{inventory_export['inventario_html_sha256']}`"
        ),
        (
            "- `outputs/inventario-musicas-pais-ano-20261115/pending-and-unavailable-queue.jsonl`: "
            f"`{q_rows}` rows, SHA256 `{q_bytes}`"
        ),
        (
            "- `outputs/inventario-musicas-pais-ano-20261115/change-ledger-v1-repairs.jsonl`: "
            f"`{l_rows}` rows, SHA256 `{l_bytes}`"
        ),
        f"- Completion JSON: `{report_json.resolve()}`",
        "",
        "## 4. Scientific Blockers Remaining (Unchanged Policy)",
        "",
        (
            "- **G1 (`0 / 277,650`, reprovado)**: Unverified chart positions across 174 missing "
            "markets and depth-shortfall cells require authorized archives + human verification."
        ),
        (
            "- **G2 (`0 / 90,600`, pendente)**: Acquired/verified raw text counts are technical "
            "staging availability, not human/official transcription & rights adjudication."
        ),
        (
            "- **G3–G5 (pendente)**: Blocked until G1/G2 approvals, rubric acceptance, "
            "and independent 80+240 validation split pass."
        ),
        "",
    ]
    handoff_md.write_text("\n".join(handoff_lines), encoding="utf-8")
    return report_json, handoff_md


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, default=DEFAULT_CAMPAIGN_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--collab-dir", type=Path, default=DEFAULT_COLLAB_DIR)
    parser.add_argument("--v4-selection", type=Path, default=DEFAULT_V4_SELECTION)
    parser.add_argument("--v5-selection", type=Path, default=DEFAULT_V5_SELECTION)
    parser.add_argument("--max-live-v4", type=int, default=150)
    parser.add_argument("--max-live-v5", type=int, default=150)
    parser.add_argument("--max-seconds", type=int, default=120)
    parser.add_argument("--workers", type=int, default=6, choices=range(1, 9))
    parser.add_argument("--skip-live", action="store_true")
    parser.add_argument("--no-replay-milestones", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--continue-live", action="store_true")
    parser.add_argument(
        "--stage",
        choices=[
            "all",
            "inventory",
            "acquisition",
            "technical_verification",
            "review_queue",
            "persistence_reconciliation",
            "refreshed_inventory",
            "completion_report",
        ],
        default="all",
    )
    args = parser.parse_args()

    campaign_dir = args.campaign_dir.resolve()
    output_dir = args.output_dir.resolve()
    collab_dir = args.collab_dir.resolve()
    v4_selection = args.v4_selection.resolve()
    v5_selection = args.v5_selection.resolve()
    for p in (campaign_dir, output_dir, collab_dir, v4_selection, v5_selection):
        if not p.is_relative_to(ROOT):
            raise ValueError(f"path outside repository: {p}")

    campaign_dir.mkdir(parents=True, exist_ok=True)
    checkpoints = campaign_dir / "checkpoints"
    checkpoints.mkdir(parents=True, exist_ok=True)

    engine = create_engine(Settings.load(ROOT).database_url, connect_args={"connect_timeout": 15})
    contract = _checkpoint_code_contract(v4_selection, v5_selection)
    change_ledger_rows: list[dict[str, Any]] = []
    ledger_ckpt = checkpoints / "change_ledger.json"
    if args.resume and ledger_ckpt.exists():
        change_ledger_rows = json.loads(ledger_ckpt.read_text(encoding="utf-8"))

    try:
        # 1. INVENTORY & RECONCILIATION
        _write_coordination_record(
            collab_dir,
            campaign_dir=campaign_dir,
            v4_selection=v4_selection,
            v5_selection=v5_selection,
            stage="inventory",
        )
        if not args.no_replay_milestones:
            replay_res = replay_sqlite_staging_runs(MILESTONE_SQLITE_SPECS, engine)
            publish_status(campaign_dir / "milestone-pg-replay.json", {"runs": replay_res})
            _verify_mirror_subprocess(
                ROOT
                / "data/runtime/research-resume-20261115"
                / "low-coverage-native-agy-0002/pending-staging.sqlite",
                "b85c4d84d1e36ffd744c6279b090120457011f8361329e762fc8f25bf14d4114",
                collab_dir / "staging-mirror-verification-restored.json",
            )

        reconcile_ckpt = checkpoints / "v4_reconciled.json"
        reconcile_report_path = campaign_dir / "reconciliation-report.json"
        if args.resume and reconcile_ckpt.exists() and reconcile_report_path.exists():
            v4_records, v4_texts = _load_stage_checkpoint(reconcile_ckpt, code_contract=contract)
            reconciliation = json.loads(reconcile_report_path.read_text(encoding="utf-8"))
        else:
            v4_records, v4_texts, reconciliation, diff_ledger = reconcile_v4_staging_runs(
                ROOT
                / "data/runtime/research-resume-20261115"
                / "low-coverage-native-0002/pending-staging.sqlite",
                "f59314e586e0027f0554345cec5bcdc86c3e613302b0e1cf19f379aea40dbf85",
                ROOT
                / "data/runtime/research-resume-20261115"
                / "low-coverage-native-0003/pending-staging.sqlite",
                "15da38539e2aafa9dc2de0b55caa5325f9e7296d8f37efd47ba0be5b563f6776",
                ROOT
                / "data/runtime/research-resume-20261115"
                / "low-coverage-native-agy-0002/pending-staging.sqlite",
                "b85c4d84d1e36ffd744c6279b090120457011f8361329e762fc8f25bf14d4114",
                ROOT,
            )
            change_ledger_rows.extend(diff_ledger)
            _save_stage_checkpoint(
                checkpoints, "v4_reconciled", v4_records, v4_texts, code_contract=contract
            )
            publish_status(reconcile_report_path, reconciliation)
            ledger_ckpt.write_text(
                json.dumps(change_ledger_rows, ensure_ascii=False), encoding="utf-8"
            )
        reconcile_sha = file_hash(reconcile_ckpt)

        v5_ckpt = checkpoints / "v5_initial.json"
        if args.resume and v5_ckpt.exists():
            v5_records, v5_texts = _load_stage_checkpoint(
                v5_ckpt, code_contract=contract, expected_upstream_sha256=reconcile_sha
            )
            v5_only_ids = {k for k in v5_records if k not in v4_records}
        else:
            v5_records, v5_texts, v5_only_ids = build_v5_records(v5_selection, v4_records, v4_texts)
            _save_stage_checkpoint(
                checkpoints,
                "v5_initial",
                v5_records,
                v5_texts,
                code_contract=contract,
                upstream_sha256=reconcile_sha,
            )
        v5_init_sha = file_hash(v5_ckpt)

        if args.stage == "inventory":
            print(json.dumps({"stage": "inventory", "reconciliation": reconciliation}, indent=2))
            return

        # 2. ACQUISITION (OFFLINE CACHE/STORE -> BOUNDED LIVE -> VERIFIED V1 PG FALLBACK)
        _write_coordination_record(
            collab_dir,
            campaign_dir=campaign_dir,
            v4_selection=v4_selection,
            v5_selection=v5_selection,
            stage="acquisition",
        )
        acq_stats_path = campaign_dir / "acquisition-stats.json"
        v4_acq_ckpt = checkpoints / "v4_acquired.json"
        v5_acq_ckpt = checkpoints / "v5_acquired.json"
        if (
            args.resume
            and v4_acq_ckpt.exists()
            and v5_acq_ckpt.exists()
            and acq_stats_path.exists()
        ):
            v4_records, v4_texts = _load_stage_checkpoint(
                v4_acq_ckpt, code_contract=contract, expected_upstream_sha256=reconcile_sha
            )
            v5_records, v5_texts = _load_stage_checkpoint(
                v5_acq_ckpt, code_contract=contract, expected_upstream_sha256=v5_init_sha
            )
            acquisition_stats = json.loads(acq_stats_path.read_text(encoding="utf-8"))
            if args.continue_live and not args.skip_live:
                v5_extra_map = {k: v5_records[k] for k in sorted(v5_only_ids)}
                exhausted_v4 = (ROOT / "data/derived/lyrics/low-coverage-native-agy-20261115",)
                v4_live_cont = run_bounded_live_recovery(
                    v4_records,
                    v4_texts,
                    ROOT,
                    campaign_dir / "store-v4",
                    change_ledger_rows,
                    max_candidates=args.max_live_v4,
                    max_seconds=args.max_seconds,
                    workers=args.workers,
                    label="v4_cont",
                    exclude_exhausted_stores=exhausted_v4,
                    extra_cache_sources=EXTRA_CACHE_SOURCES,
                )
                v5_live_cont = run_bounded_live_recovery(
                    v5_extra_map,
                    v5_texts,
                    ROOT,
                    campaign_dir / "store-v5",
                    change_ledger_rows,
                    max_candidates=args.max_live_v5,
                    max_seconds=args.max_seconds,
                    workers=args.workers,
                    label="v5_si_cont",
                    extra_cache_sources=EXTRA_CACHE_SOURCES,
                )
                for cid, rec in v4_records.items():
                    if cid in v5_records:
                        v5_records[cid] = {**rec, "payload": v5_records[cid]["payload"]}
                        if rec.get("text_sha256"):
                            v5_texts[rec["text_sha256"]] = v4_texts[rec["text_sha256"]]
                for cid, rec in v5_extra_map.items():
                    v5_records[cid] = rec
                acquisition_stats["v4_live_cont"] = v4_live_cont
                acquisition_stats["v5_live_cont"] = v5_live_cont
                _save_stage_checkpoint(
                    checkpoints,
                    "v4_acquired",
                    v4_records,
                    v4_texts,
                    code_contract=contract,
                    upstream_sha256=reconcile_sha,
                )
                _save_stage_checkpoint(
                    checkpoints,
                    "v5_acquired",
                    v5_records,
                    v5_texts,
                    code_contract=contract,
                    upstream_sha256=v5_init_sha,
                )
                publish_status(acq_stats_path, acquisition_stats)
                ledger_ckpt.write_text(
                    json.dumps(change_ledger_rows, ensure_ascii=False), encoding="utf-8"
                )
        else:
            v4_offline = run_offline_store_and_cache_pass(
                v4_records,
                v4_texts,
                ROOT,
                campaign_dir / "offline-cache-v4",
                LEGACY_STORES,
                change_ledger_rows,
                label="v4",
                extra_cache_sources=EXTRA_CACHE_SOURCES,
            )
            # Only process distinct v5-only (Slovenia IPF) targets in v5 acquisition passes
            v5_extra_map = {k: v5_records[k] for k in sorted(v5_only_ids)}
            v5_offline = run_offline_store_and_cache_pass(
                v5_extra_map,
                v5_texts,
                ROOT,
                campaign_dir / "offline-cache-v5",
                LEGACY_STORES,
                change_ledger_rows,
                label="v5_si",
                extra_cache_sources=EXTRA_CACHE_SOURCES,
            )

            if args.skip_live:
                v4_live: dict[str, Any] = {"skipped_live": True, "attempted": 0, "recovered": 0}
                v5_live: dict[str, Any] = {"skipped_live": True, "attempted": 0, "recovered": 0}
            else:
                exhausted_v4 = (ROOT / "data/derived/lyrics/low-coverage-native-agy-20261115",)
                v4_live = run_bounded_live_recovery(
                    v4_records,
                    v4_texts,
                    ROOT,
                    campaign_dir / "store-v4",
                    change_ledger_rows,
                    max_candidates=args.max_live_v4,
                    max_seconds=args.max_seconds,
                    workers=args.workers,
                    label="v4",
                    exclude_exhausted_stores=exhausted_v4,
                    extra_cache_sources=EXTRA_CACHE_SOURCES,
                )
                v5_live = run_bounded_live_recovery(
                    v5_extra_map,
                    v5_texts,
                    ROOT,
                    campaign_dir / "store-v5",
                    change_ledger_rows,
                    max_candidates=args.max_live_v5,
                    max_seconds=args.max_seconds,
                    workers=args.workers,
                    label="v5_si",
                    extra_cache_sources=EXTRA_CACHE_SOURCES,
                )

            v4_pg_fb = apply_pg_v1_clean_fallback(
                v4_records, v4_texts, engine, change_ledger_rows, label="v4"
            )
            v5_pg_fb = apply_pg_v1_clean_fallback(
                v5_extra_map, v5_texts, engine, change_ledger_rows, label="v5_si"
            )

            # Sync v4 updates + v5_only updates into unified v5_records map
            for cid, rec in v4_records.items():
                if cid in v5_records:
                    v5_records[cid] = {
                        **rec,
                        "payload": v5_records[cid]["payload"],
                    }
                    if rec.get("text_sha256"):
                        v5_texts[rec["text_sha256"]] = v4_texts[rec["text_sha256"]]
            for cid, rec in v5_extra_map.items():
                v5_records[cid] = rec
                if rec.get("text_sha256"):
                    v5_texts[rec["text_sha256"]] = v5_texts[rec["text_sha256"]]

            acquisition_stats = {
                "v4_offline": v4_offline,
                "v5_offline": v5_offline,
                "v4_live": v4_live,
                "v5_live": v5_live,
                "v4_pg_v1_fallback": v4_pg_fb,
                "v5_pg_v1_fallback": v5_pg_fb,
            }
            _save_stage_checkpoint(
                checkpoints,
                "v4_acquired",
                v4_records,
                v4_texts,
                code_contract=contract,
                upstream_sha256=reconcile_sha,
            )
            _save_stage_checkpoint(
                checkpoints,
                "v5_acquired",
                v5_records,
                v5_texts,
                code_contract=contract,
                upstream_sha256=v5_init_sha,
            )
            publish_status(acq_stats_path, acquisition_stats)
            ledger_ckpt.write_text(
                json.dumps(change_ledger_rows, ensure_ascii=False), encoding="utf-8"
            )
        v4_acq_sha = file_hash(v4_acq_ckpt)
        v5_acq_sha = file_hash(v5_acq_ckpt)

        if args.stage == "acquisition":
            print(json.dumps({"stage": "acquisition", "stats": acquisition_stats}, indent=2))
            return

        # 3. TECHNICAL VERIFICATION
        _write_coordination_record(
            collab_dir,
            campaign_dir=campaign_dir,
            v4_selection=v4_selection,
            v5_selection=v5_selection,
            stage="technical_verification",
        )
        v4_ver_ckpt = checkpoints / "v4_verified.json"
        v5_ver_ckpt = checkpoints / "v5_verified.json"
        ver_summary_path = campaign_dir / "verification-summary.json"
        reuse_verification = (
            args.resume
            and v4_ver_ckpt.exists()
            and v5_ver_ckpt.exists()
            and ver_summary_path.exists()
        )
        if reuse_verification:
            try:
                verified_v4_records, verified_v4_texts = _load_stage_checkpoint(
                    v4_ver_ckpt, code_contract=contract, expected_upstream_sha256=v4_acq_sha
                )
                verified_v5_records, verified_v5_texts = _load_stage_checkpoint(
                    v5_ver_ckpt, code_contract=contract, expected_upstream_sha256=v5_acq_sha
                )
                ver_summary = json.loads(ver_summary_path.read_text(encoding="utf-8"))
                v4_records, v4_texts = verified_v4_records, verified_v4_texts
                v5_records, v5_texts = verified_v5_records, verified_v5_texts
            except (ValueError, KeyError, json.JSONDecodeError) as error:
                archive_dir = _archive_invalidated_checkpoints(
                    campaign_dir,
                    [v4_ver_ckpt, v5_ver_ckpt, ver_summary_path],
                    reason=f"resume checkpoint rejected: {type(error).__name__}: {error}",
                    expected_upstream={"v4": v4_acq_sha, "v5": v5_acq_sha},
                )
                print(
                    json.dumps(
                        {
                            "stage": "technical_verification",
                            "checkpoint_resume": "invalidated_and_rebuilt",
                            "archived_checkpoints": str(archive_dir),
                        }
                    ),
                    flush=True,
                )
                reuse_verification = False
        if reuse_verification:
            v4_rec_list = [v4_records[k] for k in sorted(v4_records)]
            v5_rec_list = [v5_records[k] for k in sorted(v5_records)]
        else:
            v4_rec_list, v4_ver = verify_all_candidates(
                v4_records,
                v4_texts,
                ROOT,
                selection_hash=file_hash(v4_selection / "manifest.json"),
            )
            v5_rec_list, v5_ver = verify_all_candidates(
                v5_records,
                v5_texts,
                ROOT,
                selection_hash=file_hash(v5_selection / "manifest.json"),
            )
            v4_records = {r["candidate_id"]: r for r in v4_rec_list}
            v5_records = {r["candidate_id"]: r for r in v5_rec_list}
            ver_summary = {"v4": v4_ver, "v5": v5_ver}
            _save_stage_checkpoint(
                checkpoints,
                "v4_verified",
                v4_records,
                v4_texts,
                code_contract=contract,
                upstream_sha256=v4_acq_sha,
            )
            _save_stage_checkpoint(
                checkpoints,
                "v5_verified",
                v5_records,
                v5_texts,
                code_contract=contract,
                upstream_sha256=v5_acq_sha,
            )
            publish_status(ver_summary_path, ver_summary)

        if args.stage == "technical_verification":
            print(json.dumps({"stage": "technical_verification", **ver_summary}, indent=2))
            return

        # 4. REVIEW QUEUES & CHANGE LEDGER
        _write_coordination_record(
            collab_dir,
            campaign_dir=campaign_dir,
            v4_selection=v4_selection,
            v5_selection=v5_selection,
            stage="review_queue",
        )
        v5_extra_list = [v5_records[k] for k in sorted(v5_only_ids)]
        review_dir = campaign_dir / "review"
        queue_result = write_queues_and_change_ledger(
            output_dir, v4_rec_list, v5_extra_list, change_ledger_rows, review_dir
        )
        review_packets = _export_review_packets(review_dir, v4_rec_list)
        queue_result["review_packets"] = review_packets
        publish_status(campaign_dir / "queue-and-ledger-summary.json", queue_result)
        if args.stage == "review_queue":
            print(json.dumps({"stage": "review_queue", **queue_result}, indent=2))
            return

        # 5. PERSISTENCE RECONCILIATION (LOCAL SQLITE + POSTGRESQL PARITY)
        _write_coordination_record(
            collab_dir,
            campaign_dir=campaign_dir,
            v4_selection=v4_selection,
            v5_selection=v5_selection,
            stage="persistence_reconciliation",
        )
        v4_manifest, _, v4_members, _ = load_selection(v4_selection)
        v5_manifest, _, v5_members, _ = load_selection(v5_selection)
        v4_persist = persist_verified_staging(
            v4_rec_list,
            v4_texts,
            selection_dir=v4_selection,
            local_sqlite_path=campaign_dir / "staging-v4/pending-staging.sqlite",
            pg_engine=engine,
            phase="pipeline-reconciled-final",
            memberships_count=v4_manifest["memberships"],
            extra_manifest={
                "updated_at": datetime.now(UTC).isoformat(),
                "selection_version": "v4-final-0002",
                "code_contract": contract,
            },
        )
        v5_persist = persist_verified_staging(
            v5_rec_list,
            v5_texts,
            selection_dir=v5_selection,
            local_sqlite_path=campaign_dir / "staging-v5/pending-staging.sqlite",
            pg_engine=engine,
            phase="pipeline-reconciled-final-v5-provisional",
            memberships_count=v5_manifest["memberships"],
            extra_manifest={
                "updated_at": datetime.now(UTC).isoformat(),
                "selection_version": "v5-published-provisional-0003",
                "code_contract": contract,
            },
        )
        v4_mirror = _verify_mirror_subprocess(
            Path(v4_persist["local_sqlite"]),
            v4_persist["run_id"],
            campaign_dir / "mirror-verify-v4.json",
        )
        v5_mirror = _verify_mirror_subprocess(
            Path(v5_persist["local_sqlite"]),
            v5_persist["run_id"],
            campaign_dir / "mirror-verify-v5.json",
        )
        pg_inventory = db_health.current_inventory(ROOT, v4_selection, engine=engine)
        if args.stage == "persistence_reconciliation":
            print(
                json.dumps(
                    {
                        "stage": "persistence_reconciliation",
                        "v4_run_id": v4_persist["run_id"],
                        "v5_run_id": v5_persist["run_id"],
                        "v4_mirror": v4_mirror,
                        "v5_mirror": v5_mirror,
                    },
                    indent=2,
                )
            )
            return

        # 6. REFRESHED INVENTORY (JSON + DYNAMIC HTML)
        _write_coordination_record(
            collab_dir,
            campaign_dir=campaign_dir,
            v4_selection=v4_selection,
            v5_selection=v5_selection,
            stage="refreshed_inventory",
        )
        cohort_metrics = fetch_postgres_cohort_metrics(engine)
        _, snapshot_created_at, _, _ = load_sqlite_staging_snapshot(
            Path(v4_persist["local_sqlite"]), v4_persist["run_id"]
        )
        inventory_export = rebuild_inventory_outputs(
            output_dir,
            v4_selection_dir=v4_selection,
            v5_selection_dir=v5_selection,
            v4_run_id=v4_persist["run_id"],
            v5_run_id=v5_persist["run_id"],
            snapshot_created_at=snapshot_created_at,
            v4_records_by_id=v4_records,
            v5_records_by_id=v5_records,
            cohort_metrics=cohort_metrics,
        )
        if args.stage == "refreshed_inventory":
            print(json.dumps({"stage": "refreshed_inventory", **inventory_export}, indent=2))
            return

        # 7. COMPLETION REPORT & FROZEN HANDOFF
        _write_coordination_record(
            collab_dir,
            campaign_dir=campaign_dir,
            v4_selection=v4_selection,
            v5_selection=v5_selection,
            stage="completion_report",
        )
        report_json, handoff_md = _write_completion_reports(
            collab_dir=collab_dir,
            campaign_dir=campaign_dir,
            output_dir=output_dir,
            reconciliation=reconciliation,
            acquisition_stats=acquisition_stats,
            v4_verification=ver_summary["v4"],
            v5_verification=ver_summary["v5"],
            queue_result=queue_result,
            v4_persist=v4_persist,
            v5_persist=v5_persist,
            v4_mirror=v4_mirror,
            v5_mirror=v5_mirror,
            pg_inventory=pg_inventory,
            inventory_export=inventory_export,
            cohort_metrics=cohort_metrics,
        )
        print(
            json.dumps(
                {
                    "stage": "completed",
                    "v4_run_id": v4_persist["run_id"],
                    "v5_run_id": v5_persist["run_id"],
                    "v4_resumo": inventory_export["v4_resumo"],
                    "v5_resumo": inventory_export["v5_resumo"],
                    "completion_report": str(report_json),
                    "handoff_md": str(handoff_md),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
