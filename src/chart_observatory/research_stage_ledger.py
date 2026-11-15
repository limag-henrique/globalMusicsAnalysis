"""Append-only research audit transitions; no scientific scores or exception text."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from chart_observatory.lyrics.revision_protocol import canonical_json

LEDGER_VERSION = "research-stage-ledger-v1"
GATES = ("G1", "G2", "G3", "G4", "G5")
_DIGEST = re.compile(r"[0-9a-f]{64}")
_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_runs(
    run_id TEXT PRIMARY KEY,
    selection_sha256 TEXT NOT NULL CHECK(length(selection_sha256)=64),
    actor TEXT NOT NULL, output TEXT NOT NULL UNIQUE,
    ledger_version TEXT NOT NULL, code_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS research_terminals(
    run_id TEXT PRIMARY KEY REFERENCES research_runs(run_id),
    terminal_type TEXT NOT NULL CHECK(terminal_type IN ('finished','failed')),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS research_stage_events(
    event_id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES research_runs(run_id),
    gate TEXT NOT NULL CHECK(gate IN ('G1','G2','G3','G4','G5')),
    state TEXT NOT NULL CHECK(state IN ('pendente','em_execucao','reprovado','aprovado')),
    event_type TEXT NOT NULL CHECK(event_type IN ('initialized','started','finished','failed')),
    numerator INTEGER, denominator INTEGER, ratio REAL,
    evidence_path TEXT, report_sha256 TEXT, protocol TEXT,
    error_type TEXT, created_at TEXT NOT NULL,
    UNIQUE(run_id,gate,event_type)
);
CREATE TRIGGER IF NOT EXISTS research_events_no_update
BEFORE UPDATE ON research_stage_events BEGIN
    SELECT RAISE(ABORT,'research audit events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS research_events_no_delete
BEFORE DELETE ON research_stage_events BEGIN
    SELECT RAISE(ABORT,'research audit events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS research_runs_no_update
BEFORE UPDATE ON research_runs BEGIN
    SELECT RAISE(ABORT,'research audit runs are immutable'); END;
CREATE TRIGGER IF NOT EXISTS research_runs_no_delete
BEFORE DELETE ON research_runs BEGIN
    SELECT RAISE(ABORT,'research audit runs are immutable'); END;
CREATE TRIGGER IF NOT EXISTS research_terminals_no_update
BEFORE UPDATE ON research_terminals BEGIN
    SELECT RAISE(ABORT,'research audit terminals are immutable'); END;
CREATE TRIGGER IF NOT EXISTS research_terminals_no_delete
BEFORE DELETE ON research_terminals BEGIN
    SELECT RAISE(ABORT,'research audit terminals are immutable'); END;
"""


def _now():
    return datetime.now(UTC).isoformat()


class ResearchStageLedger:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def begin(self, selection_sha256: str, actor: str, output) -> str:
        if not isinstance(selection_sha256, str) or not _DIGEST.fullmatch(selection_sha256):
            raise ValueError("complete selection SHA-256 required")
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError("responsible actor required")
        output = os.path.normcase(str(Path(output).resolve()))
        run_id, at = str(uuid4()), _now()
        code_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute(
                    "INSERT INTO research_runs VALUES (?,?,?,?,?,?,?)",
                    (run_id, selection_sha256, actor, output, LEDGER_VERSION, code_sha256, at),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(
                    "audit output already has a registered run; use a new output"
                ) from exc
            for gate in GATES:
                for state, kind in (("pendente", "initialized"), ("em_execucao", "started")):
                    conn.execute(
                        """INSERT INTO research_stage_events
                        (run_id,gate,state,event_type,created_at) VALUES (?,?,?,?,?)""",
                        (run_id, gate, state, kind, at),
                    )
        return run_id

    @staticmethod
    def _active_run(conn, run_id):
        run = conn.execute("SELECT * FROM research_runs WHERE run_id=?", (run_id,)).fetchone()
        if run is None:
            raise ValueError("unknown research audit run")
        if conn.execute("SELECT 1 FROM research_terminals WHERE run_id=?", (run_id,)).fetchone():
            raise ValueError("research audit run already finalized")
        return run

    def finish(self, run_id: str, report: dict, report_sha256: str) -> None:
        if not isinstance(report_sha256, str) or not _DIGEST.fullmatch(report_sha256):
            raise ValueError("complete report SHA-256 required")
        from chart_observatory.research_flow import VERSION

        gates = report.get("gates", [])
        if (
            len(gates) != 5
            or {gate.get("gate") for gate in gates} != set(GATES)
            or report.get("protocol") != VERSION
        ):
            raise ValueError("complete five-gate versioned report required")
        prepared = []
        for gate in gates:
            state = gate.get("state")
            if state not in {"pendente", "reprovado", "aprovado"}:
                raise ValueError("invalid final gate state")
            numerator, denominator, ratio = (
                gate.get(key)
                for key in (
                    "numerator",
                    "denominator",
                    "ratio",
                )
            )
            if any(
                value is not None and (type(value) is not int or value < 0)
                for value in (numerator, denominator)
            ):
                raise ValueError("gate counts must be nonnegative integers or null")
            if numerator is not None and denominator is not None and numerator > denominator:
                raise ValueError("gate numerator exceeds denominator")
            if ratio is not None and (
                type(ratio) not in (int, float) or not math.isfinite(ratio) or not 0 <= ratio <= 1
            ):
                raise ValueError("gate ratio must be finite and between zero and one")
            prepared.append((gate["gate"], state, numerator, denominator, ratio))
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            run = self._active_run(conn, run_id)
            if (
                report.get("actor") != run["actor"]
                or report.get("selection_sha256") != run["selection_sha256"]
            ):
                raise ValueError("report actor or selection differs from registered run")
            evidence = Path(run["output"]) / "report.json"
            if (
                not evidence.is_file()
                or hashlib.sha256(evidence.read_bytes()).hexdigest() != report_sha256
                or canonical_json(json.loads(evidence.read_text(encoding="utf-8")))
                != canonical_json(report)
            ):
                raise ValueError("report artifact does not match supplied report and hash")
            at = _now()
            conn.execute("INSERT INTO research_terminals VALUES (?,?,?)", (run_id, "finished", at))
            for gate, state, numerator, denominator, ratio in prepared:
                conn.execute(
                    """INSERT INTO research_stage_events
                    (run_id,gate,state,event_type,numerator,denominator,ratio,
                    evidence_path,report_sha256,protocol,created_at)
                    VALUES (?,?,?,'finished',?,?,?,?,?,?,?)""",
                    (
                        run_id,
                        gate,
                        state,
                        numerator,
                        denominator,
                        ratio,
                        str(evidence),
                        report_sha256,
                        report["protocol"],
                        at,
                    ),
                )

    def fail(self, run_id: str, error_type: str) -> None:
        # Arbitrary exception messages, SQL and tokens are never persisted.
        safe_type = (
            error_type
            if isinstance(error_type, str)
            and re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_]{0,99}",
                error_type,
            )
            else "InvalidErrorType"
        )
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._active_run(conn, run_id)
            at = _now()
            conn.execute("INSERT INTO research_terminals VALUES (?,?,?)", (run_id, "failed", at))
            for gate in GATES:
                conn.execute(
                    """INSERT INTO research_stage_events
                    (run_id,gate,state,event_type,error_type,created_at)
                    VALUES (?,?,'reprovado','failed',?,?)""",
                    (run_id, gate, safe_type, at),
                )

    def records(self, run_id: str | None = None) -> list[dict]:
        sql = """SELECT e.*,r.selection_sha256,r.actor,r.output,
            r.ledger_version,r.code_sha256 FROM research_stage_events e
            JOIN research_runs r ON r.run_id=e.run_id"""
        parameters = ()
        if run_id is not None:
            sql += " WHERE e.run_id=?"
            parameters = (run_id,)
        sql += " ORDER BY e.event_id"
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(sql, parameters)]
