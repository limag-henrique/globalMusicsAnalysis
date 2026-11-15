"""Run synthetic research integration in a new PostgreSQL cluster, then stop it."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
PORT = 55441


def main():
    layout_call = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         ". ./scripts/research_postgres_paths.ps1; Get-ResearchPostgresLayout | ConvertTo-Json"],
        cwd=ROOT, capture_output=True, text=True, check=True, timeout=30,
    )
    layout = json.loads(layout_call.stdout)
    binaries = Path(layout["Binaries"])
    allowed = Path(os.environ["LOCALAPPDATA"]) / "ChartObservatory/research-flow-tests"
    run_id = uuid4().hex
    output = allowed / run_id
    cluster = output / "cluster"
    if not str(cluster).isascii():
        raise ValueError("isolated PostgreSQL requires an ASCII destination")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", PORT))
    output.mkdir(parents=True, exist_ok=False)
    report = dict(
        protocol="research-flow-isolated-postgres-v1", started_at=datetime.now(UTC).isoformat(),
        cluster=str(cluster), port=PORT, production_database_writes=0, paid_calls=0,
    )
    started, exit_code = False, 1

    def run(command, name, *, env=None, timeout=90):
        with (output / name).open("wb") as log:
            result = subprocess.run(
                [str(v) for v in command], cwd=ROOT, env=env, stdout=log,
                stderr=subprocess.STDOUT, timeout=timeout,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        if result.returncode:
            raise RuntimeError(name + " failed; inspect private isolated test logs")

    try:
        run([binaries / "initdb.exe", "-D", cluster, "-U", "research_test",
             "--auth=trust", "--encoding=UTF8", "--locale=C"], "initdb.log")
        run([binaries / "pg_ctl.exe", "-D", cluster, "-l", output / "server.log",
             "-o", f"-p {PORT} -h 127.0.0.1", "-t", "45", "-w", "start"], "start.log")
        started = True
        database = "research_flow_test_" + run_id
        with psycopg.connect(host="127.0.0.1", port=PORT, user="research_test",
                             dbname="postgres", autocommit=True) as conn:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
            conn.execute(sql.SQL("COMMENT ON DATABASE {} IS {}").format(
                sql.Identifier(database), sql.Literal(report["protocol"])
            ))
        env = dict(os.environ,
                   CHART_OBSERVATORY_TEST_DATABASE_URL=(
                       f"postgresql+psycopg://research_test@127.0.0.1:{PORT}/{database}"),
                   CHART_OBSERVATORY_RESEARCH_TEST_CLUSTER=str(cluster))
        run([sys.executable, "-m", "pytest", "tests/integration/research/test_research_flow.py",
             "-q", "--basetemp", ROOT / "data/runtime" / ("research-pg-tests-" + run_id),
             "--junitxml", output / "junit.xml"], "pytest.log", env=env, timeout=180)
        report["integration_passed"] = True
        exit_code = 0
    except Exception as exc:
        report["failure_type"] = type(exc).__name__
    finally:
        if started:
            try:
                run([binaries / "pg_ctl.exe", "-D", cluster, "-m", "fast", "-t", "45",
                     "-w", "stop"], "stop.log")
                report["isolated_cluster_stopped"] = True
            except Exception as exc:
                report["shutdown_failure_type"] = type(exc).__name__
                exit_code = 1
        report.update(finished_at=datetime.now(UTC).isoformat(), exit_code=exit_code)
        (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        receipt = ROOT / "data/runtime/research-execution-20261115/postgres-integration.json"
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(json.dumps(dict(report, output=str(output)), indent=2), encoding="utf-8")
        print(json.dumps(dict(report, output=str(output))))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
