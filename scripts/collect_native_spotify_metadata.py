"""Bounded public native-ID metadata collection; persist no embed sessions or tokens."""

import argparse
import hashlib
import json
import msvcrt
import os
import sqlite3
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import UTC, datetime
from pathlib import Path

import httpx
from resolve_public_track_metadata import spotify_entity

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/raw/metadata_resolution/20261031"
STATE = ROOT / "data/runtime/native-spotify-metadata-20261031"


def wait_until(deadline):
    path = STATE / "status.json"
    status = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    status.update(
        stage="waiting_provider_cooldown",
        pid=os.getpid(),
        updated_at=datetime.now(UTC).isoformat(),
        resume_not_before=datetime.fromtimestamp(deadline, UTC).isoformat(),
    )
    part = path.with_suffix(".part")
    part.write_text(json.dumps(status, indent=2), encoding="utf-8")
    part.replace(path)
    while time.time() < deadline:
        time.sleep(max(0, min(15, deadline - time.time())))


def run(base, not_before=None, hours=8):
    STATE.mkdir(exist_ok=True)
    with (STATE / "owner.lock").open("a+b") as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        if not_before and not_before > time.time():
            wait_until(not_before)
        deadline = time.monotonic() + hours * 3600
        unproductive, rate_pauses = 0, 0
        while time.monotonic() < deadline:
            pause = collect(base, deadline)
            if not pause or pause["status"] not in (429, 500, 502, 503, 504):
                break
            rate_pauses += pause["status"] == 429
            unproductive = 0 if pause.get("resolved_progress", 0) > 0 else unproductive + 1
            delay = max(900 if pause["status"] == 429 else 60, pause.get("retry_after", 0))
            if rate_pauses >= 3 or unproductive >= 3 or time.monotonic() + delay >= deadline:
                break
            wait_until(time.time() + delay)


def collect(base, deadline=None):
    wanted = sorted(
        {
            row["candidate_id"]
            for row in map(
                json.loads, (base / "combined.jsonl").read_text(encoding="utf-8").splitlines()
            )
            if row["candidate_id"].startswith("SPOTIFY:")
        }
    )
    db = sqlite3.connect(CACHE / "native-metadata.sqlite")
    db.execute(
        "CREATE TABLE IF NOT EXISTS evidence(candidate_id TEXT PRIMARY KEY, proof TEXT NOT NULL)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS attempts(candidate_id TEXT, observed_at TEXT, proof TEXT)"
    )
    for key in wanted:
        native = key.removeprefix("SPOTIFY:")
        saved = CACHE / f"rank-change-{native}.json"
        if saved.exists():
            with db:
                db.execute(
                    "INSERT OR IGNORE INTO evidence VALUES (?,?)",
                    (key, saved.read_text(encoding="utf-8")),
                )
    known = dict(db.execute("SELECT candidate_id,proof FROM evidence"))
    pending = [key for key in wanted if key not in known]
    counts = dict(
        selected=len(wanted),
        cached=len(wanted) - len(pending),
        requested=0,
        resolved=0,
        unavailable=0,
    )
    output = CACHE / "native-proof-batches"
    output.mkdir(exist_ok=True)
    previous = base / "native-display-metadata.json"
    refs = json.loads(previous.read_text(encoding="utf-8")) if previous.exists() else {}

    def publish(stage):
        proofs = {}
        for key, raw in db.execute("SELECT candidate_id,proof FROM evidence ORDER BY rowid"):
            proof = json.loads(raw)
            if (
                proof.get("status") == 200
                and (proof.get("metadata") or {}).get("uri")
                == f"spotify:track:{key.removeprefix('SPOTIFY:')}"
            ):
                proofs[key] = proof
        items = list(proofs.items())
        for offset in range(0, len(items), 100):
            chunk = dict(items[offset : offset + 100])
            raw = json.dumps(chunk, ensure_ascii=False, sort_keys=True).encode()
            digest = hashlib.sha256(raw).hexdigest()
            path = output / f"{digest}.json"
            if not path.exists():
                part = path.with_suffix(".part")
                part.write_bytes(raw)
                part.replace(path)
            for key in chunk:
                refs[key] = dict(evidence_file=str(path), evidence_sha256=digest, evidence_key=key)
        part = previous.with_suffix(".part")
        part.write_text(json.dumps(refs, ensure_ascii=False, indent=2), encoding="utf-8")
        part.replace(previous)
        counts["resolved"] = len(proofs)
        part = STATE / "status.part"
        part.write_text(
            json.dumps(
                dict(
                    stage=stage,
                    pid=os.getpid(),
                    updated_at=datetime.now(UTC).isoformat(),
                    counts=counts,
                    base_root=str(base),
                    session_tokens_saved=False,
                    recording_and_lyrics_validated=False,
                ),
                indent=2,
            ),
            encoding="utf-8",
        )
        part.replace(STATE / "status.json")

    stop, pace = threading.Event(), threading.Lock()
    pause_reason = None
    last_start = 0.0
    with httpx.Client(timeout=20, follow_redirects=True) as client:

        def fetch(key):
            nonlocal last_start
            native = key.removeprefix("SPOTIFY:")
            url = f"https://open.spotify.com/embed/track/{native}"
            with pace:
                time.sleep(max(0, 1.0 - (time.monotonic() - last_start)))
                if stop.is_set():
                    return None
                last_start = time.monotonic()
            try:
                response = client.get(url)
                if response.status_code in (401, 403, 429, 500, 502, 503, 504):
                    stop.set()
                return dict(
                    source_url=url,
                    status=response.status_code,
                    body_sha256=hashlib.sha256(response.content).hexdigest(),
                    retry_after=int(response.headers.get("Retry-After", "0"))
                    if response.headers.get("Retry-After", "0").isdigit()
                    else 0,
                    retrieved_at=datetime.now(UTC).isoformat(),
                    metadata=spotify_entity(response.text, native)
                    if response.status_code == 200
                    else None,
                )
            except (httpx.HTTPError, ValueError, TypeError, AttributeError, KeyError) as exc:
                return dict(source_url=url, error_type=type(exc).__name__, metadata=None)

        iterator, active = iter(pending), {}
        publish("collecting_public_native_metadata")
        with ThreadPoolExecutor(2) as pool:
            while True:
                while (
                    len(active) < 2
                    and not stop.is_set()
                    and (deadline is None or time.monotonic() < deadline)
                ):
                    key = next(iterator, None)
                    if key is None:
                        break
                    active[pool.submit(fetch, key)] = key
                if not active:
                    break
                done, _ = wait(active, timeout=10, return_when=FIRST_COMPLETED)
                for future in done:
                    key, proof = active.pop(future), future.result()
                    if proof is None:
                        continue
                    counts["requested"] += 1
                    with db:
                        db.execute(
                            "INSERT INTO attempts VALUES (?,?,?)",
                            (
                                key,
                                datetime.now(UTC).isoformat(),
                                json.dumps(proof, ensure_ascii=False),
                            ),
                        )
                    if proof.get("status") in (401, 403, 429, 500, 502, 503, 504):
                        proposed = {
                            "status": proof["status"],
                            "retry_after": proof.get("retry_after", 0),
                        }
                        priority = {401: 3, 403: 3, 429: 2}
                        if not pause_reason or priority.get(proposed["status"], 1) >= priority.get(
                            pause_reason["status"], 1
                        ):
                            proposed["retry_after"] = max(
                                proposed["retry_after"], (pause_reason or {}).get("retry_after", 0)
                            )
                            pause_reason = proposed
                        counts["pause_http_status"] = pause_reason["status"]
                        if proof["status"] in (500, 502, 503, 504):
                            failures = db.execute(
                                "SELECT count(*) FROM attempts WHERE candidate_id=? "
                                "AND json_extract(proof,'$.status') IN (500,502,503,504)",
                                (key,),
                            ).fetchone()[0]
                            if failures >= 3:
                                proof["pending_review_reason"] = "persistent_transient_response"
                                with db:
                                    db.execute(
                                        "INSERT OR IGNORE INTO evidence VALUES (?,?)",
                                        (key, json.dumps(proof, ensure_ascii=False)),
                                    )
                    if not proof.get("metadata"):
                        counts["unavailable"] += 1
                    if proof.get("status") not in (
                        401,
                        403,
                        429,
                        500,
                        502,
                        503,
                        504,
                    ) and not proof.get("error_type"):
                        with db:
                            db.execute(
                                "INSERT OR IGNORE INTO evidence VALUES (?,?)",
                                (key, json.dumps(proof, ensure_ascii=False)),
                            )
                if counts["requested"] % 100 == 0:
                    publish("collecting_public_native_metadata")
            publish(
                "provider_access_paused"
                if stop.is_set()
                else "time_window_ended_pending_metadata"
                if deadline and time.monotonic() >= deadline
                else "collected_pending_lyric_identity_review"
            )
    db.close()
    if pause_reason:
        pause_reason["resolved_progress"] = counts["requested"] - counts["unavailable"]
    return pause_reason


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-root", type=Path, required=True)
    parser.add_argument("--not-before", type=float)
    parser.add_argument("--hours", type=float, default=8)
    args = parser.parse_args()
    if not 0 < args.hours <= 24:
        parser.error("hours must be in (0,24]")
    run(args.base_root.resolve(), args.not_before, args.hours)
