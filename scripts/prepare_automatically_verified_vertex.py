"""Prepare only automatically verified songs inside the global population quota."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from chart_observatory.automatic_preparation import POLICY, assess, materialize, register
from chart_observatory.config import Settings
from chart_observatory.final_pipeline import catalog, digest, encode, read_result, save
from chart_observatory.lyrics.research_contract import contract
from chart_observatory.research_flow import load_selection

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verification", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--materialize", action="store_true")
    args = parser.parse_args()
    config = json.loads((ROOT / "config/final_pipeline.json").read_text())
    if config.get("automatic_preparation_authorized") is not True:
        raise ValueError("automatic preparation has not been authorized")
    if not (args.verification / "report.json").is_file():
        raise ValueError("full cohort verification must finish before preparation")
    selection = ROOT / config["population_selection"]
    manifest, _, members, _ = load_selection(selection)
    if manifest["requested_positions"] > 150_000:
        raise ValueError("population selection exceeds global budget")
    allocation = json.loads((selection / "allocation-summary.json").read_text())
    country_order = {c: n for n, c in enumerate(allocation["priority_countries"])}
    by_song = defaultdict(list)
    for row in members:
        by_song[row["candidate_id"]].append(row)
    priority = {
        cid: min((country_order[r["country_code"]], r["position"], r["year"], cid) for r in rows)
        for cid, rows in by_song.items()
    }
    settings = Settings.load(ROOT)
    definition = contract()
    definition_hash = digest(encode(definition).encode())
    selection_hash = digest((selection / "manifest.json").read_bytes())
    out = args.output.resolve()
    if not out.is_relative_to(ROOT / "data/runtime"):
        raise ValueError("output must remain in runtime")
    out.mkdir(parents=True, exist_ok=False)
    save(out / "contract.json", definition)
    counts = Counter()
    country_stats = defaultdict(Counter)
    verification = sqlite3.connect(
        (args.verification / "verification.sqlite").resolve().as_uri() + "?mode=ro", uri=True
    )
    jobs_file = out / "jobs.private.jsonl"
    with (
        catalog(ROOT / "data/runtime/final-pipeline") as ledger,
        ledger,
        jobs_file.open("x", encoding="utf-8") as jobs,
        (out / "pending.jsonl").open("x", encoding="utf-8") as pending,
    ):
        for cid in sorted(by_song, key=priority.get):
            counts["selected_unique_songs"] += 1
            row = verification.execute(
                "SELECT result,verification FROM candidates WHERE id=?", (cid,)
            ).fetchone()
            if row is None:
                eligibility = dict(eligible=False, reasons=["not_verified"])
            else:
                result, decision = json.loads(row[0]), json.loads(row[1])
                eligibility = assess(decision)
            if not eligibility["eligible"]:
                counts["pending"] += 1
                pending.write(encode(dict(candidate_id=cid, eligibility=eligibility)) + "\n")
                continue
            _, text, _ = read_result(result, ROOT)
            sha = decision["text_sha256"]
            if text is None or digest(text.encode()) != sha:
                raise ValueError("verified transcription changed before preparation")
            request_id = digest(
                encode([POLICY, cid, sha, definition_hash, settings.gemini_model]).encode()
            )
            if not register(
                ledger,
                recording_id=cid,
                request_id=request_id,
                text_hash=sha,
                selection_hash=selection_hash,
            ):
                counts["blocked_by_global_cap"] += 1
                continue
            job = dict(
                candidate_id=cid,
                request_id=request_id,
                text_sha256=sha,
                source_reference=result,
                selection_sha256=selection_hash,
                verification_sha256=digest(row[1].encode()),
                configured_model=settings.gemini_model,
                configured_location=settings.google_cloud_location,
                contract_sha256=definition_hash,
                automatic_eligibility=eligibility,
                scientific_approval=False,
                paid_calls=0,
                memberships=[
                    dict(
                        country_code=r["country_code"],
                        year=r["year"],
                        position=r["position"],
                        platform=r["platform"],
                        selection_status=r.get("selection_status"),
                    )
                    for r in by_song[cid]
                ],
            )
            jobs.write(encode(job) + "\n")
            counts["ready_for_automatic_preparation"] += 1
            for membership in by_song[cid]:
                country_stats[membership["country_code"]][str(membership["year"])] += 1
                counts["ready_memberships"] += 1
    verification.close()
    with (out / "ready-by-country-year.csv").open("x", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["country", "year", "ready_positions"])
        for country in allocation["priority_countries"]:
            for year in manifest["years"]:
                writer.writerow([country, year, country_stats[country][str(year)]])
    report = dict(
        counts=counts,
        policy=POLICY,
        total_position_budget=150_000,
        automatic_preparation_authorized=True,
        scientific_approval=False,
        human_review_fabricated=False,
        source_texts_copied=False,
        model_revision_resolution_required_before_dispatch=True,
        paid_calls=0,
        uploads=0,
        completed_at=datetime.now(UTC).isoformat(),
        priority=(
            "country quota descending, population tie-break; position ascending, year ascending"
        ),
    )
    if args.materialize:
        report["materialized_requests"] = materialize(
            jobs_file, out / "vertex-requests.jsonl", ROOT
        )
    save(out / "report.json", report)
    print(encode(report), flush=True)


if __name__ == "__main__":
    main()
