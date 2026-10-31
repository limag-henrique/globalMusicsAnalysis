"""Recover missing texts from verified local HTTP responses, with no network transport."""

import argparse
import hashlib
import json
import msvcrt
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx
from export_quota_lyric_review import BASE, ROOT, STORE, read_rows

from chart_observatory.ingestion.import_quotas import (
    apply_native_display_metadata,
    recovery_targets,
)
from chart_observatory.lyrics.quota_acquisition import PacedHTTP, fetch_candidate
from chart_observatory.lyrics.quota_discovery import audit_saved_result, discover_candidate
from chart_observatory.lyrics.text_quality import prepare_lyric_derivative
from chart_observatory.runtime_status import publish_status

OUTPUT = STORE / "offline-replay"
STATE = ROOT / "data/runtime/offline-lyrics-replay-20261031"


class LocalResponsesOnly(PacedHTTP):
    def get(self, url, **kwargs):
        with self._domain_guard:
            self._blocked_until[urlparse(url).netloc] = float("inf")
        return super().get(url, **kwargs)


def main(include_flagged=False):
    OUTPUT.mkdir(exist_ok=True)
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / "owner.lock").open("a+b") as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        publish_status(
            STATE / "status.json",
            dict(stage="verifying_local_selection_and_metadata", pid=os.getpid(),
                 updated_at=datetime.now(UTC).isoformat(), network_requests=0),
        )
        selected = read_rows(BASE / "combined.jsonl")
        enrichment = json.loads((BASE / "metadata-enrichment.json").read_text(encoding="utf-8"))
        for row in selected:
            meta = enrichment.get("resolved", {}).get(row["candidate_id"], {})
            for field in ("title", "artist"):
                if not row.get(field) and meta.get(field):
                    row[field] = meta[field]
        display_path = BASE / "native-display-metadata.json"
        if display_path.exists():
            apply_native_display_metadata(
                selected, json.loads(display_path.read_text(encoding="utf-8"))
            )
        with sqlite3.connect(
            f"file:{(STORE / 'acquisition.sqlite').as_posix()}?mode=ro", uri=True
        ) as db:
            known = {
                key: (state, json.loads(result) if result else {})
                for key, state, result in db.execute("SELECT identity,status,result FROM tasks")
            }
        if include_flagged:
            # Refresh stale flags from immutable blobs without changing the live writer's DB.
            for verified, (state, result) in enumerate(known.values(), 1):
                if verified == 1 or verified % 500 == 0:
                    publish_status(
                        STATE / "status.json",
                        dict(stage="verifying_saved_text_quality", pid=os.getpid(),
                             updated_at=datetime.now(UTC).isoformat(), network_requests=0,
                             verified_tasks=verified, total_tasks=len(known)),
                    )
                if state == "running" or not result.get("text_path"):
                    continue
                raw = Path(result["text_path"]).read_bytes()
                if hashlib.sha256(raw).hexdigest() != result.get("text_sha256"):
                    raise ValueError("saved lyric blob hash mismatch")
                quality = prepare_lyric_derivative(
                    raw.decode("utf-8"), result.get("source", "UNKNOWN")
                )
                result["text_quality_flags"] = sorted(
                    set(result.get("text_quality_flags", [])) | set(quality.flags)
                )
        targets = [
            row
            for row in recovery_targets(selected)
            if (
                not known.get(row["recording_id"], ("pending", {}))[1].get("text_path")
                or (
                    include_flagged
                    and (
                        (
                            audit := audit_saved_result(
                                row, known.get(row["recording_id"], ("pending", {}))[1]
                            )
                        )["source_quarantined"]
                        or audit["text_quality_flags"]
                    )
                )
            )
            and known.get(row["recording_id"], ("pending", {}))[0] != "running"
        ]
        counts = dict(
            total=len(targets), processed=0, recovered=0, previously_recovered=0, errors=0
        )

        def report(stage):
            publish_status(STATE / "status.json",
                    dict(
                        stage=stage,
                        pid=os.getpid(),
                        updated_at=datetime.now(UTC).isoformat(),
                        network_requests=0,
                        counts=counts,
                    ),
            )

        def forbidden(request):
            raise AssertionError("offline replay attempted network access")

        quality = ROOT / "data/derived/research_quality"
        caches = [
            STORE / "http-cache",
            *quality.glob("corpus-revision-*/*/http-cache"),
            *quality.glob("recovery-expanded-*/http-cache"),
            *(ROOT / "data/derived/annual_revision").glob("*/acquisition/http-cache"),
        ]
        with httpx.Client(transport=httpx.MockTransport(forbidden)) as client:
            http = LocalResponsesOnly(OUTPUT / "http-cache", client, cache_sources=caches)

            def recover(payload):
                previous = known.get(payload["recording_id"], ("pending", {}))[1]
                old_hash = previous.get("text_sha256") if previous.get("text_path") else None
                kind = "flagged_repair" if old_hash else "missing_text"
                signature = json.dumps(
                    [
                        payload["recording_id"],
                        payload["title"],
                        payload["artist"],
                        "main-entity-native-display-v2",
                        *([kind, old_hash] if old_hash else []),
                    ],
                    ensure_ascii=False,
                )
                path = OUTPUT / (hashlib.sha256(signature.encode()).hexdigest() + ".json")
                if path.exists():
                    return "previously_recovered"
                try:
                    result = discover_candidate(payload["title"], payload["artist"], http)
                    audit = audit_saved_result(payload, result)
                    if (
                        not result.get("text")
                        or audit["source_quarantined"]
                        or audit["text_quality_flags"]
                    ):
                        alternative = fetch_candidate(
                            payload["title"],
                            payload["artist"],
                            http,
                            html_sources={"AZLYRICS", "MUSIXMATCH"},
                        )
                        alternative_audit = audit_saved_result(payload, alternative)
                        if (
                            alternative.get("text")
                            and not alternative_audit["source_quarantined"]
                            and not alternative_audit["text_quality_flags"]
                        ):
                            result = alternative
                    final_audit = audit_saved_result(payload, result)
                    if (
                        result.get("text")
                        and not final_audit["source_quarantined"]
                        and not final_audit["text_quality_flags"]
                    ):
                        part = path.with_suffix(".part")
                        part.write_text(
                            json.dumps(
                                dict(
                                    payload=payload,
                                    result=result,
                                    recovered_at=datetime.now(UTC).isoformat(),
                                    network_requests=0,
                                    replay_kind=kind,
                                    replaces_text_sha256=old_hash,
                                ),
                                ensure_ascii=False,
                            ),
                            encoding="utf-8",
                        )
                        part.replace(path)
                        return "recovered"
                    return "not_found"
                except Exception as exc:
                    if isinstance(exc, AssertionError):
                        raise
                    return "errors"

            report("replaying_local_responses")
            with ThreadPoolExecutor(4) as pool:
                for future in as_completed([pool.submit(recover, row) for row in targets]):
                    outcome = future.result()
                    counts["processed"] += 1
                    if outcome in counts:
                        counts[outcome] += 1
                    if counts["processed"] % 100 == 0:
                        report("replaying_local_responses")
            report("finished_pending_import_and_validation")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-root", type=Path)
    parser.add_argument("--state-root", type=Path)
    parser.add_argument("--include-flagged", action="store_true")
    args = parser.parse_args()
    if args.base_root:
        BASE = args.base_root.resolve()
    if args.state_root:
        STATE = args.state_root.resolve()
    main(args.include_flagged)
