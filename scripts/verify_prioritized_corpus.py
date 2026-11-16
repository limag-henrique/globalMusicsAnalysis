"""Audit every consolidated candidate, preserving country/year/rank priorities."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sqlite3
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from chart_observatory.final_pipeline import digest, encode, read_result, save
from chart_observatory.lyrics.automated_validation import assess_lyric_identity_completeness
from chart_observatory.lyrics.corpus_quality import assess_acquired_lyric
from chart_observatory.lyrics.identity_collisions import flag_shared_text_identities
from chart_observatory.lyrics.quota_acquisition import identity
from chart_observatory.lyrics.quota_discovery import audit_saved_result
from chart_observatory.lyrics.recovery_pipeline import (
    _flag_shared_provider_editions,
    apply_native_proof_to_record,
    load_native_spotify_proofs,
)
from chart_observatory.lyrics.source_chain import verify_source_chain

ROOT = Path(__file__).resolve().parents[1]
PROOFS = {}


def initialize(proof_file):
    global PROOFS
    PROOFS = json.loads(gzip.decompress(Path(proof_file).read_bytes()))


def verify(job):
    cid, payload, result = job
    try:
        source, body, previous = read_result(result, ROOT)
        payload = dict(payload)
        native, native_flags, native_evidence = apply_native_proof_to_record(
            cid, payload, source, PROOFS
        )
        if not cid.startswith("SPOTIFY:"):
            native, native_flags = False, ["native_recording_proof_missing"]
        sha = result.get("text_sha256")
        audit = audit_saved_result(payload, source)
        assessed = assess_acquired_lyric(payload, source, body, sha)
        flags = set(assessed.get("flags", [])) | set(native_flags)
        # Preserve prior cross-record conflicts until the complete cohort is rechecked.
        flags.update(
            f
            for f in previous.get("text_quality_flags", [])
            if f.startswith("same_text_") or f == "shared_provider_id_across_editions"
        )
        audit["text_quality_flags"] = sorted(flags)
        audit["source_quarantined"] = bool(
            audit.get("source_quarantined") or previous.get("source_quarantined")
        )
        chain = (
            verify_source_chain(payload, source, body, sha, ROOT)
            if body is not None
            else dict(status="unavailable")
        )
        record = dict(
            candidate_id=cid,
            payload=payload,
            source_result=dict(
                source=source.get("source"), source_metadata=source.get("source_metadata", {})
            ),
            text_sha256=sha,
            audit=audit,
        )
        # The full source result is necessary for assessment; retain only metadata in output.
        validation = assess_lyric_identity_completeness(
            dict(record, source_result=source), body, chain
        )
        record.update(
            validation=validation,
            native_supported=bool(native and not native_flags),
            native_evidence=native_evidence,
            has_text=body is not None,
            body_hash_verified=body is not None and digest(body.encode()) == sha,
        )
        return record
    except Exception as exc:
        return dict(
            candidate_id=cid,
            payload=payload,
            text_sha256=result.get("text_sha256"),
            audit=dict(text_quality_flags=["validator_error"]),
            source_result={},
            has_text=bool(result.get("text_sha256")),
            native_supported=False,
            validation={},
            error_type=type(exc).__name__,
        )


def load_inputs(
    catalog_path, stages, *, selection_rows=None, selection_scope=None, acquisitions=()
):
    with sqlite3.connect(catalog_path.resolve().as_uri() + "?mode=ro", uri=True) as db:
        jobs = {
            cid: [cid, json.loads(payload), json.loads(result) if result else {}]
            for cid, payload, result in db.execute("SELECT id,payload,result FROM songs")
        }
        members = db.execute(
            "SELECT scope,country,period,platform,rank,song_id FROM memberships"
        ).fetchall()
    if selection_rows is not None:
        scope = str(selection_scope.resolve()) if selection_scope else "population-selection"
        members = [
            (
                scope,
                row["country_code"],
                str(row["year"]),
                row["platform"],
                row["position"],
                row["candidate_id"],
            )
            for row in selection_rows
        ]
        for row in selection_rows:
            cid = row["candidate_id"]
            jobs.setdefault(cid, [cid, row, {}])
    for stage in stages:
        path = Path(stage["database"]).resolve()
        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
            db.execute("BEGIN")
            for cid, raw, sha in db.execute(
                "SELECT candidate_id,payload,text_sha256 FROM quota_lyric_staging_candidates "
                "WHERE run_id=?",
                (stage["run_id"],),
            ):
                if cid not in jobs or not sha:
                    continue
                payload = json.loads(raw)
                if any(
                    identity(payload.get(k)) != identity(jobs[cid][1].get(k))
                    for k in ("title", "artist")
                ):
                    continue
                jobs[cid] = [
                    cid,
                    payload,
                    dict(
                        text_sha256=sha,
                        staging_reference=dict(
                            database=str(path), run_id=stage["run_id"], candidate_id=cid
                        ),
                    ),
                ]
    for acquisition in acquisitions:
        path = Path(acquisition).resolve()
        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
            for cid, raw, _status, result_raw in db.execute(
                "SELECT identity,payload,status,result FROM tasks"
            ):
                if cid not in jobs or not result_raw:
                    continue
                result = json.loads(result_raw)
                if not result.get("text_sha256") or not result.get("text_path"):
                    continue
                payload = json.loads(raw)
                if any(
                    identity(payload.get(key)) != identity(jobs[cid][1].get(key))
                    for key in ("title", "artist")
                ):
                    continue
                jobs[cid] = [cid, payload, result]
    if selection_rows is not None:
        selected_ids = {row["candidate_id"] for row in selection_rows}
        jobs = {cid: job for cid, job in jobs.items() if cid in selected_ids}
    return jobs, members


def priorities(members):
    # Prefer the latest historical selection for scheduling, retaining all versions in reports.
    scopes = sorted({r[0] for r in members if r[0] != "current"})
    selected_scope = next(
        (s for s in reversed(scopes) if "v5" in s), scopes[-1] if scopes else "current"
    )
    selected = [r for r in members if r[0] == selected_scope]
    country_counts = Counter(r[1] for r in selected)
    priorities_by_song = {}
    for _scope, country, year, platform, rank, cid in selected:
        key = (-country_counts[country], country, rank, year, platform, cid)
        priorities_by_song[cid] = min(key, priorities_by_song.get(cid, key))
    # Current snapshots remain a separate scope after historical country/year positions.
    for _scope, country, period, platform, rank, cid in members:
        if cid not in priorities_by_song:
            priorities_by_song[cid] = (1, country, rank, period, platform, cid)
    return priorities_by_song, selected_scope


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=4, choices=range(1, 9))
    parser.add_argument("--selection", type=Path)
    parser.add_argument(
        "--stage",
        action="append",
        default=[],
        metavar="DATABASE|RUN_ID",
        help="Override configured staging inputs; repeat once per immutable staging run.",
    )
    parser.add_argument(
        "--acquisition",
        action="append",
        default=[],
        type=Path,
        help="Overlay local recovery-store results for the selected cohort.",
    )
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to(ROOT / "data/runtime"):
        raise ValueError("output must remain in project runtime")
    out.mkdir(parents=True, exist_ok=False)
    config = json.loads((ROOT / "config/final_pipeline.json").read_text())
    stages = config["staging"]
    if args.stage:
        stages = []
        for value in args.stage:
            database, separator, run_id = value.partition("|")
            if not separator or not database or not run_id:
                parser.error("--stage must be DATABASE|RUN_ID")
            stages.append(dict(database=database, run_id=run_id))
    selection_rows = None
    selection_scope = None
    if args.selection:
        from chart_observatory.research_flow import load_selection

        selection_scope = args.selection.resolve()
        _, _, selection_rows, _ = load_selection(selection_scope)
    jobs, members = load_inputs(
        ROOT / "data/runtime/final-pipeline/catalog.sqlite",
        stages,
        selection_rows=selection_rows,
        selection_scope=selection_scope,
        acquisitions=args.acquisition,
    )
    order, scope = priorities(members)
    ordered = sorted(jobs, key=lambda cid: order.get(cid, (2, cid)))
    proofs = load_native_spotify_proofs(ROOT)
    proof_file = out / "native-proof-snapshot.json.gz"
    proof_file.write_bytes(gzip.compress(encode(proofs).encode(), mtime=0))
    save(
        out / "inputs.json",
        dict(
            config=config,
            selection=str(selection_scope) if selection_scope else None,
            staging=stages,
            acquisitions=[str(path.resolve()) for path in args.acquisition],
            candidates=len(jobs),
            memberships=len(members),
            native_proof_sha256=digest(proof_file.read_bytes()),
            implementation_sha256=digest(Path(__file__).read_bytes()),
            priority_scope=scope,
            paid_calls=0,
        ),
    )
    records = []
    db = sqlite3.connect(out / "verification.sqlite")
    db.execute(
        "CREATE TABLE candidates("
        "id TEXT PRIMARY KEY,priority INTEGER,payload TEXT,result TEXT,verification TEXT)"
    )
    with (
        ProcessPoolExecutor(
            max_workers=args.workers, initializer=initialize, initargs=(str(proof_file),)
        ) as pool,
        (out / "decisions.preliminary.jsonl").open("x", encoding="utf-8") as log,
    ):
        for index, record in enumerate(
            pool.map(verify, (jobs[c] for c in ordered), chunksize=8), 1
        ):
            cid = record["candidate_id"]
            records.append(record)
            log.write(encode(record) + "\n")
            db.execute(
                "INSERT INTO candidates VALUES (?,?,?,?,?)",
                (cid, index, encode(jobs[cid][1]), encode(jobs[cid][2]), encode(record)),
            )
            if index % 250 == 0:
                db.commit()
                save(
                    out / "status.json",
                    dict(stage="verifying", completed=index, total=len(jobs)),
                )
                print(encode(dict(completed=index, total=len(jobs))), flush=True)
    db.commit()
    flag_shared_text_identities(records)
    _flag_shared_provider_editions(records, proofs)
    counts = Counter()
    decisions = {}
    with (out / "decisions.jsonl").open("x", encoding="utf-8") as log:
        for record in records:
            validation = record.get("validation", {})
            flags = record.get("audit", {}).get("text_quality_flags", [])
            collision = any(
                f.startswith("same_text_") or f == "shared_provider_id_across_editions"
                for f in flags
            )
            supported = (
                validation.get("identity", {}).get("status") == "passed"
                and validation.get("completeness", {}).get("status") == "passed"
                and not collision
                and not record.get("error_type")
            )
            record.update(
                provider_supported=supported,
                native_and_provider_supported=supported and record.get("native_supported", False),
                vertex_ready=False,
            )
            counts["total"] += 1
            counts["with_text"] += record["has_text"]
            counts["provider_supported"] += supported
            counts["native_and_provider_supported"] += record["native_and_provider_supported"]
            counts["validator_errors"] += bool(record.get("error_type"))
            counts["missing_text"] += not record["has_text"]
            decisions[record["candidate_id"]] = record
            log.write(encode(record) + "\n")
            db.execute(
                "UPDATE candidates SET verification=? WHERE id=?",
                (encode(record), record["candidate_id"]),
            )
    db.commit()
    db.close()
    with (out / "priority-import-queue.jsonl").open("x", encoding="utf-8") as handle:
        for cid in ordered:
            if not decisions[cid]["native_and_provider_supported"]:
                handle.write(
                    encode(
                        dict(
                            candidate_id=cid,
                            priority=order.get(cid),
                            payload=jobs[cid][1],
                            result=jobs[cid][2],
                        )
                    )
                    + "\n"
                )
    with (out / "country-year-rank.csv").open("x", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "scope",
                "country",
                "period",
                "platform",
                "position",
                "candidate_id",
                "with_text",
                "provider_supported",
                "native_and_provider_supported",
                "vertex_ready",
            ]
        )
        for member in sorted(members):
            rec = decisions[member[5]]
            writer.writerow(
                [
                    *member,
                    rec["has_text"],
                    rec["provider_supported"],
                    rec["native_and_provider_supported"],
                    False,
                ]
            )
    report = dict(
        counts=counts,
        vertex_ready=0,
        paid_calls=0,
        uploads=0,
        priority="countries by descending selected positions; rank ascending; year ascending",
        completed_at=datetime.now(UTC).isoformat(),
        complete=len(records) == len(jobs),
    )
    save(out / "report.json", report)
    save(out / "status.json", dict(stage="completed", **report))
    print(encode(report), flush=True)


if __name__ == "__main__":
    main()
