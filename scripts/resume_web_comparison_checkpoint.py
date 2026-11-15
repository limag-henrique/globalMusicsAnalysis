"""Resume a preserved web comparison in a fresh campaign without repeating reviews."""

import argparse
import hashlib
import json
import msvcrt
import os
import sqlite3
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from chart_observatory.lyrics.web_comparison import reuse_recent_web_responses
from chart_observatory.runtime_status import publish_status

ROOT = Path(__file__).resolve().parents[1]


def prepare(source, state, hours):
    if (state / "campaign.json").exists():
        raise ValueError("destination campaign already exists")
    with (source / "owner.lock").open("a+b") as owner:
        owner.seek(0)
        msvcrt.locking(owner.fileno(), msvcrt.LK_NBLCK, 1)
        parent = json.loads((source / "campaign.json").read_text(encoding="utf8"))
        state.mkdir(parents=True, exist_ok=True)
        with (
            sqlite3.connect((source / "comparison.sqlite").as_uri() + "?mode=ro", uri=True) as old,
            sqlite3.connect(state / "comparison.sqlite") as new,
        ):
            old.backup(new)
            if new.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("comparison checkpoint backup failed integrity check")
            checked = new.execute("SELECT count(*) FROM inputs WHERE done=1").fetchone()[0]
            results = new.execute("SELECT count(*) FROM results").fetchone()[0]
            if checked != results:
                raise ValueError("comparison result inventory differs from completed input count")
            proposals = new.execute(
                "SELECT count(*) FROM results WHERE "
                "json_extract(result,'$.proposal_file') IS NOT NULL"
            ).fetchone()[0]
            marked = int(
                (new.execute("SELECT value FROM meta WHERE key='published'").fetchone() or [0])[0]
            )
            published = max(
                0, marked - parent.get("prior_unpublished_proposals_require_reconciliation", 0)
            )
            # Every inherited proposal is skipped. Its original disposition remains
            # preserved in the parent campaign, including anything held for review.
            new.execute("INSERT OR REPLACE INTO meta VALUES ('published',?)", (str(proposals),))
            new.execute("DELETE FROM meta WHERE key='cache_reused'")
            new.commit()
            total = new.execute("SELECT count(*) FROM inputs").fetchone()[0]
        now = datetime.now(UTC)
        campaign = {
            **parent,
            "starts_at": now.isoformat(),
            "ends_at": (now + timedelta(hours=hours)).isoformat(),
            "parent_checkpoint": str(source),
            "parent_campaign_sha256": hashlib.sha256(
                (source / "campaign.json").read_bytes()
            ).hexdigest(),
            "inherited_completed": checked,
            "inherited_proposals_not_republished": proposals,
            "inherited_published": published,
            "prior_unpublished_proposals_require_reconciliation": proposals - published,
            "paid_calls_authorized": 0,
        }
        publish_status(state / "campaign.json", campaign)
        publish_status(
            state / "resume-inventory.json",
            dict(
                checked=checked,
                pending=total - checked,
                prior_proposals=proposals,
                prior_published=published,
                checkpoint_integrity="ok",
                approvals=0,
            ),
        )
        return campaign


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--hours", type=float, default=12)
    parser.add_argument("--wait-acquisition", type=Path)
    parser.add_argument("--response-cache", action="append", type=Path, default=[])
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    source, state = args.source.resolve(), args.state.resolve()
    if (
        not all(p.is_relative_to(ROOT / "data/runtime") for p in (source, state))
        or not 0 < args.hours <= 24
    ):
        raise ValueError("use project runtime paths and hours in (0,24]")
    if args.wait_acquisition:
        waited = args.wait_acquisition.resolve()
        if not waited.is_relative_to(ROOT / "data/runtime"):
            raise ValueError("dependency campaign outside project")
        deadline = datetime.now(UTC) + timedelta(hours=24)
        while datetime.now(UTC) < deadline:
            path = waited / "status.json"
            status = json.loads(path.read_text(encoding="utf8")) if path.exists() else {}
            if status.get("stage") == "completed_pending_reviews":
                break
            if status.get("stage", "").startswith(("failed", "paused")):
                raise RuntimeError("acquisition did not complete; comparison was not started")
            publish_status(
                state / "waiting.json",
                dict(
                    pid=os.getpid(),
                    stage="waiting_for_acquisition_provider_slot",
                    acquisition=str(waited),
                    updated_at=datetime.now(UTC).isoformat(),
                    approvals=0,
                    paid_calls=0,
                ),
            )
            time.sleep(15)
        else:
            raise TimeoutError("acquisition did not finish in the bounded window")
    prepare(source, state, args.hours)
    if args.response_cache:
        copied = {}
        for cache in args.response_cache:
            cache = cache.resolve()
            if not cache.is_relative_to(ROOT):
                raise ValueError("response cache outside project")
            copied[str(cache)] = reuse_recent_web_responses(
                cache, state / "acquisition/http-cache", datetime.now(UTC)
            )
        publish_status(
            state / "additional-response-evidence.json",
            dict(
                copied=copied, maximum_age_seconds=86400, original_observation_times_preserved=True
            ),
        )
    if not args.prepare_only:
        subprocess.run(
            [
                sys.executable,
                "scripts/compare_all_lyrics_web.py",
                "--state-root",
                str(state),
                "--base-root",
                str(ROOT / "data/derived/annual_revision/global-2018-2026-20261108"),
                "--store-root",
                str(ROOT / "data/derived/lyrics/global-20261108"),
                "--reuse-comparison-root",
                str(source),
                "--hours",
                str(args.hours),
            ],
            cwd=ROOT,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )


if __name__ == "__main__":
    main()
