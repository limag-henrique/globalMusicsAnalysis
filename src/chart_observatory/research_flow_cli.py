# ruff: noqa: B008
"""Local research audit and preparation commands. No paid provider interaction."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import UUID

import typer

from chart_observatory import research_flow as flow
from chart_observatory import research_rankings
from chart_observatory.lyrics.classification_gate import ClassificationGate
from chart_observatory.lyrics.research_contract import (
    build_profile,
    prepare_request,
    table_row,
    validate_rubric,
)
from chart_observatory.lyrics.revision_protocol import canonical_json
from chart_observatory.pipeline_state import file_hash

app = typer.Typer(help="Audit frozen research gates and prepare private, unsent requests.")


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _failure(exc: Exception):
    # Database errors can contain connection strings. Print only safe validation details.
    detail = str(exc) if isinstance(exc, (ValueError, FileNotFoundError)) else type(exc).__name__
    typer.echo(json.dumps({"error": detail}, ensure_ascii=False), err=True)
    raise typer.Exit(code=1) from exc


def reconstruct_local(
    *,
    observations: Path,
    output: Path,
    country: str,
    year: int,
    platform: str,
    provider: str,
    quota: int,
    depth: int,
    frequency: str,
    expected_periods: Path | None = None,
) -> dict:
    if output.exists():
        raise ValueError("reconstruction output already exists; use a new version directory")
    inputs = [
        observations.resolve(),
        Path(research_rankings.__file__).resolve(),
        Path(__file__).resolve(),
    ]
    if expected_periods is not None:
        inputs.append(expected_periods.resolve())
    hashes = {str(path): file_hash(path) for path in inputs}
    if any(digest is None for digest in hashes.values()):
        raise ValueError("reconstruction input is missing")
    schedule = _read_json(expected_periods) if expected_periods is not None else None
    if schedule is not None and not isinstance(schedule, list):
        raise ValueError("expected periods must be a JSON list of ISO period-end dates")
    result = research_rankings.reconstruct_chart_sum(
        flow.rows(observations),
        country_code=country,
        year=year,
        platform=platform,
        provider=provider,
        quota=quota,
        expected_depth=depth,
        frequency=frequency,
        expected_period_ends=schedule,
    )
    if any(file_hash(path) != digest for path, digest in hashes.items()):
        raise ValueError("reconstruction input changed during processing")
    output.mkdir(parents=True, exist_ok=False)
    flow.write_json(output / "reconstruction.json", result)
    flow.write_rows(output / "ranked_rows.jsonl", result["rows"])
    flow.write_json(
        output / "manifest.json",
        {
            "protocol": result["version"],
            "input_hashes": hashes,
            "reconstruction_approved": result["approved"],
            "scientific_approval": False,
            "paid_calls": 0,
            "uploads": 0,
            "artifacts": {
                path.name: file_hash(path) for path in output.iterdir() if path.is_file()
            },
        },
    )
    return result


@app.command("reconstruct")
def reconstruct_command(
    observations: Path = typer.Option(
        ..., "--observations", "--input", help="Normalized chart observations JSONL."
    ),
    output: Path = typer.Option(..., help="New reconstruction directory."),
    country: str = typer.Option(..., help="Frozen chart market code."),
    year: int = typer.Option(..., help="Annual window, assigned by native period end."),
    platform: str = typer.Option(..., help="One platform only, e.g. SPOTIFY."),
    provider: str = typer.Option(..., help="One provider only, e.g. MGD."),
    quota: int = typer.Option(..., help="Requested annual depth."),
    depth: int = typer.Option(..., help="Expected native chart depth per period."),
    frequency: str = typer.Option(..., help="daily or weekly."),
    expected_periods: Path | None = typer.Option(
        None,
        help="JSON list of ISO period ends; required for weekly reconstruction.",
    ),
):
    try:
        result = reconstruct_local(
            observations=observations,
            output=output,
            country=country,
            year=year,
            platform=platform,
            provider=provider,
            quota=quota,
            depth=depth,
            frequency=frequency,
            expected_periods=expected_periods,
        )
        typer.echo(
            json.dumps(
                {
                    "output": str(output.resolve()),
                    "reconstruction_approved": result["approved"],
                    "reasons": result["reasons"],
                    "counts": result["counts"],
                    "scientific_approval": False,
                    "paid_calls": 0,
                    "uploads": 0,
                },
                ensure_ascii=False,
            )
        )
    except Exception as exc:
        _failure(exc)


@app.command("audit")
def audit_command(
    selection: Path = typer.Option(..., help="Frozen worldwide selection directory."),
    output: Path = typer.Option(..., help="New immutable audit directory."),
    actor: str = typer.Option(..., help="Person responsible for this audit invocation."),
    evidence: Path | None = typer.Option(None, help="Explicit hash-bound research evidence JSON."),
    project: Path = typer.Option(Path.cwd(), help="Project root for data and evidence references."),
):
    try:
        report = flow.audit_research_flow(
            project=project,
            selection=selection,
            output=output,
            actor=actor,
            evidence_path=evidence,
        )
        typer.echo(
            json.dumps(
                {
                    "output": str(output.resolve()),
                    "protocol": report["protocol"],
                    "actor": report["actor"],
                    "inventory": report["inventory"],
                    "gates": {gate["gate"]: gate["state"] for gate in report["gates"]},
                    "research_ready": report["research_ready"],
                    "paid_calls": 0,
                    "uploads": 0,
                },
                ensure_ascii=False,
            )
        )
    except Exception as exc:
        _failure(exc)


@app.command("verify")
def verify_command(audit: Path = typer.Option(..., help="Previously generated audit directory.")):
    try:
        report = flow.verify_audit(audit)
        typer.echo(
            json.dumps(
                {
                    "integrity": "verified",
                    "audit": str(audit.resolve()),
                    "protocol": report["protocol"],
                    "research_ready": report["research_ready"],
                    "scientific_approval_rechecked": False,
                },
                ensure_ascii=False,
            )
        )
    except Exception as exc:
        _failure(exc)


@app.command("require")
def require_command(
    audit: Path = typer.Option(..., help="Immutable research audit directory."),
    gate: str = typer.Option(..., help="Required scientific gate: G1, G2, G3, G4 or G5."),
    project: Path = typer.Option(Path.cwd(), help="Project root for current canonical DB state."),
):
    """Automation guard: a diagnostic audit completing successfully is not approval."""
    try:
        if gate not in {"G1", "G2", "G3", "G4", "G5"}:
            raise ValueError("gate must be one of G1, G2, G3, G4, G5")
        report = flow.require_research_stage(audit, gate, project=project)
        typer.echo(
            json.dumps(
                {
                    "audit": str(audit.resolve()),
                    "gate": gate,
                    "state": "aprovado",
                    "current_canonical_state_rechecked": True,
                    "research_ready": report["research_ready"],
                },
                ensure_ascii=False,
            )
        )
    except Exception as exc:
        _failure(exc)


def prepare_private_requests(
    *, audit: Path, output: Path, project: Path, rubric_path: Path, profile_path: Path
) -> dict:
    """Revalidate G2 and current canonical documents before writing any private text."""
    if output.exists():
        raise ValueError("preparation output already exists; use a new version directory")
    report = flow.require_research_stage(audit, "G2", project=project)
    rubric = validate_rubric(_read_json(rubric_path), require_accepted=True)
    profile = _read_json(profile_path)
    configuration = profile.get("configuration", {})
    expected_profile = build_profile(
        model_id=profile.get("model_id"),
        resolved_model_version=configuration.get("resolved_model_version"),
        generation_configuration=configuration.get("generation"),
        rubric=rubric,
    )
    if canonical_json(expected_profile) != canonical_json(profile):
        raise ValueError("profile does not bind the accepted rubric and actual contract")
    input_hashes = {
        str(path.resolve()): file_hash(path)
        for path in (audit / "manifest.json", audit / "report.json", rubric_path, profile_path)
    }
    identities = list(report["canonical_state"])
    documents = flow.read_canonical_documents(project, [UUID(identity) for identity in identities])
    candidate_memberships = {}
    for item in flow.rows(audit / "items.jsonl"):
        if item.get("lyric_verified") is True:
            candidate_memberships.setdefault(item["candidate_id"], []).append(
                {key: item[key] for key in ("country_code", "year", "position", "candidate_id")}
            )
    gate = ClassificationGate.load()
    requests, deficits, mappings = [], [], []
    for identity in identities:
        document = documents.get(identity)
        if (
            document is None
            or flow.canonical_fingerprint(document) != report["canonical_state"][identity]
            or not isinstance(document.text, str)
            or hashlib.sha256(document.text.encode()).hexdigest() != document.content_sha256
            or not gate.assess(document).eligible
        ):
            raise ValueError("canonical document changed or approval revoked; rerun audit")
        candidates = sorted(
            set((document.metadata_json or {}).get("research_candidate_ids", []))
            & candidate_memberships.keys()
        )
        if not candidates:
            deficits.append({"document_id": identity, "reason": "no_approved_membership"})
            continue
        language = document.language_code
        if not isinstance(language, str) or not language.strip():
            deficits.append(
                {
                    "document_id": identity,
                    "candidate_ids": candidates,
                    "reason": "explicit_language_missing",
                }
            )
            continue
        request = prepare_request(
            edition_id=identity,
            text=document.text,
            language=language,
            profile=profile,
            rubric=rubric,
        )
        requests.append(request)
        mappings.append(
            {
                "request_id": request["request_id"],
                "request_file": f"requests/{request['request_id']}.json",
                "document_id": identity,
                "candidate_ids": candidates,
                "memberships": [
                    membership
                    for candidate in candidates
                    for membership in candidate_memberships[candidate]
                ],
            }
        )
    # Inputs and approvals can change while a large local preparation is running.
    flow.require_research_stage(audit, "G2", project=project)
    if any(file_hash(path) != digest for path, digest in input_hashes.items()):
        raise ValueError("input changed during preparation")
    output.mkdir(parents=True, exist_ok=False)
    flow.write_rows(output / "requests.private.jsonl", requests)
    if requests:
        request_dir = output / "requests"
        request_dir.mkdir()
        for request in requests:
            flow.write_json(request_dir / (request["request_id"] + ".json"), request)
    flow.write_rows(output / "request-memberships.jsonl", mappings)
    flow.write_rows(output / "deficits.jsonl", deficits)
    table = [table_row(request) for request in requests]
    fields = (
        list(table[0])
        if table
        else [
            "request_id",
            "edition_id",
            "text_sha256",
            "language",
            "status",
        ]
    )
    flow.write_csv(output / "preparatory-table.csv", table, fields)
    manifest = {
        "protocol": flow.VERSION,
        "private": True,
        "status": "prepared_not_submitted",
        "source_audit": str(audit.resolve()),
        "audit_actor": report["actor"],
        "canonical_documents": len(identities),
        "prepared_requests": len(requests),
        "deficits": len(deficits),
        "paid_calls": 0,
        "uploads": 0,
        "reservations": 0,
        "scientific_classifier_acceptance": False,
        "rubric_sha256": flow.object_hash(rubric),
        "input_hashes": input_hashes,
        "artifacts": {
            path.relative_to(output).as_posix(): file_hash(path)
            for path in output.rglob("*")
            if path.is_file()
        },
    }
    flow.write_json(output / "manifest.json", manifest)
    return manifest


@app.command("prepare")
def prepare_command(
    audit: Path = typer.Option(..., help="Immutable audit whose G2 is approved."),
    output: Path = typer.Option(..., help="New private preparation directory."),
    rubric: Path = typer.Option(..., help="Explicitly accepted full 26-topic rubric JSON."),
    profile: Path = typer.Option(..., help="Resolved execution profile for the actual contract."),
    project: Path = typer.Option(Path.cwd(), help="Project root for current canonical DB state."),
):
    try:
        manifest = prepare_private_requests(
            audit=audit.resolve(),
            output=output.resolve(),
            project=project.resolve(),
            rubric_path=rubric.resolve(),
            profile_path=profile.resolve(),
        )
        typer.echo(
            json.dumps(
                {
                    "output": str(output.resolve()),
                    **{
                        key: manifest[key]
                        for key in (
                            "status",
                            "private",
                            "prepared_requests",
                            "deficits",
                            "paid_calls",
                            "uploads",
                        )
                    },
                },
                ensure_ascii=False,
            )
        )
    except Exception as exc:
        _failure(exc)
