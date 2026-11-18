"""Read-only parity check across canonical SQLite, staging SQLites, and PostgreSQL (port 55433)."""

import argparse
import hashlib
import json
import os
import socket
import sqlite3
import subprocess
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import psycopg
from dotenv import dotenv_values
from sqlalchemy.engine import make_url


def _pg_listening(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False


@contextmanager
def ensure_local_pg(host: str, port: int):
    if _pg_listening(host, port):
        yield "peer_or_existing_running"
        return

    ps_out = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            ". ./scripts/research_postgres_paths.ps1; Get-ResearchPostgresLayout | ConvertTo-Json",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    )
    layout = json.loads(ps_out.stdout)
    pg_ctl = Path(layout["Binaries"]) / "pg_ctl.exe"
    cluster = Path(layout["Cluster"])
    log_file = Path(layout["Base"]) / "postgres16-parity.log"

    subprocess.run(
        [str(pg_ctl), "-D", str(cluster), "-l", str(log_file), "-w", "start"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
        timeout=45,
    )
    try:
        yield "started_and_stopped_cleanly"
    finally:
        subprocess.run(
            [str(pg_ctl), "-D", str(cluster), "-w", "stop", "-m", "fast"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )


def check_sqlite_canonical(catalog_path: Path, selection_path: Path) -> dict:
    db = sqlite3.connect(catalog_path.resolve().as_uri() + "?mode=ro", uri=True)
    quick = db.execute("PRAGMA quick_check").fetchone()[0]
    fk_viol = len(db.execute("PRAGMA foreign_key_check").fetchall())
    songs_count = db.execute("SELECT count(*) FROM songs").fetchone()[0]
    members_count = db.execute("SELECT count(*) FROM memberships").fetchone()[0]
    charts_count = db.execute("SELECT count(*) FROM charts").fetchone()[0]
    orphan_members = db.execute(
        "SELECT count(*) FROM memberships m LEFT JOIN songs s ON s.id = m.song_id WHERE s.id IS NULL"
    ).fetchone()[0]

    sel_ids = set()
    with (selection_path / "combined.jsonl").open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                sel_ids.add(json.loads(line)["candidate_id"])

    song_rows = {
        cid: json.loads(res) if res else {}
        for cid, res in db.execute("SELECT id, result FROM songs")
    }
    db.close()

    missing_sel_songs = len(sel_ids - set(song_rows))
    by_staging_db: dict[str, list[tuple[str, str, str, str]]] = {}
    for cid in sel_ids:
        res = song_rows.get(cid) or {}
        ref = res.get("staging_reference")
        if ref:
            db_key = str(Path(ref["database"]).resolve())
            by_staging_db.setdefault(db_key, []).append(
                (cid, ref["run_id"], ref["candidate_id"], res.get("text_sha256") or "")
            )

    staging_refs = 0
    staging_hash_ok = 0
    staging_hash_mismatch = 0
    staging_missing_ref = 0
    for db_key, items in by_staging_db.items():
        sconn = sqlite3.connect(Path(db_key).as_uri() + "?mode=ro", uri=True)
        run_ids = tuple({it[1] for it in items})
        placeholders = ",".join("?" * len(run_ids))
        blob_map = {
            (rid, rcid): (sha, body)
            for rid, rcid, sha, body in sconn.execute(
                f"SELECT c.run_id, c.candidate_id, c.text_sha256, b.body "
                f"FROM quota_lyric_staging_candidates c "
                f"JOIN quota_lyric_staging_blobs b ON b.sha256=c.text_sha256 "
                f"WHERE c.run_id IN ({placeholders})",
                run_ids,
            )
        }
        sconn.close()
        for _, rid, rcid, expected_sha in items:
            staging_refs += 1
            hit = blob_map.get((rid, rcid))
            if hit is None:
                staging_missing_ref += 1
            elif hit[0] == expected_sha and hashlib.sha256(hit[1].encode("utf-8")).hexdigest() == hit[0]:
                staging_hash_ok += 1
            else:
                staging_hash_mismatch += 1

    return {
        "quick_check": quick,
        "foreign_key_violations": fk_viol,
        "songs_total": songs_count,
        "memberships_total": members_count,
        "charts_total": charts_count,
        "orphan_memberships": orphan_members,
        "v10_selected_candidates": len(sel_ids),
        "missing_v10_candidates_in_catalog": missing_sel_songs,
        "v10_staging_references_checked": staging_refs,
        "v10_staging_hash_ok": staging_hash_ok,
        "v10_staging_hash_mismatch": staging_hash_mismatch,
        "v10_staging_missing_ref": staging_missing_ref,
        "v10_song_shas": {
            cid: {
                "text_sha256": (song_rows[cid] or {}).get("text_sha256"),
                "source": (song_rows[cid] or {}).get("source"),
                "staging_reference": (song_rows[cid] or {}).get("staging_reference"),
                "text_path": (song_rows[cid] or {}).get("text_path"),
            }
            for cid in sel_ids
            if cid in song_rows
        },
    }


def check_postgres_ro(v10_song_shas: dict[str, str | None]) -> dict:
    db_url = os.environ.get("CHART_OBSERVATORY_DATABASE_URL") or dotenv_values(".env").get(
        "CHART_OBSERVATORY_DATABASE_URL"
    )
    if not db_url:
        raise RuntimeError("CHART_OBSERVATORY_DATABASE_URL not configured")
    url = make_url(db_url)
    host = url.host or "127.0.0.1"
    port = int(url.port or 55433)
    dsn = url.set(drivername="postgresql", query={}).render_as_string(hide_password=False)

    with ensure_local_pg(host, port) as pg_lifecycle:
        info: dict = {
            "host": host,
            "port": port,
            "database": url.database,
            "service_ownership_mode": pg_lifecycle,
        }
        with psycopg.connect(
            dsn, connect_timeout=10, options="-c default_transaction_read_only=on -c timezone=UTC"
        ) as conn:
            info["transaction_read_only"] = conn.execute("SHOW transaction_read_only").fetchone()[0]
            info["alembic_version"] = conn.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchone()[0]
            for tbl in (
                "canonical_tracks",
                "lyric_documents",
                "lyric_classification_snapshots",
                "quota_lyric_staging_runs",
                "quota_lyric_staging_candidates",
                "quota_lyric_staging_blobs",
            ):
                info[f"pg_{tbl}"] = conn.execute(f"SELECT count(*) FROM public.{tbl}").fetchone()[0]

            pg_runs = {
                r[0]
                for r in conn.execute("SELECT id FROM public.quota_lyric_staging_runs").fetchall()
            }
            cfg = json.loads(
                Path("data/runtime/final-pipeline-v10-canonical-final-config.json").read_text(
                    encoding="utf-8"
                )
            )
            cfg_runs = [s["run_id"] for s in cfg.get("staging", [])]
            info["canonical_staging_runs_in_pg"] = [r for r in cfg_runs if r in pg_runs]
            info["canonical_staging_runs_missing_in_pg"] = [r for r in cfg_runs if r not in pg_runs]

            # Compare candidate IDs / text hashes between canonical SQLite and PG quota_lyric_staging_candidates
            pg_cand_shas: dict[str, set[str]] = {}
            for cid, sha in conn.execute(
                "SELECT candidate_id, text_sha256 FROM public.quota_lyric_staging_candidates WHERE text_sha256 IS NOT NULL"
            ):
                pg_cand_shas.setdefault(cid, set()).add(sha)

            # Also check whether sqlite text_sha256 exists anywhere in pg_lyric_documents.content_sha256
            pg_doc_shas_all = {
                r[0]
                for r in conn.execute(
                    "SELECT DISTINCT content_sha256 FROM public.lyric_documents WHERE content_sha256 IS NOT NULL"
                )
            }

            in_both_exact_sha = 0
            in_both_diff_sha = 0
            in_sqlite_not_pg = 0
            discrepancies = []
            for cid, meta in sorted(v10_song_shas.items()):
                csha = meta.get("text_sha256")
                if not csha:
                    continue
                if cid not in pg_cand_shas:
                    in_sqlite_not_pg += 1
                    discrepancies.append({
                        "candidate_id": cid,
                        "discrepancy_type": "missing_from_pg_staging",
                        "reason": "expected_snapshot_skew_filesystem_store_or_retry_not_in_pg_staging" if not meta.get("staging_reference") else "staging_reference_missing_in_pg",
                        "sqlite_text_sha256": csha,
                        "sqlite_source": meta.get("source"),
                        "sqlite_staging_run_id": (meta.get("staging_reference") or {}).get("run_id"),
                        "sqlite_text_path": meta.get("text_path"),
                        "pg_staging_shas": [],
                        "in_pg_lyric_documents_content_sha256": csha in pg_doc_shas_all,
                    })
                elif csha in pg_cand_shas[cid]:
                    in_both_exact_sha += 1
                else:
                    in_both_diff_sha += 1
                    discrepancies.append({
                        "candidate_id": cid,
                        "discrepancy_type": "different_sha_in_pg_staging",
                        "reason": "expected_snapshot_skew_newer_store_or_retry_replacement_in_sqlite" if not meta.get("staging_reference") else "expected_snapshot_skew_newer_staging_run",
                        "sqlite_text_sha256": csha,
                        "sqlite_source": meta.get("source"),
                        "sqlite_staging_run_id": (meta.get("staging_reference") or {}).get("run_id"),
                        "sqlite_text_path": meta.get("text_path"),
                        "pg_staging_shas": sorted(pg_cand_shas[cid]),
                        "in_pg_lyric_documents_content_sha256": csha in pg_doc_shas_all,
                    })

            info["sqlite_vs_pg_staging_parity"] = {
                "v10_candidates_with_sha_in_sqlite": sum(1 for v in v10_song_shas.values() if v.get("text_sha256")),
                "matched_exact_sha_in_pg_staging": in_both_exact_sha,
                "present_in_pg_staging_different_sha_snapshot_skew": in_both_diff_sha,
                "missing_from_pg_staging_snapshot_skew": in_sqlite_not_pg,
                "discrepancies": discrepancies,
            }
        return info


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=Path("data/runtime/final-pipeline/catalog.sqlite"))
    parser.add_argument(
        "--selection",
        type=Path,
        default=Path("data/derived/annual_revision/population-total-150k-2018-2026-20261116-v10-archives"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/runtime/antigravity-collaboration-20261115/persistence-parity-20261117-01.json"),
    )
    args = parser.parse_args(argv)

    sqlite_res = check_sqlite_canonical(args.catalog, args.selection)
    v10_shas = sqlite_res.pop("v10_song_shas")
    pg_res = check_postgres_ro(v10_shas)
    discrepancies = pg_res["sqlite_vs_pg_staging_parity"].pop("discrepancies", [])
    disc_path = args.output.with_name("persistence-parity-discrepancies-20261118-01.jsonl")
    with disc_path.open("w", encoding="utf-8") as df:
        for d in discrepancies:
            df.write(json.dumps(d, ensure_ascii=False) + "\n")
    from collections import Counter
    pg_res["sqlite_vs_pg_staging_parity"]["discrepancy_reason_counts"] = dict(
        Counter((d["discrepancy_type"], d["reason"]) for d in discrepancies).most_common()
    )
    pg_res["sqlite_vs_pg_staging_parity"]["discrepancies_jsonl"] = str(disc_path)
    pg_res["sqlite_vs_pg_staging_parity"]["discrepancies_jsonl_sha256"] = hashlib.sha256(
        disc_path.read_bytes()
    ).hexdigest()
    # Serialize tuple keys as strings
    pg_res["sqlite_vs_pg_staging_parity"]["discrepancy_reason_counts"] = {
        f"{k[0]}:{k[1]}": v for k, v in Counter((d["discrepancy_type"], d["reason"]) for d in discrepancies).most_common()
    }
    report = {
        "schema_version": "persistence-parity-report-v2",
        "generated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "canonical_sqlite": sqlite_res,
        "postgresql_mirror": pg_res,
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
