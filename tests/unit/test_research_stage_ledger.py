import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from chart_observatory.research_flow import VERSION
from chart_observatory.research_stage_ledger import GATES, ResearchStageLedger


def report_artifact(output, **changes):
    report = {
        "protocol": VERSION,
        "actor": "researcher",
        "selection_sha256": "a" * 64,
        "gates": [
            {
                "gate": gate,
                "state": "reprovado" if gate == "G1" else "pendente",
                "numerator": 0,
                "denominator": 10,
                "ratio": 0.0,
            }
            for gate in GATES
        ],
        **changes,
    }
    output.mkdir(parents=True)
    payload = json.dumps(report).encode()
    (output / "report.json").write_bytes(payload)
    return report, hashlib.sha256(payload).hexdigest()


def test_begin_and_finish_preserve_all_transitions_and_evidence(tmp_path):
    ledger = ResearchStageLedger(tmp_path / "ledger.sqlite")
    output = tmp_path / "audit"
    run = ledger.begin("a" * 64, "researcher", output)
    initial = ledger.records(run)
    assert len(initial) == 10
    assert [row["state"] for row in initial[:2]] == ["pendente", "em_execucao"]
    report, digest = report_artifact(output)
    ledger.finish(run, report, digest)
    records = ledger.records(run)
    assert records[:10] == initial
    assert len(records) == 15
    assert records[-1]["report_sha256"] == digest
    assert records[-1]["actor"] == "researcher"
    assert records[-1]["selection_sha256"] == "a" * 64
    assert len(records[-1]["code_sha256"]) == 64


def test_failure_sanitizes_messages_and_leaves_no_running_latest_events(tmp_path):
    ledger = ResearchStageLedger(tmp_path / "ledger.sqlite")
    run = ledger.begin("a" * 64, "researcher", tmp_path / "audit")
    ledger.fail(run, "postgresql://password@host")
    rows = ledger.records(run)
    assert len(rows) == 15
    assert all(row["state"] == "reprovado" for row in rows[-5:])
    assert all(row["error_type"] == "InvalidErrorType" for row in rows[-5:])
    assert "password" not in json.dumps(rows)


def test_events_cannot_be_updated_or_deleted_even_with_direct_sql(tmp_path):
    ledger = ResearchStageLedger(tmp_path / "ledger.sqlite")
    ledger.begin("a" * 64, "researcher", tmp_path / "audit")
    for sql in (
        "UPDATE research_stage_events SET state='aprovado'",
        "DELETE FROM research_stage_events",
    ):
        with sqlite3.connect(ledger.path) as conn, pytest.raises(sqlite3.IntegrityError):
            conn.execute(sql)
    assert len(ledger.records()) == 10


def test_finish_is_atomic_and_cannot_rewrite_or_double_finalize(tmp_path):
    ledger = ResearchStageLedger(tmp_path / "ledger.sqlite")
    output = tmp_path / "audit"
    run = ledger.begin("a" * 64, "researcher", output)
    report, digest = report_artifact(output, actor="other")
    with pytest.raises(ValueError, match="actor"):
        ledger.finish(run, report, digest)
    assert len(ledger.records(run)) == 10
    ledger.fail(run, "ValueError")
    with pytest.raises(ValueError, match="already finalized"):
        ledger.fail(run, "RuntimeError")


def test_changed_report_bytes_cannot_be_registered(tmp_path):
    ledger = ResearchStageLedger(tmp_path / "ledger.sqlite")
    output = tmp_path / "audit"
    run = ledger.begin("a" * 64, "researcher", output)
    report, digest = report_artifact(output)
    (output / "report.json").write_text("{}")
    with pytest.raises(ValueError, match="artifact"):
        ledger.finish(run, report, digest)
    assert len(ledger.records(run)) == 10


def test_duplicate_output_has_only_one_concurrent_owner(tmp_path):
    ledger = ResearchStageLedger(tmp_path / "ledger.sqlite")

    def begin(index):
        try:
            return ledger.begin("a" * 64, "researcher", tmp_path / "audit")
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        owners = list(pool.map(begin, range(2)))
    assert sum(owner is not None for owner in owners) == 1
    assert len(ledger.records()) == 10


def test_independent_outputs_and_filter_are_isolated(tmp_path):
    ledger = ResearchStageLedger(tmp_path / "ledger.sqlite")
    first = ledger.begin("a" * 64, "researcher", tmp_path / "first")
    second = ledger.begin("b" * 64, "reviewer", tmp_path / "second")
    ledger.fail(first, "ValueError")
    assert len(ledger.records()) == 25
    assert len(ledger.records(second)) == 10


def test_invalid_gate_counts_do_not_insert_partial_terminal_events(tmp_path):
    ledger = ResearchStageLedger(tmp_path / "ledger.sqlite")
    output = tmp_path / "audit"
    run = ledger.begin("a" * 64, "researcher", output)
    report, digest = report_artifact(output)
    report["gates"][-1]["numerator"] = True
    with pytest.raises(ValueError, match="nonnegative integers"):
        ledger.finish(run, report, digest)
    assert len(ledger.records(run)) == 10
