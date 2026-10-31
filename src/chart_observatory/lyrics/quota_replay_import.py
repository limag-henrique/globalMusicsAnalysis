"""Apply audited local candidates under the acquisition writer's exclusive lock."""

import hashlib
import json
from collections import defaultdict
from pathlib import Path

from chart_observatory.lyrics.quota_discovery import (
    audit_saved_result,
    settle_metadata_reconciliation,
    usable_cached_repair,
    usable_cached_replay,
)


def import_cached_candidates(store, wanted, directory, progress=None):
    """No network; do not call while acquisition futures are active."""
    current = [
        row
        for row in store.conn.execute("SELECT identity,payload,status,result FROM tasks")
        if row[0] in wanted
    ]
    if any(row[2] == "running" for row in current):
        raise RuntimeError("cached import requires a drained acquisition queue")
    by_id = defaultdict(list)
    counts = dict(imported=0, repairs=0, gaps=0, conflicts=0, invalid_replays=0)
    for path in sorted(directory.glob("*.json")):
        try:
            raw = path.read_bytes()
            replay = json.loads(raw)
            key = replay.get("payload", {}).get("recording_id")
            if key in wanted:
                by_id[key].append((path, hashlib.sha256(raw).hexdigest(), replay))
        except (OSError, ValueError, AttributeError):
            counts["invalid_replays"] += 1
    for key, raw_payload, _status, raw_result in current:
        payload = json.loads(raw_payload)
        old = json.loads(raw_result) if raw_result else {}
        options = {}
        for path, evidence_hash, replay in by_id.get(key, []):
            accepted = usable_cached_replay(payload, old, replay) or usable_cached_repair(
                payload, old, replay
            )
            if accepted:
                digest = hashlib.sha256(accepted["text"].encode()).hexdigest()
                options[digest] = path, evidence_hash, accepted
        if len(options) > 1:
            counts["conflicts"] += 1
            audit = audit_saved_result(payload, old)
            audit["text_quality_flags"].append("conflicting_offline_replays")
            with store.conn:
                store.conn.execute(
                    "INSERT OR REPLACE INTO evidence_audits VALUES (?,?)",
                    (key, json.dumps(audit, ensure_ascii=False)),
                )
            continue
        if not options:
            continue
        digest, (path, evidence_hash, accepted) = next(iter(options.items()))
        previous_hash = old.get("text_sha256")
        if (
            previous_hash
            and hashlib.sha256(Path(old["text_path"]).read_bytes()).hexdigest() != previous_hash
        ):
            raise ValueError("previous lyric hash mismatch; refusing cached repair")
        method = f"offline-replay-v2:{previous_hash or 'missing'}:{digest}"
        with store.conn:
            reserved = store.conn.execute(
                "INSERT INTO recovery_attempts VALUES (?,?,'reserved',?,NULL) "
                "ON CONFLICT(identity,method) DO UPDATE SET state='reserved' "
                "WHERE recovery_attempts.state!='finished'",
                (key, method, raw_result),
            ).rowcount
        if not reserved:
            continue
        result = {
            **accepted,
            "offline_replay_evidence_file": str(path),
            "offline_replay_evidence_sha256": evidence_hash,
        }
        if previous_hash:
            result["replaced_unverified_result"] = old
        store.finish(key, result)
        settled = settle_metadata_reconciliation(payload, result)
        stored_result = store.conn.execute(
            "SELECT result FROM tasks WHERE identity=?", (key,)
        ).fetchone()[0]
        with store.conn:
            if settled != payload:
                store.conn.execute(
                    "UPDATE tasks SET payload=? WHERE identity=?",
                    (json.dumps(settled, ensure_ascii=False), key),
                )
            store.conn.execute(
                "UPDATE recovery_attempts SET state='finished',result=? "
                "WHERE identity=? AND method=?",
                (stored_result, key, method),
            )
            store.conn.execute(
                "INSERT OR REPLACE INTO evidence_audits VALUES (?,?)",
                (key, json.dumps(audit_saved_result(settled, result), ensure_ascii=False)),
            )
        counts["imported"] += 1
        counts["repairs" if previous_hash else "gaps"] += 1
        if progress and counts["imported"] % 250 == 0:
            progress(dict(counts))
    return counts
