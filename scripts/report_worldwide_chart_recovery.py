"""Freeze a recovery checkpoint and report exact annual calendar deficits, without DB writes."""

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from chart_observatory.research_chart_recovery import validate_capture
from chart_observatory.research_flow import file_hash, write_json, write_rows


def build(state, output):
    state, output = Path(state).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError("use a new checkpoint report directory")
    campaign = json.loads((state / "campaign.json").read_text(encoding="utf-8"))
    checkpoint_raw = (state / "checkpoint.json").read_bytes()
    checkpoint = json.loads(checkpoint_raw)
    captures, hashes, capture_hash_by_key = {}, {}, {}
    for key, value in checkpoint.items():
        if value["status"] != "captured_discovery":
            continue
        path = (state / value["capture"]).resolve()
        if not path.is_relative_to(state / "captures") or file_hash(path) != value["sha256"]:
            raise ValueError("capture missing, changed or outside campaign")
        doc = validate_capture(json.loads(path.read_text(encoding="utf-8")))
        if key != f"{doc['country_code']}/{doc['period_end']}":
            raise ValueError("checkpoint and actual capture market/calendar differ")
        captures[key] = doc
        hashes[str(path)] = value["sha256"]
        capture_hash_by_key[key] = value["sha256"]
    reports, candidates = [], []
    for task in campaign["tasks"]:
        country, year = task["country_code"], task["year"]
        expected = [f"{country}/{end}" for end in task["expected_period_ends"]]
        found = [captures[key] for key in expected if key in captures]
        missing = [key for key in expected if key not in captures]
        metadata_missing = sum(len(doc["missing_display_positions"]) for doc in found)
        metadata_conflicts = sum(len(doc["display_metadata_conflict_positions"]) for doc in found)
        ambiguous = sum(
            any(
                n > 1
                for n in Counter(
                    (
                        row["title"],
                        row["artist"],
                        tuple(
                            sorted(
                                {
                                    a["id"]
                                    for a in row.get("native_artist_ids", [])
                                    if a.get("id")
                                }
                            )
                        ),
                    )
                    for row in doc["rows"]
                ).values()
            )
            for doc in found
        )
        report = {
            "country_code": country,
            "year": year,
            "quota": task["quota"],
            "expected_weeks": len(expected),
            "captured_weeks": len(found),
            "calendar_complete": not missing,
            "missing_weeks": missing,
            "weekly_positions": sum(len(doc["rows"]) for doc in found),
            "missing_display_positions": metadata_missing,
            "rendered_native_metadata_conflicts": metadata_conflicts,
            "ambiguous_display_weeks": ambiguous,
            "annual_positions_added": 0,
            "scientific_approval": False,
            "recording_identity_verified": False,
            "classification_ready": False,
            "blockers": [],
        }
        if missing:
            report["blockers"].append("incomplete_weekly_calendar")
        if metadata_missing:
            report["blockers"].append("missing_source_identity_metadata")
        if metadata_conflicts:
            report["blockers"].append("rendered_native_metadata_conflicts")
        if ambiguous:
            report["blockers"].append("ambiguous_display_identity_within_week")
        report["blockers"].append("native_item_identity_and_protocol_review_required")
        if not missing and not metadata_missing and not ambiguous:
            totals = defaultdict(int)
            representative_videos = defaultdict(set)
            observations = defaultdict(list)
            group_metadata_conflicts = defaultdict(bool)
            for doc in found:
                week_key = f"{doc['country_code']}/{doc['period_end']}"
                for row in doc["rows"]:
                    artist_ids = tuple(
                        sorted({a["id"] for a in row.get("native_artist_ids", []) if a.get("id")})
                    )
                    key = row["title"], row["artist"], artist_ids
                    totals[key] += row["metric_value"]
                    observations[key].append(
                        {
                            "week_end": doc["period_end"],
                            "rank": row["rank"],
                            "weekly_views": row["metric_value"],
                            "capture_sha256": capture_hash_by_key[week_key],
                        }
                    )
                    group_metadata_conflicts[key] |= bool(row.get("display_metadata_conflict"))
                    if row.get("representative_video_id"):
                        representative_videos[key].add(row["representative_video_id"])
            ordered = sorted(totals.items(), key=lambda item: (-item[1], item[0]))
            for position, ((title, artist, artist_ids), metric) in enumerate(
                ordered[: task["quota"]], 1
            ):
                candidates.append(
                    {
                        "country_code": country,
                        "year": year,
                        "provisional_display_position": position,
                        "title": title,
                        "artist": artist,
                        "native_artist_ids": list(artist_ids),
                        "representative_video_ids": sorted(
                            representative_videos[(title, artist, artist_ids)]
                        ),
                        "weekly_evidence": observations[(title, artist, artist_ids)],
                        "observed_weekly_views": metric,
                        "native_id": None,
                        "identity_basis": (
                            "native_display_metadata_plus_artist_entity_ids"
                            if artist_ids
                            else "exact_display_strings_only_not_confirmed_recording"
                        ),
                        "recording_identity_validated": False,
                        "source_metadata_review_required": group_metadata_conflicts[
                            (title, artist, artist_ids)
                        ],
                        "annual_rank_certified": False,
                        "classification_ready": False,
                    }
                )
        reports.append(report)
    summary = {
        "version": "worldwide-chart-recovery-report-v1",
        "observed_at": datetime.now(UTC).isoformat(),
        "selection_sha256": campaign["selection_sha256"],
        "checkpoint_sha256": hashlib.sha256(checkpoint_raw).hexdigest(),
        "source_tasks": len(reports),
        "captured_weekly_charts": len(captures),
        "captured_weekly_positions": sum(len(d["rows"]) for d in captures.values()),
        "complete_calendar_cells": sum(r["calendar_complete"] for r in reports),
        "provisional_display_candidates": len(candidates),
        "annual_positions_added": 0,
        "scientific_approval": False,
        "unknown_other_source_tasks": len(campaign["other_source_tasks"]),
        "paid_calls": 0,
        "production_writes": 0,
        "capture_hashes": hashes,
    }
    output.mkdir(parents=True)
    (output / "checkpoint.snapshot.json").write_bytes(checkpoint_raw)
    write_json(output / "summary.json", summary)
    write_rows(output / "annual-calendars.jsonl", reports)
    write_rows(output / "provisional-display-candidates.jsonl", candidates)
    write_json(
        output / "manifest.json",
        {
            "version": summary["version"],
            "source_campaign_sha256": file_hash(state / "campaign.json"),
            "capture_hashes": hashes,
            "artifacts": {p.name: file_hash(p) for p in output.iterdir() if p.is_file()},
        },
    )
    return {key: value for key, value in summary.items() if key != "capture_hashes"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.state, args.output), ensure_ascii=False))
