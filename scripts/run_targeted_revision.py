"""One resumable targeted revision: alternatives, text evidence audit and scoped recovery."""

import hashlib
import json
import msvcrt
import sqlite3
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, select

from chart_observatory.config import Settings
from chart_observatory.lyrics.identity_collisions import flag_shared_text_identities
from chart_observatory.lyrics.quota_discovery import audit_saved_result
from chart_observatory.lyrics.quota_staging import blobs, candidates, runs
from chart_observatory.lyrics.text_quality import prepare_lyric_derivative
from chart_observatory.quota_campaign import remaining_seconds, verify_frozen_inputs
from chart_observatory.runtime_status import publish_status

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/derived/annual_revision/reconciled-russia-2018-2026-20261031"
STATE = ROOT / "data/runtime/targeted-revision-20261103"
STORE = ROOT / "data/derived/lyrics/quota-20261030"
PYTHON = ROOT / ".venv/Scripts/python.exe"


def read(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def report(stage, **details):
    publish_status(
        STATE / "status.json",
        dict(
            stage=stage,
            updated_at=datetime.now(UTC).isoformat(),
            classification_ready=False,
            paid_calls=0,
            **details,
        ),
    )


def plan_missing(limit=500):
    coverage = read(STORE / "review-inventory/staging-coverage.json")
    scoped = coverage["missing_text_candidates"][:limit]
    with sqlite3.connect(
        f"file:{(STORE / 'acquisition.sqlite').as_posix()}?mode=ro", uri=True
    ) as conn:
        for row in scoped:
            current = conn.execute(
                "SELECT result FROM tasks WHERE identity=?", (row["candidate_id"],)
            ).fetchone()
            result = json.loads(current[0]) if current and current[0] else {}
            row["previous_source_errors"] = result.get("source_errors", [])
            row["prior_text_present"] = bool(result.get("text_sha256"))
    # A new text acquired since the consolidated coverage does not justify another request.
    scoped = [r for r in scoped if not r["prior_text_present"]]
    if not scoped:
        raise ValueError("targeted scope is empty; refresh coverage before another campaign")
    raw = "".join(json.dumps(r) + "\n" for r in scoped)
    (STATE / "candidate-ids.jsonl").write_bytes(raw.encode("utf-8"))
    publish_status(
        STATE / "missing-plan.json",
        dict(
            selected_candidates=len(scoped),
            ranked_by="memberships_then_best_position",
            affected_memberships=sum(r["selected_memberships"] for r in scoped),
            candidate_filter_sha256=hashlib.sha256(raw.encode()).hexdigest(),
            failed_source_signals=dict(
                Counter(e for r in scoped for e in r["previous_source_errors"])
            ),
            annual_position_changes=0,
            quota_changes=0,
        ),
    )


def audit_saved_texts():
    engine = create_engine(Settings.load(ROOT).database_url, connect_args={"connect_timeout": 5})
    counts = Counter()
    repair = []
    identity_records = []
    try:
        with engine.connect() as conn:
            run_id = conn.execute(
                select(runs.c.id).order_by(runs.c.created_at.desc(), runs.c.id).limit(1)
            ).scalar_one()
            query = select(
                candidates.c.candidate_id,
                candidates.c.payload,
                candidates.c.source_result,
                candidates.c.text_sha256,
                blobs.c.body,
            ).join(blobs, blobs.c.sha256 == candidates.c.text_sha256)
            query = query.where(candidates.c.run_id == run_id)
            with (STATE / "text-evidence-audit.jsonl").open("w", encoding="utf-8") as out:
                for row in conn.execution_options(stream_results=True).execute(query).mappings():
                    text_body = row["body"]
                    digest_ok = hashlib.sha256(text_body.encode()).hexdigest() == row["text_sha256"]
                    quality = prepare_lyric_derivative(
                        text_body, row["source_result"].get("source", "UNKNOWN")
                    )
                    audit = audit_saved_result(row["payload"], row["source_result"])
                    flags = sorted(set(audit["text_quality_flags"]) | set(quality.flags))
                    if not digest_ok:
                        flags.append("stored_text_hash_mismatch")
                    tier = (
                        "repair_required"
                        if flags or audit["source_quarantined"]
                        else "source_checks_passed_recording_and_completeness_unproven"
                    )
                    counts[tier] += 1
                    item = dict(
                        candidate_id=row["candidate_id"],
                        text_sha256=row["text_sha256"],
                        source=audit["source"],
                        hash_verified=digest_ok,
                        flags=flags,
                        source_quarantined=audit["source_quarantined"],
                        tier=tier,
                        identity_validated=False,
                        completeness_validated=False,
                        classification_ready=False,
                    )
                    out.write(json.dumps(item, ensure_ascii=False) + "\n")
                    identity_records.append(
                        dict(
                            candidate_id=row["candidate_id"],
                            text_sha256=row["text_sha256"],
                            payload=row["payload"],
                            audit=audit,
                        )
                    )
                    if tier == "repair_required":
                        repair.append(dict(candidate_id=row["candidate_id"], reasons=flags))
            collisions = flag_shared_text_identities(identity_records)
            publish_status(
                STATE / "shared-text-conflicts.json",
                dict(groups=collisions, automatic_resolution=False),
            )
            publish_status(
                STATE / "text-audit-summary.json",
                dict(
                    run_id=run_id,
                    counts=dict(counts),
                    checked=sum(counts.values()),
                    identity_validated=0,
                    completeness_validated=0,
                    classification_ready=0,
                    shared_text_identity_conflicts=len(collisions),
                ),
            )
            (STATE / "repair-candidates.jsonl").write_text(
                "".join(json.dumps(r) + "\n" for r in repair), encoding="utf-8"
            )
    finally:
        engine.dispose()


def alternative_sources():
    url = (
        "https://music.apple.com/in/playlist/top-100-songs-2018-india/"
        "pl.7df4aa48d58c4689bad274bfe7c54cce"
    )
    path = STATE / "apple-IN-2018.html"
    if not path.exists():
        response = httpx.get(url, timeout=25, follow_redirects=True)
        response.raise_for_status()
        path.write_bytes(response.content)
    raw = path.read_bytes()
    soup = BeautifulSoup(raw, "html.parser")
    schema = json.loads(soup.find("script", id="schema:music-playlist").string)
    if schema["name"] != "Top 100 Songs 2018: India":
        raise ValueError("alternative page country/year mismatch")
    observations = []
    for item in schema["track"]:
        native_url = item["url"]
        parsed = urlparse(native_url)
        if parsed.hostname != "music.apple.com" or not parsed.path.startswith("/in/song/"):
            raise ValueError("alternative song native ID outside source storefront")
        observations.append(
            dict(
                title=item["name"],
                native_url=native_url,
                native_id=parsed.path.rsplit("/", 1)[-1],
                duration=item.get("duration"),
                annual_position_verified=False,
            )
        )
    publish_status(
        STATE / "alternative-ranking-evidence.json",
        dict(
            country_code="IN",
            year=2018,
            quota=440,
            source_url=url,
            source_sha256=hashlib.sha256(raw).hexdigest(),
            published_at=schema.get("datePublished"),
            observed_tracks=len(observations),
            annual_memberships_added=0,
            blockers=[
                "depth_below_440",
                "published_before_calendar_year_end",
                "current_playlist_order_does_not_prove_historical_positions",
                "recording_credits_require_native_verification",
            ],
            candidates=observations,
            selection_status="DISCOVERY_QUARANTINE",
        ),
    )
    publish_status(
        STATE / "ranking-source-decisions.json",
        dict(
            sources=[
                dict(
                    country="IN",
                    year=2018,
                    provider="APPLE_MUSIC",
                    evidence="alternative-ranking-evidence.json",
                    decision="reference_only_not_full_annual_ranking",
                ),
                dict(
                    country="KR",
                    years=[2018, 2019, 2020],
                    provider="CIRCLE_CHART",
                    source_url="https://circlechart.kr/page_chart/onoff.circle?hitYear=2018&nationGbn=T&serviceGbn=ALL&termGbn=year&year_time=3",
                    decision="no_bulk_collection_unauthorized_TDM_prohibited_by_source",
                ),
                dict(
                    country="IL",
                    years=[2023, 2024],
                    provider="KWORB_DAILY_TOTALS",
                    decision="all_time_totals_rejected_as_annual_evidence",
                ),
            ]
        ),
    )


def main():
    STATE.mkdir(parents=True, exist_ok=True)
    if (STATE / "finished.json").exists() or (STATE / "safety-hold.json").exists():
        return
    with (STATE / "owner.lock").open("a+b") as lock:
        lock.write(b"0")
        lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return
        steps = [
            ("ranking_alternatives", alternative_sources),
            ("text_evidence_audit", audit_saved_texts),
            ("prioritized_missing_plan", plan_missing),
        ]
        commands = [
            (
                "offline_scoped_replay",
                [
                    "scripts/replay_cached_quota_lyrics.py",
                    "--base-root",
                    str(BASE),
                    "--state-root",
                    str(STATE / "offline-replay"),
                    "--candidate-ids-file",
                    str(STATE / "candidate-ids.jsonl"),
                ],
            ),
            (
                "network_scoped_recovery",
                [
                    "scripts/autonomous_lyrics.py",
                    "--base-root",
                    str(BASE),
                    "--state-root",
                    str(STATE / "acquisition"),
                    "--candidate-ids-file",
                    str(STATE / "candidate-ids.jsonl"),
                    "--rounds",
                    "1",
                    "--hours",
                    "2",
                    "--method-prefix",
                    "targeted-20261103-v1",
                ],
            ),
            ("coverage", ["scripts/report_quota_staging_coverage.py"]),
            ("scope_audit", ["scripts/audit_quota_analysis_scope.py"]),
        ]
        try:
            verify_frozen_inputs()
            for name, action in steps:
                done = STATE / f"{name}-done.json"
                if not done.exists():
                    report(name)
                    action()
                    publish_status(done, dict(returncode=0))
            for name, command in commands:
                done = STATE / f"{name}-done.json"
                if done.exists():
                    continue
                if remaining_seconds() is not None and remaining_seconds() <= 0:
                    report("time_budget_finished_pending_work", pending_step=name)
                    return
                report(name)
                with (STATE / f"{name}.log").open("ab") as log:
                    result = subprocess.run(
                        [str(PYTHON), "-u", *command],
                        cwd=ROOT,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                if result.returncode:
                    raise RuntimeError(
                        f"{name}: failed with exit {result.returncode}; inspect local log"
                    )
                publish_status(done, dict(returncode=0))
            report("finished_pending_scientific_review")
            publish_status(
                STATE / "finished.json",
                dict(completed_at=datetime.now(UTC).isoformat(), classification_ready=False),
            )
        except Exception as exc:
            report("attention_required", error_type=type(exc).__name__)
            publish_status(
                STATE / "safety-hold.json", dict(error_type=type(exc).__name__, error=str(exc))
            )
            raise


if __name__ == "__main__":
    main()
