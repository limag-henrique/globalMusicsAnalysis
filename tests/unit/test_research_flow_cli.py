import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from typer.testing import CliRunner

from chart_observatory import research_flow_cli as cli
from chart_observatory.lyrics.research_contract import build_profile, rubric_draft, verify_request
from chart_observatory.lyrics.revision_protocol import canonical_json

runner = CliRunner()


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def test_audit_command_forwards_explicit_paths_actor_and_reports_compact_gates(
    tmp_path, monkeypatch
):
    captured = {}

    def audit(**kwargs):
        captured.update(kwargs)
        return {
            "protocol": "test",
            "actor": kwargs["actor"],
            "inventory": {"items": 10},
            "gates": [{"gate": "G1", "state": "reprovado"}],
            "research_ready": False,
        }

    monkeypatch.setattr(cli.flow, "audit_research_flow", audit)
    result = runner.invoke(
        cli.app,
        [
            "audit",
            "--selection",
            str(tmp_path / "selection"),
            "--output",
            str(tmp_path / "audit"),
            "--actor",
            "responsável",
            "--project",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert captured["actor"] == "responsável"
    assert captured["evidence_path"] is None
    assert json.loads(result.stdout)["gates"] == {"G1": "reprovado"}
    assert json.loads(result.stdout)["paid_calls"] == 0


def test_audit_actor_is_required(tmp_path):
    result = runner.invoke(
        cli.app,
        [
            "audit",
            "--selection",
            str(tmp_path),
            "--output",
            str(tmp_path / "output"),
        ],
    )
    assert result.exit_code != 0
    assert not (tmp_path / "output").exists()


def test_verify_is_integrity_check_not_scientific_approval(tmp_path, monkeypatch):
    monkeypatch.setattr(
        cli.flow,
        "verify_audit",
        lambda path: {
            "protocol": "test",
            "research_ready": False,
        },
    )
    result = runner.invoke(cli.app, ["verify", "--audit", str(tmp_path)])
    assert result.exit_code == 0
    response = json.loads(result.stdout)
    assert response["integrity"] == "verified"
    assert response["scientific_approval_rechecked"] is False


def test_sensitive_database_error_message_is_not_printed(tmp_path, monkeypatch):
    def fail(path):
        raise RuntimeError("postgresql://sensitive-password@host/database")

    monkeypatch.setattr(cli.flow, "verify_audit", fail)
    result = runner.invoke(cli.app, ["verify", "--audit", str(tmp_path)])
    assert result.exit_code == 1
    assert "sensitive-password" not in result.output
    assert "RuntimeError" in result.output


def test_require_command_is_successful_only_after_current_gate_revalidation(tmp_path, monkeypatch):
    calls = []

    def require(audit, gate, **kwargs):
        calls.append((audit, gate, kwargs))
        return {"research_ready": False}

    monkeypatch.setattr(cli.flow, "require_research_stage", require)
    result = runner.invoke(
        cli.app,
        [
            "require",
            "--audit",
            str(tmp_path / "audit"),
            "--gate",
            "G2",
            "--project",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert calls[0][1] == "G2"
    assert calls[0][2]["project"] == tmp_path
    assert json.loads(result.stdout)["current_canonical_state_rechecked"] is True


def test_require_command_returns_nonzero_for_blocked_stage(tmp_path, monkeypatch):
    def require(*args, **kwargs):
        raise ValueError("research stage is not approved: G1")

    monkeypatch.setattr(cli.flow, "require_research_stage", require)
    result = runner.invoke(cli.app, ["require", "--audit", str(tmp_path), "--gate", "G1"])
    assert result.exit_code == 1
    assert "not approved" in result.output


@pytest.fixture
def prepared_environment(tmp_path, monkeypatch):
    audit = tmp_path / "audit"
    audit.mkdir()
    save(audit / "manifest.json", {"audit": "fixture"})
    save(audit / "report.json", {"audit": "fixture"})
    candidate = "SPOTIFY:exact-id"
    cli.flow.write_rows(
        audit / "items.jsonl",
        [
            {
                "candidate_id": candidate,
                "country_code": "BR",
                "year": 2020,
                "position": 1,
                "lyric_verified": True,
            }
        ],
    )
    text = "Texto privado completo.\r\nRefrão.\r\nRefrão."
    document = SimpleNamespace(
        id=uuid4(),
        canonical_track_id=uuid4(),
        text=text,
        content_sha256=hashlib.sha256(text.encode()).hexdigest(),
        source="fixture",
        rights_status="authorized",
        language_code="pt",
        metadata_json={"research_candidate_ids": [candidate]},
    )
    identity = str(document.id)
    report = {
        "actor": "researcher",
        "canonical_state": {
            identity: cli.flow.canonical_fingerprint(document),
        },
    }
    calls = []

    def require(path, gate, **kwargs):
        calls.append((path, gate, kwargs))
        return report

    monkeypatch.setattr(cli.flow, "require_research_stage", require)
    monkeypatch.setattr(
        cli.flow,
        "read_canonical_documents",
        lambda project, ids: {
            identity: document,
        },
    )
    monkeypatch.setattr(
        cli.ClassificationGate,
        "load",
        lambda: SimpleNamespace(
            assess=lambda document: SimpleNamespace(eligible=True),
        ),
    )
    rubric = rubric_draft()
    rubric["status"] = "accepted"
    rubric["acceptance"] = {
        "actor": "scientific-reviewer",
        "at": datetime.now(UTC).isoformat(),
        "rubric_sha256": hashlib.sha256(canonical_json(rubric).encode()).hexdigest(),
    }
    profile = build_profile(
        model_id="test",
        resolved_model_version="test-fixed-001",
        generation_configuration={"temperature": 0},
        rubric=rubric,
    )
    rubric_path = save(tmp_path / "rubric.json", rubric)
    profile_path = save(tmp_path / "profile.json", profile)
    return SimpleNamespace(
        audit=audit,
        output=tmp_path / "private",
        project=tmp_path,
        rubric_path=rubric_path,
        profile_path=profile_path,
        document=document,
        report=report,
        calls=calls,
    )


def prepare(env):
    return cli.prepare_private_requests(
        **{
            key: getattr(env, key)
            for key in (
                "audit",
                "output",
                "project",
                "rubric_path",
                "profile_path",
            )
        }
    )


def test_prepare_blocks_before_creating_files_when_g2_fails(prepared_environment, monkeypatch):
    def fail(*args, **kwargs):
        raise ValueError("research stage is not approved: G2")

    monkeypatch.setattr(cli.flow, "require_research_stage", fail)
    with pytest.raises(ValueError, match="not approved"):
        prepare(prepared_environment)
    assert not prepared_environment.output.exists()


def test_prepare_uses_current_canonical_ids_and_creates_private_unsent_exact_requests(
    prepared_environment,
):
    env = prepared_environment
    manifest = prepare(env)
    assert len(env.calls) == 2
    assert all(call[1] == "G2" for call in env.calls)
    assert manifest["private"] is True
    assert manifest["paid_calls"] == manifest["uploads"] == manifest["reservations"] == 0
    assert manifest["prepared_requests"] == 1
    request = list(cli.flow.rows(env.output / "requests.private.jsonl"))[0]
    verify_request(request)
    assert request["edition_id"] == str(env.document.id)
    assert "".join(segment["text"] for segment in request["segments"]) == env.document.text
    table = (env.output / "preparatory-table.csv").read_text(encoding="utf-8-sig")
    assert "Texto privado" not in table
    assert "prepared_not_submitted" in table
    assert manifest["scientific_classifier_acceptance"] is False


def test_missing_language_is_deficit_without_guess_or_request(prepared_environment):
    env = prepared_environment
    env.document.language_code = None
    # Model an audit that already froze an approved document with no language.
    env.report["canonical_state"][str(env.document.id)] = cli.flow.canonical_fingerprint(
        env.document
    )
    manifest = prepare(env)
    assert manifest["prepared_requests"] == 0
    assert manifest["deficits"] == 1
    deficits = list(cli.flow.rows(env.output / "deficits.jsonl"))
    assert deficits[0]["reason"] == "explicit_language_missing"
    assert not (env.output / "requests.private.jsonl").read_text()


def test_language_changed_after_audit_requires_reaudit(prepared_environment):
    env = prepared_environment
    env.document.language_code = "en"
    with pytest.raises(ValueError, match="document changed"):
        prepare(env)
    assert not env.output.exists()


def test_changed_canonical_text_cannot_be_prepared(prepared_environment):
    env = prepared_environment
    env.document.text = "Changed after approval"
    with pytest.raises(ValueError, match="document changed"):
        prepare(env)
    assert not env.output.exists()


def test_draft_or_mismatching_profile_cannot_create_private_text(prepared_environment):
    env = prepared_environment
    rubric = json.loads(env.rubric_path.read_text(encoding="utf-8"))
    rubric["status"] = "draft"
    save(env.rubric_path, rubric)
    with pytest.raises(ValueError, match="acceptance"):
        prepare(env)
    assert not env.output.exists()


def test_prepare_cli_prints_only_summary(prepared_environment):
    env = prepared_environment
    result = runner.invoke(
        cli.app,
        [
            "prepare",
            "--audit",
            str(env.audit),
            "--output",
            str(env.output),
            "--project",
            str(env.project),
            "--rubric",
            str(env.rubric_path),
            "--profile",
            str(env.profile_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Texto privado" not in result.output
    assert json.loads(result.stdout)["prepared_requests"] == 1


def chart_rows(count=365):
    for offset in range(count):
        period = (date(2018, 1, 1) + timedelta(days=offset)).isoformat()
        yield {
            "country_code": "BR",
            "platform": "SPOTIFY",
            "provider": "MGD",
            "period_start": period,
            "period_end": period,
            "candidate_id": "SPOTIFY:one",
            "position": 1,
            "metric_value": 10,
            "title": "Synthetic",
            "artist": "Fixture",
        }


def reconstruct_arguments(tmp_path):
    return [
        "reconstruct",
        "--observations",
        str(tmp_path / "observations.jsonl"),
        "--output",
        str(tmp_path / "reconstructed"),
        "--country",
        "BR",
        "--year",
        "2018",
        "--platform",
        "SPOTIFY",
        "--provider",
        "MGD",
        "--quota",
        "1",
        "--depth",
        "1",
        "--frequency",
        "daily",
    ]


def test_reconstruct_cli_runs_real_independent_calculation_with_hashed_inputs(tmp_path):
    cli.flow.write_rows(tmp_path / "observations.jsonl", chart_rows())
    result = runner.invoke(cli.app, reconstruct_arguments(tmp_path))
    assert result.exit_code == 0, result.output
    response = json.loads(result.stdout)
    assert response["reconstruction_approved"] is True
    assert response["scientific_approval"] is False
    output = tmp_path / "reconstructed"
    rows = list(cli.flow.rows(output / "ranked_rows.jsonl"))
    assert rows[0]["metric_value"] == "3650"
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert str((tmp_path / "observations.jsonl").resolve()) in manifest["input_hashes"]
    assert "reconstruction.json" in manifest["artifacts"]
    repeated = runner.invoke(cli.app, reconstruct_arguments(tmp_path))
    assert repeated.exit_code == 1


def test_incomplete_calendar_produces_diagnostic_reconstruction_without_approval(tmp_path):
    cli.flow.write_rows(tmp_path / "observations.jsonl", chart_rows(1))
    result = runner.invoke(cli.app, reconstruct_arguments(tmp_path))
    assert result.exit_code == 0, result.output
    response = json.loads(result.stdout)
    assert response["reconstruction_approved"] is False
    assert "missing_periods" in response["reasons"]
    assert response["scientific_approval"] is False


def test_malformed_reconstruction_input_creates_no_output(tmp_path):
    (tmp_path / "observations.jsonl").write_text("{broken}\n", encoding="utf-8")
    result = runner.invoke(cli.app, reconstruct_arguments(tmp_path))
    assert result.exit_code == 1
    assert not (tmp_path / "reconstructed").exists()
