"""Finish source checks and rebuild the local dossier after the current acquisition exits."""

import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from import_all_quota_lyrics import BASE, ROOT, run_job

from chart_observatory.runtime_status import publish_status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-root", required=True, type=Path)
    parser.add_argument("--preparation-root", required=True, type=Path)
    parser.add_argument("--web-comparison-root", type=Path)
    args = parser.parse_args()
    campaign, preparation = args.campaign_root.resolve(), args.preparation_root.resolve()
    if any(not p.is_relative_to(ROOT / "data/runtime") for p in (campaign, preparation)):
        parser.error("state must remain in project data/runtime")
    state = preparation / "finalization"
    state.mkdir(exist_ok=True)
    web = args.web_comparison_root.resolve() if args.web_comparison_root else None
    if web and not web.is_relative_to(ROOT / "data/runtime"):
        parser.error("web comparison must remain in project data/runtime")
    try:
        finalize(campaign, preparation, state, web)
    except Exception as error:
        publish_status(
            state / "status.json",
            dict(
                stage="failed",
                error_type=type(error).__name__,
                paid_calls=0,
                submission_ready=False,
            ),
        )
        raise


def finalize(campaign, preparation, state, web):
    config = json.loads((campaign / "campaign.json").read_text())
    deadline = datetime.fromisoformat(config["ends_at"]) + timedelta(hours=27 if web else 3)
    while datetime.now(UTC) < deadline:
        collection = json.loads((campaign / "status.json").read_text())
        audit = json.loads((preparation / "source-audit/status.json").read_text())
        web_status = (
            json.loads((web / "status.json").read_text()) if web else {"stage": "completed"}
        )
        if (
            collection.get("stage", "").startswith("finished")
            and audit.get("stage") == "completed"
            and web_status.get("stage") == "completed"
        ):
            break
        if audit.get("stage") == "failed" or web_status.get("stage") == "failed":
            raise RuntimeError("source audit failed; inspect its logs")
        publish_status(
            state / "status.json",
            dict(
                stage="waiting_for_collection_and_web_comparisons"
                if web
                else "waiting_for_collection_and_source_audit",
                pid=os.getpid(),
                paid_calls=0,
                updated_at=datetime.now(UTC).isoformat(),
            ),
        )
        time.sleep(15)
    else:
        raise TimeoutError("preparation deadline reached; do not declare readiness")
    # Load the current corrected recovery code in fresh child processes and reuse
    # responses obtained by the collector, without another network collector.
    replay = preparation / "final-offline-replay"
    proposals = replay / "proposals"
    jobs = [
        (
            [
                sys.executable,
                "scripts/replay_cached_quota_lyrics.py",
                "--base-root",
                str(BASE),
                "--state-root",
                str(replay),
                "--output-root",
                str(proposals),
                "--include-flagged",
            ],
            replay,
        ),
        (
            [
                sys.executable,
                "scripts/publish_source_checked_replays.py",
                "--proposals",
                str(proposals),
                "--report",
                str(replay / "publication-checks.json"),
            ],
            replay / "publication",
        ),
        (
            [
                sys.executable,
                "scripts/stage_quota_lyrics.py",
                "--base-root",
                str(BASE),
                "--state-root",
                str(preparation / "final-staging"),
            ],
            preparation / "final-staging",
        ),
        (
            [
                sys.executable,
                "scripts/audit_current_lyric_corpus.py",
                "--output",
                str(preparation / "final-quality-audit"),
            ],
            preparation / "final-quality-audit",
        ),
    ]
    for command, directory in jobs:
        if run_job(command, directory, dict(os.environ)):
            raise RuntimeError("final offline recovery or staging failed; inspect child logs")
    output = preparation / "final-source-audit"
    output.mkdir(exist_ok=True)
    if not (output / "checkpoint.sqlite").exists():
        with (
            sqlite3.connect(
                (preparation / "source-audit/checkpoint.sqlite").as_uri() + "?mode=ro", uri=True
            ) as src,
            sqlite3.connect(output / "checkpoint.sqlite") as dst,
        ):
            src.backup(dst)
    audit_code = run_job(
        [sys.executable, "scripts/verify_lyric_source_chains.py", "--output", str(output)],
        output,
        dict(os.environ),
    )
    if audit_code:
        raise RuntimeError("final source audit failed")
    code = run_job(
        [
            sys.executable,
            "scripts/prepare_vertex_readiness.py",
            "--output",
            str(preparation / "final-dossier"),
        ],
        state / "dossier",
        dict(os.environ),
    )
    if code:
        raise RuntimeError("final dossier preparation failed")
    readiness = json.loads((preparation / "final-dossier/readiness.json").read_text())
    publish_status(
        state / "status.json",
        dict(
            stage="prepared_with_documented_blockers",
            inventory=readiness["inventory"],
            submission_ready=readiness["submission_ready"],
            blockers=readiness["blockers"],
            paid_calls=0,
            uploads=0,
            finished_at=datetime.now(UTC).isoformat(),
        ),
    )


if __name__ == "__main__":
    main()
