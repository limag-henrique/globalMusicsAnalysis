import copy
import json
from datetime import UTC, datetime

import pytest
import typer
from typer.testing import CliRunner

from chart_observatory import research_progress as progress
from chart_observatory.research_progress_cli import progress_command

NOW = datetime(2026, 11, 10, 15, tzinfo=UTC)


@pytest.fixture
def campaign(tmp_path, monkeypatch):
    audit = tmp_path / "audit"
    audit.mkdir()
    (audit / "manifest.json").write_text("{}", encoding="utf-8")
    cells = [
        {
            "selected_positions": 100,
            "quota": 100,
            "status": "QUOTA_FILLED_COMPLETE_CALENDAR",
        },
        {"selected_positions": 100, "quota": 100, "status": "PARTIAL_YEAR"},
        {"selected_positions": 0, "quota": 100, "status": "NO_VERIFIED_ANNUAL_SOURCE"},
        {"selected_positions": 0, "quota": None, "status": "POPULATION_QUOTA_UNRESOLVED"},
    ]
    cell_file = tmp_path / "country_years.jsonl"
    progress.flow.write_rows(cell_file, cells)
    gates = [
        {"gate": "G1", "state": "reprovado", "numerator": 0, "denominator": 1000},
        {"gate": "G2", "state": "pendente", "numerator": 0, "denominator": 0},
        {"gate": "G3", "state": "pendente", "numerator": 0, "denominator": 0},
        {"gate": "G4", "state": "pendente"},
        {"gate": "G5", "state": "pendente", "numerator": 0, "denominator": 0},
    ]
    report = {
        "selection_sha256": "a" * 64,
        "scope": {"requested_positions": 1000, "country_year_cells": 4},
        "inventory": {"observed_positions": 400, "candidate_identities": 100},
        "gates": gates,
        "evaluated_at": "2026-11-10T14:00:00Z",
        "research_ready": False,
        "input_hashes": {str(cell_file): progress.file_hash(cell_file)},
    }
    monkeypatch.setattr(progress.flow, "verify_audit", lambda *a, **k: copy.deepcopy(report))
    monkeypatch.setattr(progress, "process_alive", lambda pid: False)
    status = tmp_path / "status.json"
    data = {
        "global_manifest_sha256": "a" * 64,
        "unique_candidates": 100,
        "text_candidates": 80,
        "paid_ready_candidates": 0,
        "updated_at": "2026-11-08T23:00:00Z",
        "run_id": "local-intake",
        "pid": 123,
    }
    status.write_text(json.dumps(data), encoding="utf-8")
    return audit, status, report, data


def test_progress_separates_observed_text_and_scientific_denominators(campaign):
    audit, status, _, _ = campaign
    result = progress.build_progress(audit, status, now=NOW)
    assert result["rankings_observed"]["percent"] == 40
    assert result["lyrics_availability"]["percent"] == 80
    assert result["scientific_gate_completion"]["percent"] == 0
    assert result["scientific_gates"][0]["current_percent"] == 0
    assert result["scientific_gates"][1]["current_percent"] is None
    assert result["overall_software_completion_percent"] is None
    assert result["current_database_certified"] is False
    assert result["country_year_cells"]["with_observed_positions"]["percent"] == 50
    assert result["country_year_cells"]["at_least_80_percent_observed_of_known_quota"][
        "percent"
    ] == pytest.approx(200 / 3)
    assert result["country_year_cells"]["unresolved_quota_cells"]["numerator"] == 1
    assert result["country_year_cells"]["quota_filled_complete_calendar"]["percent"] == 25


def test_old_local_status_is_neither_a_live_process_nor_scientific_approval(campaign):
    audit, status, _, _ = campaign
    result = progress.build_progress(audit, status, now=NOW)
    local = result["lyrics_availability"]
    assert local["older_than_24_hours"] is True
    assert local["evidence_status"] == "local_historical_snapshot"
    assert local["scientific_approval"] is False
    assert local["process"] == {
        "pid": 123,
        "pid_exists": False,
        "identity_verified": False,
        "state": "not_found",
    }


def test_existing_pid_does_not_prove_matching_process_is_running(campaign, monkeypatch):
    audit, status, _, _ = campaign
    monkeypatch.setattr(progress, "process_alive", lambda pid: True)
    result = progress.build_progress(audit, status, now=NOW)
    assert result["lyrics_availability"]["process"]["state"] == "identity_unverified"
    assert result["lyrics_availability"]["process"]["identity_verified"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("global_manifest_sha256", "b" * 64),
        ("unique_candidates", 99),
        ("text_candidates", 101),
        ("text_candidates", -1),
        ("text_candidates", True),
        ("paid_ready_candidates", 81),
        ("pid", "123"),
        ("updated_at", "2026-11-10T16:00:00Z"),
        ("updated_at", "2026-11-08T23:00:00"),
    ],
)
def test_staging_count_selection_and_timestamp_forgery_are_rejected(campaign, field, value):
    audit, status, _, data = campaign
    data[field] = value
    status.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        progress.build_progress(audit, status, now=NOW)


def test_changed_inputs_preserve_historical_facts_without_current_approval(campaign, monkeypatch):
    audit, status, report, _ = campaign
    report["gates"] = [{**g, "state": "aprovado"} for g in report["gates"]]
    report["research_ready"] = True

    def verify(path, *, check_inputs=True):
        if check_inputs:
            raise ValueError("audit input missing or changed")
        return report

    monkeypatch.setattr(progress.flow, "verify_audit", verify)
    result = progress.build_progress(audit, status, now=NOW)
    assert not result["audit_current_inputs_verified"]
    assert result["scientific_gate_completion"] is None
    assert result["recorded_scientific_gate_completion"]["percent"] == 100
    assert all(g["current_state"] == "audit_stale" for g in result["scientific_gates"])
    assert all(g["current_percent"] is None for g in result["scientific_gates"])
    assert not result["research_ready"]


def test_tampered_audit_artifacts_are_not_reported_as_historical_truth(campaign, monkeypatch):
    def reject(*args, **kwargs):
        raise ValueError("audit artifact changed")

    monkeypatch.setattr(progress.flow, "verify_audit", reject)
    with pytest.raises(ValueError, match="artifact changed"):
        progress.build_progress(campaign[0], campaign[1], now=NOW)


def test_missing_staging_does_not_invent_lyrics_percentage(campaign):
    result = progress.build_progress(campaign[0], now=NOW)
    assert result["lyrics_availability"] is None


def test_progress_output_is_immutable_and_hash_bound_without_lyrics(campaign, tmp_path):
    result = progress.build_progress(campaign[0], campaign[1], now=NOW)
    output = tmp_path / "progress"
    progress.write_progress(output, result)
    assert (output / "progress.csv").is_file()
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert all(
        progress.file_hash(output / name) == digest
        for name, digest in manifest["artifacts"].items()
    )
    with pytest.raises(ValueError, match="already exists"):
        progress.write_progress(output, result)


def test_cli_exports_immutable_progress(campaign, tmp_path):
    app = typer.Typer()
    app.command("progress")(progress_command)
    result = CliRunner().invoke(
        app,
        [
            "--audit",
            str(campaign[0]),
            "--staging-status",
            str(campaign[1]),
            "--output",
            str(tmp_path / "cli"),
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["overall_software_completion_percent"] is None


@pytest.mark.parametrize("a,b", [(0, 0), (0, 1), (1, 1)])
def test_zero_denominators_are_undefined_and_real_counts_remain_exact(a, b):
    assert progress.fraction(a, b)["percent"] == (100 * a / b if b else None)
