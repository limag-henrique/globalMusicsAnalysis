"""Durable retry scheduling and immutable, source-preserving acquisition batches."""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4


def fingerprint(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class RetrySchedule:
    """Retry failed access only after its deadline; changed inputs start a new attempt."""

    def __init__(self, db: sqlite3.Connection, minimum_seconds: float = 3600):
        if not math.isfinite(minimum_seconds) or minimum_seconds <= 0:
            raise ValueError("retry minimum must be finite and positive")
        self.db, self.minimum = db, minimum_seconds
        db.execute("""CREATE TABLE IF NOT EXISTS supplemental_retry_schedule (
            song_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
            attempts INTEGER NOT NULL, next_at REAL NOT NULL)""")

    def due(self, song_id: str, input_hash: str, *, now: float | None = None) -> bool:
        row = self.db.execute(
            "SELECT fingerprint,next_at FROM supplemental_retry_schedule WHERE song_id=?",
            (song_id,),
        ).fetchone()
        return row is None or row[0] != input_hash or row[1] <= (time.time() if now is None else now)

    def record(
        self, song_id: str, input_hash: str, failure: str | None,
        *, now: float | None = None, provider_delay: float = 0,
    ) -> None:
        if failure != "access_failed_rate_limited":
            self.db.execute("DELETE FROM supplemental_retry_schedule WHERE song_id=?", (song_id,))
            return
        row = self.db.execute(
            "SELECT fingerprint,attempts FROM supplemental_retry_schedule WHERE song_id=?", (song_id,)
        ).fetchone()
        attempts = row[1] + 1 if row and row[0] == input_hash else 1
        delay = max(min(86400, self.minimum * 2 ** min(attempts - 1, 16)), provider_delay)
        self.db.execute(
            "INSERT OR REPLACE INTO supplemental_retry_schedule VALUES (?,?,?,?)",
            (song_id, input_hash, attempts, (time.time() if now is None else now) + delay),
        )


@contextmanager
def worker_lock(path: Path):
    """One writer per state root, with OS-owned recovery after a process exits."""
    with path.open("a+b") as handle:
        handle.seek(0)
        if not handle.read(1):
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def freeze_batch(
    db: sqlite3.Connection, root: Path, first_id: int, last_id: int, *, project: Path,
) -> Path:
    """Publish the exact ledger range, current candidate rows and referenced source bytes.

    Call under the worker lock, after committing the batch and before the next batch.
    Missing evidence is recorded as a deficit; a manifest never grants approval.
    """
    directory = root / "batches" / f"ledger-{first_id:09d}-{last_id:09d}"
    manifest = directory / "manifest.json"
    if manifest.exists():
        saved = json.loads(manifest.read_text(encoding="utf-8"))
        for item in saved["files"]:
            path = (directory / item["path"]).resolve()
            if not path.is_relative_to(directory.resolve()) or file_sha256(path) != item["sha256"]:
                raise ValueError("published batch was modified")
        return manifest
    if first_id < 1 or last_id < first_id:
        raise ValueError("invalid ledger range")
    temporary = directory.with_name(directory.name + ".pending-" + uuid4().hex)
    temporary.mkdir(parents=True)
    cursor = db.execute(
        "SELECT * FROM supplemental_lyric_ledger WHERE id BETWEEN ? AND ? ORDER BY id",
        (first_id, last_id),
    )
    names = [column[0] for column in cursor.description]
    attempts = [dict(zip(names, row, strict=True)) for row in cursor]
    if not attempts or attempts[0]["id"] != first_id or attempts[-1]["id"] != last_id:
        raise ValueError("ledger range is incomplete")
    candidates, missing, copies = [], [], {}

    def preserve(song_id, source, category, expected_hash=None):
        path = Path(source)
        path = path.resolve() if path.is_absolute() else (project / path).resolve()
        if not path.is_relative_to(project.resolve()) or not path.is_file():
            missing.append(dict(song_id=song_id, kind=category, source_path=str(path)))
            return
        actual = file_sha256(path)
        if expected_hash and actual != expected_hash:
            missing.append(dict(song_id=song_id, kind=category, reason="hash_mismatch"))
            return
        target = f"{category}/{actual}{path.suffix}"
        if str(path) not in copies:
            destination = temporary / target
            destination.parent.mkdir(exist_ok=True)
            shutil.copyfile(path, destination)
            if file_sha256(destination) != actual:
                raise ValueError("evidence changed during snapshot")
            copies[str(path)] = target

    for song_id in sorted({row["song_id"] for row in attempts}):
        cursor = db.execute("SELECT * FROM supplemental_lyrics WHERE song_id=?", (song_id,))
        columns = [column[0] for column in cursor.description]
        row = cursor.fetchone()
        if row is None:
            missing.append(dict(song_id=song_id, kind="candidate_row"))
            continue
        record = dict(zip(columns, row, strict=True))
        candidates.append(record)
        if record["text_path"]:
            preserve(song_id, record["text_path"], "texts", record["text_sha256"])
        result = json.loads(record["result_json"])
        for event in result.get("http_evidence", []):
            if event.get("cache_path"):
                preserve(song_id, event["cache_path"], "cache")
            elif event.get("status") == 200:
                missing.append(dict(song_id=song_id, kind="successful_response_without_cache"))
    for name, rows in [("attempts.jsonl", attempts), ("candidates.jsonl", candidates)]:
        (temporary / name).write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8",
        )
    (temporary / "source-map.json").write_text(json.dumps(copies, indent=2), encoding="utf-8")
    files = [
        dict(path=path.relative_to(temporary).as_posix(), sha256=file_sha256(path),
             size_bytes=path.stat().st_size)
        for path in sorted(temporary.rglob("*")) if path.is_file()
    ]
    payload = dict(
        schema_version="supplemental-frozen-batch-v1", ledger_range=[first_id, last_id],
        attempts=len(attempts), candidate_count=len(candidates), files=files,
        missing_evidence=missing, referenced_evidence_complete=not missing,
        source_replay_complete=False, validator_replay_performed=False,
        scientific_approval=False, core_integration_performed=False, uploads=0, paid_calls=0,
    )
    (temporary / "manifest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (temporary / "manifest.sha256").write_text(
        file_sha256(temporary / "manifest.json") + "\n", encoding="utf-8",
    )
    temporary.rename(directory)
    return manifest
