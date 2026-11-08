"""Publish source-reproduced candidate proposals for staging, never approve recordings."""

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path

from import_all_quota_lyrics import ROOT, STORE

from chart_observatory.lyrics.quota_discovery import usable_cached_repair, usable_cached_replay
from chart_observatory.lyrics.source_chain import verify_source_chain
from chart_observatory.runtime_status import publish_status


def publish(proposals, current, destination, root):
    counts, checks = Counter(), []
    destination.mkdir(parents=True, exist_ok=True)
    for path in sorted(proposals.glob("*.json")):
        if path.name.endswith(".outcome.json"):
            continue
        raw = path.read_bytes()
        proposal = json.loads(raw)
        payload, result = proposal["payload"], proposal["result"]
        key, body = payload["recording_id"], result["text"]
        digest = hashlib.sha256(body.encode()).hexdigest()
        checked = verify_source_chain(payload, result, body, digest, root)
        before = current.get(key)
        usable = bool(
            before
            and (
                usable_cached_replay(before[0], before[1], proposal)
                or usable_cached_repair(before[0], before[1], proposal)
            )
        )
        record = dict(
            candidate_id=key,
            lyrics_sha256=digest,
            source_check=checked,
            usable_against_current_result=usable,
            approval=False,
        )
        if checked["status"] == "source_chain_matched" and usable:
            target = destination / (
                "duration-verified-" + hashlib.sha256(raw).hexdigest() + ".json"
            )
            if target.exists():
                if target.read_bytes() != raw:
                    raise ValueError("existing proposal contradicts its hash")
                counts["already_published"] += 1
            else:
                part = target.with_suffix(".part")
                part.write_bytes(raw)
                part.replace(target)
                counts["published"] += 1
            record["published_file"] = str(target)
        else:
            counts["held_for_review"] += 1
        counts[checked["status"]] += 1
        checks.append(record)
    return dict(counts), checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposals", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if any(not p.resolve().is_relative_to(ROOT) for p in (args.proposals, args.report)):
        parser.error("proposal and report paths must remain inside the project")
    with sqlite3.connect((STORE / "acquisition.sqlite").as_uri() + "?mode=ro", uri=True) as db:
        current = {
            key: (json.loads(p), json.loads(r) if r else {})
            for key, p, r in db.execute("SELECT identity,payload,result FROM tasks")
        }
    counts, checks = publish(args.proposals, current, STORE / "offline-replay", ROOT)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.with_suffix(".jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in checks), encoding="utf-8"
    )
    publish_status(
        args.report,
        dict(
            counts=counts,
            approvals=0,
            network_requests=0,
            acquisition_database_writes=0,
            paid_calls=0,
        ),
    )


if __name__ == "__main__":
    main()
