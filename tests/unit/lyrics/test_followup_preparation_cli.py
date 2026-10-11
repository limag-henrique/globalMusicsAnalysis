from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_followup_prepares_corrected_pending_and_separate_reanalysis_without_submission(
    tmp_path: Path,
) -> None:
    lyric = (
        "A complete synthetic lyric about an &#39;example&#39; with enough words to analyze.\n"
        "Another full line to provide sufficient content for this fixture."
    )
    rows = []
    for index, status in enumerate(("error", "classified", "error", "error"), start=1):
        rows.append(
            {
                "document_id": f"00000000-0000-0000-0000-{index:012d}",
                "document_track_id": f"00000000-0000-0000-0001-{index:012d}",
                "source": "GENIUS",
                "text": lyric,
                "rights_status": "RESEARCH_AUTHORIZED",
                "content_sha256": hashlib.sha256(lyric.encode()).hexdigest(),
                "classification_status": status,
                "valid_result": status == "classified",
                "error": "batch_malformed_response",
                "execution_attempts": 1 if index < 4 else 2,
                "active_reservation": index == 3,
                "ambiguous_submission": False,
                "prior_reanalysis": False,
                "global_job_failure": False,
                "prior_snapshot_id": f"00000000-0000-0000-0002-{index:012d}",
            }
        )
    fixture = tmp_path / "records.jsonl"
    fixture.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    context = tmp_path / "context.json"
    context.write_text(
        json.dumps(
            {
                "execution_id": "full-corpus-brl-20261008",
                "controller_alive": True,
                "status": "running",
                "quality_hold": False,
                "controller_stop_requested": False,
                "preparation_in_progress": None,
                "pending_run_count": 1,
                "available_brl": "0.007",
                "input_brl_per_million": "2.2241030265",
                "output_brl_per_million": "11.120515134",
                "pricing_valid_before_utc": "2099-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "next"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/prepare_lyrics_followup.py"),
            "--input-jsonl",
            str(fixture),
            "--fixture-context",
            str(context),
            "--output-dir",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0, result.stderr
    plan = json.loads((output / "plan.json").read_text(encoding="utf-8"))
    assert plan["groups"]["pending"]["request_count"] == 1
    assert plan["groups"]["corrected_reanalysis"]["request_count"] == 1
    assert plan["groups"]["corrected_reanalysis"]["spending_authorized"] is False
    assert plan["ready_to_submit"] is False
    assert {"controller_alive", "current_credit_reservation_insufficient"}.issubset(
        plan["handoff_blockers"]
    )
    pending = json.loads((output / "pending.requests.jsonl").read_text(encoding="utf-8"))
    model_text = pending["request"]["contents"][0]["parts"][0]["text"]
    assert "'example'" in model_text and "&#39;" not in model_text
    assert pending["request"]["generationConfig"]["maxOutputTokens"] == 1024
    decisions = [
        json.loads(line)
        for line in (output / "selection.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert "active_reservation" in decisions[2]["reasons"]
    assert "execution_attempt_limit" in decisions[3]["reasons"]


def test_followup_excludes_ambiguous_global_and_reanalysis_failures_and_obeys_holds(
    tmp_path: Path,
) -> None:
    lyric = (
        "A complete synthetic lyric with sufficient content for a deterministic planning test.\n"
        "Another complete line without interface residues."
    )
    rows = []
    failures = (
        {"ambiguous_submission": True},
        {"global_job_failure": True},
        {"prior_reanalysis": True},
        {"error": "authentication_failed"},
        {"rights_status": "UNKNOWN"},
    )
    for index, failure in enumerate(failures, start=1):
        rows.append(
            {
                "document_id": f"00000000-0000-0000-0000-{index:012d}",
                "document_track_id": f"00000000-0000-0000-0001-{index:012d}",
                "source": "GENIUS",
                "text": lyric,
                "rights_status": "RESEARCH_AUTHORIZED",
                "content_sha256": hashlib.sha256(lyric.encode()).hexdigest(),
                "classification_status": "error",
                "valid_result": False,
                "error": "batch_malformed_response",
                "execution_attempts": 1,
            }
            | failure
        )
    fixture = tmp_path / "rows.jsonl"
    fixture.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    context = tmp_path / "context.json"
    context.write_text(
        json.dumps(
            {
                "controller_alive": False,
                "status": "failed",
                "quality_hold": True,
                "preparation_in_progress": {"baseline": "unknown"},
                "pending_run_count": 0,
                "available_brl": "100",
                "input_brl_per_million": "2.2241030265",
                "output_brl_per_million": "11.120515134",
                "pricing_valid_before_utc": "2020-01-01T00:00:00+00:00",
                "failed_preparation_run_ids": ["preserved-old-run"],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "plan"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/prepare_lyrics_followup.py"),
            "--input-jsonl",
            str(fixture),
            "--fixture-context",
            str(context),
            "--output-dir",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0, result.stderr
    plan = json.loads((output / "plan.json").read_text(encoding="utf-8"))
    assert plan["groups"]["pending"]["request_count"] == 0
    assert {
        "current_execution_not_safely_completed",
        "quality_or_stop_hold",
        "monthly_pricing_expired",
        "ambiguous_preparation_or_submission",
        "failed_preparation_history_requires_audit",
    }.issubset(plan["handoff_blockers"])
    assert plan["exclusion_counts"] == {
        "ambiguous_submission": 1,
        "global_job_failure": 1,
        "prior_reanalysis_not_repeatable": 1,
        "error_not_in_technical_whitelist": 1,
        "rights_unauthorized": 1,
    }
