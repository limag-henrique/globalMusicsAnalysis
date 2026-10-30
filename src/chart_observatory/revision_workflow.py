"""One local entry point for preparation, evidence gates and reproducible diagnostics.

The current campaign explicitly authorizes preparation without paid inference.
Blocked scientific stages remain blocked; diagnostic exports are labeled drafts.
"""

import argparse
import csv
import importlib.util
import json
import os
import shutil
import sqlite3
import subprocess
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

os.environ.setdefault("POLARS_MAX_THREADS", "2")

from chart_observatory.lyrics.campaign_budget import CampaignBudget
from chart_observatory.pipeline_state import StageResult, StageRunner, file_hash, process_alive

STAGES = (
    "inventariar",
    "recuperar_paradas",
    "selecionar_candidatos",
    "resolver_identidades",
    "recuperar_letras",
    "validar_letras",
    "preparar_piloto",
    "classificar",
    "revisar",
    "congelar_selecao",
    "calcular_rankings",
    "gerar_artigo_pacote",
)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig")) if Path(path).is_file() else {}


def save_json(path, value):
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, default=str)
    path = Path(path)
    if not path.exists() or path.read_text(encoding="utf-8") != payload:
        path.write_text(payload, encoding="utf-8")


def json_rows(path):
    if Path(path).is_file():
        with Path(path).open("rb") as handle:
            for line in handle:
                if not line.endswith(b"\n"):
                    break
                if line.strip():
                    yield json.loads(line)


def reconcile_budget(project, state):
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    from chart_observatory.config import Settings
    from chart_observatory.lyrics.revision_budget import RevisionBudgetPolicy

    ledger = CampaignBudget(state / "campaign-budget.sqlite")
    declaration = read_json(state / "external-expense-attestation.json")
    if declaration.get("no_unrecorded_campaign_expenses") is True:
        ledger.attest(external_complete=True, evidence=declaration)
    engine = None
    database = {"available": False}
    try:
        engine = create_engine(
            Settings.load(project).database_url, connect_args={"connect_timeout": 3}
        )
        with Session(engine) as session:
            session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            RevisionBudgetPolicy(budget_path=ledger.path).reconcile(session)
        database["available"] = True
    except Exception as exc:
        database["error_type"] = type(exc).__name__
        ledger.attest(provider_complete=False, evidence=database)
    finally:
        if engine is not None:
            engine.dispose()
    return {**ledger.snapshot(), "database": database}


def registry_counts(path):
    result = {
        "platform_identity_claims": 0,
        "recordings": 0,
        "textual_editions": 0,
        "validated_editions": 0,
        "classification_requests": 0,
        "completed_requests": 0,
    }
    if Path(path).is_file():
        with sqlite3.connect(f"file:{Path(path).as_posix()}?mode=ro", uri=True) as conn:
            for table in (
                "platform_identity_claims",
                "recordings",
                "textual_editions",
                "classification_requests",
            ):
                result[table] = conn.execute("SELECT count(*) FROM " + table).fetchone()[0]
            result["validated_editions"] = conn.execute("""SELECT count(*) FROM textual_editions
                WHERE identity_confirmed=1 AND integrity_validated=1
                AND instrumental=0""").fetchone()[0]
            result["completed_requests"] = conn.execute("""SELECT count(*)
                FROM classification_requests WHERE state='completed'""").fetchone()[0]
    return result


def _recovery(project, prepared, output, previous, resume):
    spec = importlib.util.spec_from_file_location(
        "revision_recovery_report", project / "scripts/report_lyrics_recovery.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    acquisition = prepared / "acquisition"
    targets = prepared / "recovery-targets.jsonl"
    if not targets.exists():
        return StageResult("blocked", reason="recovery targets are missing")
    progress = module.summarize(targets, acquisition / "acquisition.jsonl")
    job = read_json(acquisition / "process.json")
    live = process_alive(job.get("pid"))
    checkpoint = {
        "processed": progress["processed_documents"],
        "observed_at": datetime.now(UTC).isoformat(),
        "pid": job.get("pid"),
    }
    eta = None
    if previous.get("observed_at"):
        elapsed = (
            datetime.fromisoformat(checkpoint["observed_at"])
            - datetime.fromisoformat(previous["observed_at"])
        ).total_seconds()
        gained = checkpoint["processed"] - previous.get("processed", checkpoint["processed"])
        if elapsed > 0 and gained > 0:
            eta = progress["pending_documents"] / (gained / elapsed)
    progress["acquisition_round_eta_seconds"] = eta
    progress["scientific_completion_eta_seconds"] = None
    progress["attempts"] = sum(1 for _ in json_rows(acquisition / "acquisition.jsonl"))
    progress["valid_lyrics"] = 0  # Retrieval candidates are not adjudicated lyrics.
    if resume and not live and progress["pending_documents"]:
        cache = project / (
            "data/derived/research_quality/corpus-revision-20261023/"
            "recovery-resumed-20261023/http-cache"
        )
        if min(shutil.disk_usage(acquisition).free, shutil.disk_usage(cache).free) < 1024**3:
            save_json(output / "recovery.json", progress)
            return StageResult(
                "blocked",
                progress,
                checkpoint,
                [output / "recovery.json"],
                "less than 1 GiB free on acquisition or cache volume",
            )
        # One CLI owner per stage; an existing live collector is never started twice.
        rounds = read_json(acquisition / "pipeline-rounds.json")
        target_hash = file_hash(targets)
        count = rounds.get("rounds", 0) if rounds.get("target_hash") == target_hash else 0
        if count >= 3:
            return StageResult(
                "blocked",
                progress,
                checkpoint,
                reason="three recovery rounds exhausted; inspect failures",
            )
        command = [
            str(project / ".venv/Scripts/python.exe"),
            "-u",
            str(project / "scripts/recover_reviewed_lyrics.py"),
            "--targets-jsonl",
            str(targets),
            "--output-dir",
            str(acquisition),
            "--cache-dir",
            str(cache),
            "--limit",
            str(progress["target_documents"]),
            "--workers",
            "2",
            "--all-sources",
        ]
        temporary = project / "data/runtime/tmp"
        temporary.mkdir(parents=True, exist_ok=True)
        env = {
            **os.environ,
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONIOENCODING": "utf-8",
            "TEMP": str(temporary),
            "TMP": str(temporary),
            "TMPDIR": str(temporary),
        }
        with (
            (acquisition / "stdout.log").open("ab") as out,
            (acquisition / "stderr.log").open("ab") as err,
        ):
            child = subprocess.Popen(
                command,
                cwd=project,
                env=env,
                stdout=out,
                stderr=err,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        save_json(
            acquisition / "process.json",
            {
                "pid": child.pid,
                "command": command,
                "started_at": checkpoint["observed_at"],
                "workers": 2,
                "paid_calls": 0,
            },
        )
        save_json(
            acquisition / "pipeline-rounds.json", {"target_hash": target_hash, "rounds": count + 1}
        )
        checkpoint["pid"], live = child.pid, True
    progress["process_alive"] = live
    save_json(output / "recovery.json", progress)
    return StageResult(
        "running" if live else "completed_with_deficits",
        progress,
        checkpoint,
        [output / "recovery.json"],
        "round completion is not textual or scientific validation",
    )


def diagnostic_rankings(prepared, output):
    import polars as pl

    from chart_observatory.analysis.revision_rankings import BINDING, GROUP, build_rankings

    source = prepared / "original_top80.jsonl"
    base = (
        pl.read_ndjson(source)
        .select(
            *[k for k in GROUP if k != "sample"],
            "candidate_id",
            "coverage_status",
            "metric_value",
        )
        .with_columns(
            pl.lit("original").alias("sample"),
            pl.lit(False).alias("text_validated"),
            pl.lit("pending").alias("applicability"),
            pl.lit(None, dtype=pl.String).alias("recording_id"),
            *[pl.lit(None, dtype=pl.String).alias(k) for k in BINDING],
        )
    )
    labels = pl.DataFrame(
        schema={
            **{k: pl.String for k in BINDING},
            "topic": pl.String,
            "score": pl.Int64,
            "classification_status": pl.String,
        }
    )
    result = build_rankings(base, labels)
    path = output / "missing-lyrics-scenarios.csv"
    result.write_csv(path)
    return path, {
        "topic_market_period_rows": result.height,
        "publishable_country_ranks": result["country_rank"].count(),
        "status": "diagnostic_only_not_corrected_results",
    }


def run_workflow(
    project,
    state,
    prepared,
    reviews,
    *,
    through=STAGES[-1],
    only=None,
    resume=False,
    retry_failed=False,
):
    project, state, prepared, reviews = [
        Path(path).resolve() for path in (project, state, prepared, reviews)
    ]
    if os.name == "nt" and project.drive.upper() != "D:":
        raise ValueError("Campaign project must remain on D:")
    if any(not path.is_relative_to(project) for path in (state, prepared, reviews)):
        raise ValueError("Campaign files must remain physically inside the project on D:")
    state.mkdir(parents=True, exist_ok=True)
    budget = reconcile_budget(project, state)
    identities = registry_counts(project / "data/derived/annual_revision/revision-registry.sqlite")
    save_json(state / "budget-snapshot.json", budget)
    save_json(state / "identity-snapshot.json", identities)
    save_json(state / "recovery-control.json", {"resume_collection": resume})
    runner = StageRunner(state)
    selection = read_json(prepared / "manifest.json")
    review = read_json(reviews / "manifest.json")
    coverage = prepared / "country-year-platform-coverage.csv"
    criteria = read_json(reviews / "quality-criteria-proposal.json")
    checks = {
        "selectors_tested": False,
        "deficits_documented": coverage.is_file(),
        "identities_and_texts_validated": identities["validated_editions"] > 0,
        "compatible_classifications": identities["completed_requests"] > 0,
        "eight_cases_recorded": review.get("eight_cases") == 8,
        "pilot_and_independent_validation_accepted": False,
        "costs_reconciled_within_180": budget["reconciled"] and budget["within_limits"],
        "selection_scientifically_frozen": False,
    }
    receipt = read_json(state / "test-receipt.json")
    checks["selectors_tested"] = bool(
        receipt.get("all_passed") is True
        and receipt.get("code_hashes")
        and all(
            file_hash(project / path) == digest for path, digest in receipt["code_hashes"].items()
        )
    )
    quality = read_json(reviews / "accepted-quality-report.json")
    checks["pilot_and_independent_validation_accepted"] = bool(
        quality.get("pilot_accepted") is True
        and quality.get("independent_validation_accepted") is True
        and quality.get("criteria_sha256") == file_hash(reviews / "quality-criteria-proposal.json")
        and quality.get("raw_review_evidence_sha256")
    )
    # No paid inference has been authorized in this campaign preparation.
    checks["paid_execution_authorized"] = False
    save_json(state / "readiness-input.json", checks)
    results = {}
    diagnostic = None
    selected_stages = (only,) if only is not None else STAGES[: STAGES.index(through) + 1]
    if any(name not in STAGES for name in selected_stages):
        raise ValueError("unknown workflow stage")
    for name in selected_stages:
        inputs = {"workflow": Path(__file__), "selection_manifest": prepared / "manifest.json"}
        if name in {"classificar", "revisar", "congelar_selecao", "gerar_artigo_pacote"}:
            inputs["readiness"] = state / "readiness-input.json"
        if name in {"inventariar", "recuperar_paradas", "validar_letras"}:
            inputs.update(coverage=coverage, budget=state / "budget-snapshot.json")
        if name in {"selecionar_candidatos", "calcular_rankings"}:
            inputs["original"] = prepared / "original_top80.jsonl"
            inputs["eligible"] = prepared / "eligible.jsonl"
        if name == "calcular_rankings":
            inputs["coverage"] = coverage
            inputs["ranking_implementation"] = (
                Path(__file__).parent / "analysis/revision_rankings.py"
            )
        if name in {"resolver_identidades", "validar_letras", "classificar"}:
            inputs["identities"] = state / "identity-snapshot.json"
        if name == "recuperar_letras":
            inputs["control"] = state / "recovery-control.json"
            inputs["collector"] = project / "scripts/recover_reviewed_lyrics.py"
            inputs["recovery_report"] = project / "scripts/report_lyrics_recovery.py"
            inputs["ledger"] = prepared / "acquisition/acquisition.jsonl"
            inputs["targets"] = prepared / "recovery-targets.jsonl"
            inputs["process"] = prepared / "acquisition/process.json"
        if name in {"preparar_piloto", "revisar", "congelar_selecao", "gerar_artigo_pacote"}:
            inputs["review_manifest"] = reviews / "manifest.json"
            inputs["quality"] = reviews / "accepted-quality-report.json"
            inputs["criteria"] = reviews / "quality-criteria-proposal.json"
        if name == "gerar_artigo_pacote":
            inputs["coverage"] = coverage
            inputs["budget"] = state / "budget-snapshot.json"
            if diagnostic is not None:
                inputs["diagnostic"] = diagnostic

        def action(output, checkpoint, stage=name, stage_inputs=inputs):
            nonlocal diagnostic
            if stage == "recuperar_letras":
                return _recovery(project, prepared, output, checkpoint, resume)
            if stage == "inventariar":
                return StageResult(
                    "completed_with_deficits",
                    {**selection, "costs": budget, "scientific_ready": False},
                )
            if stage == "recuperar_paradas":
                with coverage.open(encoding="utf-8-sig") as handle:
                    rows = list(csv.DictReader(handle))
                return StageResult(
                    "completed_with_deficits",
                    dict(Counter(r["coverage_status"] for r in rows)),
                    reason="unavailable periods remain deficits",
                )
            if stage == "selecionar_candidatos":
                return StageResult(
                    "completed_with_deficits",
                    {
                        "original_positions": sum(
                            1 for _ in json_rows(prepared / "original_top80.jsonl")
                        ),
                        "eligible_positions": sum(
                            1 for _ in json_rows(prepared / "eligible.jsonl")
                        ),
                        "candidate_limit": selection.get("candidate_limit"),
                    },
                )
            if stage in {"resolver_identidades", "validar_letras"}:
                return StageResult(
                    "blocked", identities, reason="identity/text adjudication pending"
                )
            if stage == "preparar_piloto":
                return StageResult(
                    "blocked", review, reason="validated pilot and two reviewers pending"
                )
            if stage == "classificar":
                return StageResult(
                    "blocked",
                    {"paid_calls": 0, **identities},
                    reason=(
                        "paid inference not authorized; prices, exact token audit and pilot pending"
                    ),
                )
            if stage == "revisar":
                return StageResult(
                    "blocked",
                    {"criteria_status": criteria.get("status")},
                    reason="independent, blinded and adjudicated validation pending",
                )
            if stage == "congelar_selecao":
                return StageResult(
                    "blocked", checks, reason="scientific acceptance criteria are not all satisfied"
                )
            if stage == "calcular_rankings":
                path, counts = diagnostic_rankings(prepared, output)
                diagnostic = path
                return StageResult(
                    "blocked",
                    counts,
                    files=[path],
                    reason="only missing-data scenarios; no validated corrected ranking",
                )
            draft = output / "article-methods-draft.md"
            draft.write_text(
                "# Revisão metodológica do painel musical 2017–2026\n\n"
                "Estado: rascunho de preparação, sem resultados corrigidos validados.\n\n"
                "A pesquisa descreve temas em músicas populares nos mercados observados. "
                "Não identifica atributos dos habitantes ou nacionalidade dos artistas.\n\n"
                "Integridade computacional, fidelidade da letra e validade temática são "
                "verificações independentes. O top 80 original permanece separado da seleção "
                "elegível com reservas. Plataforma, denominador, período e cobertura serão "
                "informados em cada indicador, com presença temática a partir de 2.\n\n"
                "Não se somam os 26 tópicos ou streams com visualizações. Cenários extremos "
                "de ausência e presença entre letras desconhecidas são sensibilidades, "
                "não estimativas corrigidas nem intervalos que resolvem viés de cobertura.\n\n"
                "Anos completos e intervalos equivalentes a 2026 são analisados separadamente. "
                "Efeitos sobre classificações e posições dos países permanecem não estimados. "
                "A edição anterior é preservada. O teto da campanha é US$180; novos envios "
                "dependem de reconciliação, preços confirmados e validação.\n",
                encoding="utf-8",
            )
            acceptance = output / "acceptance.json"
            save_json(
                acceptance,
                {
                    "criteria": checks,
                    "scientific_ready": False,
                    "status": "preparation_only",
                    "input_hashes": {role: file_hash(path) for role, path in stage_inputs.items()},
                },
            )
            package = output / "preparation-package.zip"
            with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as bundle:
                for path in (draft, acceptance, coverage):
                    bundle.write(path, path.name)
                if diagnostic is not None:
                    bundle.write(diagnostic, diagnostic.name)
            return StageResult(
                "completed_with_deficits",
                {"scientific_ready": False, "lyrics_distributed": 0},
                files=[draft, acceptance, package],
                reason="local methods draft only; publication remains blocked",
            )

        result = runner.run(name, inputs, action, retry_failed=retry_failed)
        results[name] = result
        if name == "calcular_rankings" and diagnostic is None:
            diagnostic = next(
                (
                    Path(path)
                    for path in result.get("outputs", {})
                    if path.endswith("missing-lyrics-scenarios.csv")
                ),
                None,
            )
    summary = {
        "stages": results,
        "acceptance": checks,
        "scientific_ready": False,
        "paid_calls": 0,
        "budget": budget,
        "stage_execution_is_not_scientific_completion": True,
    }
    save_json(state / "pipeline-report.json", summary)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--state-root", type=Path)
    parser.add_argument("--prepared", type=Path)
    parser.add_argument("--reviews", type=Path)
    parser.add_argument("--through", choices=STAGES, default=STAGES[-1])
    parser.add_argument("--only", choices=STAGES, help="Run one independent stage")
    parser.add_argument("--resume-collection", action="store_true")
    parser.add_argument("--retry-failed", action="store_true")
    args = parser.parse_args(argv)
    root = args.project.resolve()
    base = root / "data/derived/annual_revision"
    report = run_workflow(
        root,
        args.state_root or base / "runtime",
        args.prepared or base / "20261025-final",
        args.reviews or base / "20261025-review-v2",
        through=args.through,
        only=args.only,
        resume=args.resume_collection,
        retry_failed=args.retry_failed,
    )
    print(
        json.dumps(
            {
                "scientific_ready": report["scientific_ready"],
                "paid_calls": 0,
                "stages": {
                    name: {"status": row["status"], "cached": row.get("cached")}
                    for name, row in report["stages"].items()
                },
            }
        )
    )
    return 1 if any(row["status"] == "failed" for row in report["stages"].values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
