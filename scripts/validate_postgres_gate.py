"""Restore a read-only logical snapshot into a dedicated, local PostgreSQL cluster.

No source DML/DDL, service restart or paid API call. Retains a stopped private copy.
"""

from __future__ import annotations

import hashlib
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
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

from chart_observatory.config import Settings

ROOT = Path(__file__).resolve().parents[1]
PORT = 55439
MARKER = "classification-gate-isolated-copy-v1"
TABLES = (
    "canonical_tracks",
    "lyric_documents",
    "lyric_classification_snapshots",
    "quota_lyric_staging_candidates",
    "quota_lyric_staging_blobs",
)


def logical_manifest(url: URL) -> dict:
    """Count key tables and hash every lyric/annotation row without exporting text."""
    dsn = url.set(drivername="postgresql", query={}).render_as_string(hide_password=False)
    result = {}
    with psycopg.connect(
        dsn, connect_timeout=5, options="-c default_transaction_read_only=on -c timezone=UTC"
    ) as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        result["transaction_read_only"] = conn.execute("SHOW transaction_read_only").fetchone()[0]
        result["alembic"] = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        for name in TABLES:
            result[name] = conn.execute(
                sql.SQL("SELECT count(*) FROM public.{}").format(sql.Identifier(name))
            ).fetchone()[0]
        for name in ("canonical_tracks", "lyric_documents", "lyric_classification_snapshots"):
            checksum = hashlib.sha256()
            with conn.cursor(name=f"fingerprint_{name}") as cur:
                cur.execute(
                    sql.SQL(
                        "SELECT id::text || ':' || md5(row_to_json(t)::text) "
                        "FROM public.{} t ORDER BY id"
                    ).format(sql.Identifier(name))
                )
                for row in cur:
                    checksum.update((row[0] + "\n").encode("utf-8"))
            result[name + "_row_manifest_sha256"] = checksum.hexdigest()
    return result


def main() -> int:
    configured = make_url(Settings.load(ROOT).database_url)
    if configured.host not in {"127.0.0.1", "localhost"} or configured.port != 55433:
        raise RuntimeError("Only the configured local source on 55433 is accepted")
    run_id = uuid4().hex
    runtime_base = (Path(os.environ["LOCALAPPDATA"]) / "ChartObservatory/gate-validation").resolve()
    run_root = (runtime_base / run_id).resolve()
    if not run_root.is_relative_to(runtime_base) or not str(run_root).isascii():
        raise RuntimeError("Invalid clone destination")
    run_root.mkdir(parents=True, exist_ok=False)
    target = run_root / "cluster"
    binaries = Path(os.environ["LOCALAPPDATA"]) / "ChartObservatory/postgresql16/bin"
    report = dict(
        marker=MARKER,
        run_id=run_id,
        clone_directory=str(target),
        port=PORT,
        started_at=datetime.now(UTC).isoformat(),
        paid_calls=0,
        source_started=False,
        source_write_statements=0,
        method="pg_dump custom, repeatable-read source sessions forced read-only",
    )
    (run_root / "identity.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    baseline = None
    started = False
    exit_code = 1

    def stage(message):
        print(message, flush=True)

    def run(args, *, env=None, output=None, timeout=60):
        # pg_ctl children can inherit pipe handles even after pg_ctl exits.
        # A real file avoids waiting for the lifetime of the PostgreSQL server.
        destination = Path(output) if output else run_root / "command.log"
        with destination.open("wb") as stream:
            result = subprocess.run(
                [str(a) for a in args],
                cwd=ROOT,
                env=env,
                stdout=stream,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                timeout=timeout,
            )
        if result.returncode:
            raise RuntimeError(f"{Path(args[0]).name} exited {result.returncode}")
        return result

    try:
        with socket.socket() as probe:
            probe.settimeout(1)
            if probe.connect_ex(("127.0.0.1", PORT)) == 0:
                raise RuntimeError("Clone port is already occupied")
        # Credentials only in child-process memory, never in commands or reports.
        source_env = {
            **os.environ,
            "PGPASSWORD": configured.password or "",
            "PGOPTIONS": "-c default_transaction_read_only=on -c timezone=UTC",
        }
        source_common = [
            "-h",
            configured.host,
            "-p",
            str(configured.port),
            "-U",
            configured.username or "postgres",
            "-d",
            configured.database,
        ]
        stage("Fingerprinting the source in a repeatable-read, read-only transaction")
        baseline = logical_manifest(configured)
        report["source_before"] = baseline
        if len(sys.argv) == 3 and sys.argv[1] == "--snapshot-from":
            import shutil

            previous = Path(sys.argv[2]).resolve()
            allowed = previous.is_relative_to((ROOT / "tmp").resolve()) or previous.is_relative_to(
                runtime_base
            )
            if not allowed:
                raise RuntimeError("Snapshot reuse must stay in a validation directory")
            old = json.loads((previous / "report.json").read_text(encoding="utf-8"))
            if old.get("marker") != MARKER or old.get("source_before") != baseline:
                raise RuntimeError("The snapshot no longer matches the current source")
            with (previous / "source.dump").open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != old["dump_sha256"]:
                    raise RuntimeError("Saved snapshot hash mismatch")
            stage("Reusing the verified snapshot; source fingerprints still match")
            shutil.copy2(previous / "source.dump", run_root / "source.dump")
            report["snapshot_reused_from"] = str(previous)
        elif len(sys.argv) == 1:
            stage("Dumping a consistent logical snapshot without writing to the source")
            run(
                [
                    binaries / "pg_dump.exe",
                    *source_common,
                    "--format=custom",
                    "--no-owner",
                    "--no-privileges",
                    "--serializable-deferrable",
                    "--file",
                    run_root / "source.dump",
                ],
                env=source_env,
                output=run_root / "source-dump.log",
                timeout=180,
            )
        else:
            raise RuntimeError("Use --snapshot-from DIRECTORY or no arguments")
        with (run_root / "source.dump").open("rb") as dump:
            report["dump_sha256"] = hashlib.file_digest(dump, "sha256").hexdigest()
        report["dump_bytes"] = (run_root / "source.dump").stat().st_size
        stage("Initializing a separate PostgreSQL 16 cluster on loopback port 55439")
        run(
            [
                binaries / "initdb.exe",
                "-D",
                target,
                "-U",
                "gate_validator",
                "-A",
                "trust",
                "-E",
                "UTF8",
                "--no-locale",
            ],
            output=run_root / "initdb.log",
        )
        hba = run_root / "isolated-hba.conf"
        hba.write_text("host all all 127.0.0.1/32 trust\n", encoding="ascii")
        conf = run_root / "isolated.conf"
        conf.write_text(
            f"data_directory = '{target.as_posix()}'\nhba_file = '{hba.as_posix()}'\n"
            f"listen_addresses = '127.0.0.1'\nport = {PORT}\n"
            "archive_mode = off\nautovacuum = off\nshared_preload_libraries = ''\n"
            "default_transaction_read_only = on\nlog_min_error_statement = panic\n"
            "log_statement = none\n",
            encoding="utf-8",
        )
        started = True
        run(
            [
                binaries / "pg_ctl.exe",
                "-D",
                target,
                "-l",
                run_root / "postgres.log",
                "-o",
                f'-c config_file="{conf}"',
                "-t",
                "45",
                "-w",
                "start",
            ],
            output=run_root / "startup.log",
        )
        clone_url = URL.create(
            "postgresql+psycopg", username="gate_validator", host="127.0.0.1", port=PORT
        )
        database = f"gate_integration_{run_id}"
        research_db = f"gate_source_{run_id}"
        writable = {"options": "-c default_transaction_read_only=off"}
        admin = create_engine(
            clone_url.set(database="postgres", query=writable), isolation_level="AUTOCOMMIT"
        )
        try:
            with admin.connect() as conn:
                if Path(conn.scalar(text("SHOW data_directory"))).resolve() != target:
                    raise RuntimeError("Unexpected PostgreSQL cluster; refusing writes")
                for name in (research_db, database):
                    conn.exec_driver_sql(f'CREATE DATABASE "{name}" TEMPLATE template0')
                conn.exec_driver_sql(f"COMMENT ON DATABASE {database} IS '{MARKER}:{run_id}'")
        finally:
            admin.dispose()
        clone_env = {
            **os.environ,
            "PGPASSWORD": "",
            "PGOPTIONS": "-c default_transaction_read_only=off",
        }
        common = ["-h", "127.0.0.1", "-p", str(PORT), "-U", "gate_validator"]
        stage("Restoring the complete research snapshot only into the isolated cluster")
        run(
            [
                binaries / "pg_restore.exe",
                *common,
                "-d",
                research_db,
                "--no-owner",
                "--no-privileges",
                "--single-transaction",
                "--exit-on-error",
                run_root / "source.dump",
            ],
            env=clone_env,
            output=run_root / "data-restore.log",
            timeout=240,
        )
        restored_url = clone_url.set(database=research_db)
        report["restored_before"] = logical_manifest(restored_url)
        if report["restored_before"] != baseline:
            raise RuntimeError("Restored data does not match the source logical fingerprint")
        stage("Restoring the exact research schema and triggers into a separate test database")
        run(
            [
                binaries / "pg_dump.exe",
                *common,
                "-d",
                research_db,
                "--schema-only",
                "--schema=public",
                "--format=custom",
                "--no-owner",
                "--no-privileges",
                "--file",
                run_root / "schema.dump",
            ],
            env=clone_env,
            output=run_root / "schema-dump.log",
        )
        run(
            [
                binaries / "pg_restore.exe",
                *common,
                "-d",
                database,
                "--clean",
                "--if-exists",
                "--no-owner",
                "--no-privileges",
                "--single-transaction",
                "--exit-on-error",
                run_root / "schema.dump",
            ],
            env=clone_env,
            output=run_root / "schema-restore.log",
        )
        report["test_database"] = database
        report["copied_research_database"] = research_db
        test_env = {
            **os.environ,
            "CHART_OBSERVATORY_TEST_DATABASE_URL": clone_url.set(
                database=database, query=writable
            ).render_as_string(hide_password=False),
            "CHART_OBSERVATORY_GATE_CLONE_ROOT": str(run_root),
            "CHART_OBSERVATORY_GATE_CLONE_RUN_ID": run_id,
            "CHART_OBSERVATORY_GATE_SOURCE_DATABASE": research_db,
        }
        stage("Running PostgreSQL integration tests; HTTP/ADC/real SDK clients denied")
        try:
            run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "tests/integration/lyrics/test_classification_gate_postgres.py",
                    "tests/integration/lyrics/test_classification_queue_lock.py",
                    "-q",
                    "--basetemp",
                    ROOT / "tmp" / f"postgres-gate-tests-{run_id}",
                    "--junitxml",
                    run_root / "junit.xml",
                ],
                env=test_env,
                output=run_root / "pytest.log",
                timeout=180,
            )
            exit_code = 0
        except RuntimeError:
            report["tests_failed"] = True
        report["restored_after"] = logical_manifest(restored_url)
        report["restored_research_unchanged"] = (
            report["restored_after"] == report["restored_before"]
        )
        if not report["restored_research_unchanged"]:
            exit_code = 1
    except Exception as exc:
        # Exception text may contain connection details; keep only the type in public output.
        report["failure"] = type(exc).__name__
    finally:
        if started:
            stage("Stopping only the isolated cluster")
            try:
                run(
                    [binaries / "pg_ctl.exe", "-D", target, "-m", "fast", "-t", "45", "-w", "stop"],
                    output=run_root / "shutdown.log",
                )
                report["clone_stopped"] = True
            except Exception as exc:
                report["shutdown_failure"] = type(exc).__name__
                exit_code = 1
        if baseline is not None:
            stage("Rechecking the original source through a read-only connection")
            try:
                report["source_after"] = logical_manifest(configured)
                report["source_logical_fingerprints_unchanged"] = report["source_after"] == baseline
                if not report["source_logical_fingerprints_unchanged"]:
                    exit_code = 1
            except Exception as exc:
                report["source_recheck_failure"] = type(exc).__name__
                exit_code = 1
        report["finished_at"] = datetime.now(UTC).isoformat()
        report["exit_code"] = exit_code
        (run_root / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2), flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
