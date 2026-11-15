"""Prioritize native metadata discrepancies without deciding musical identity."""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

from chart_observatory import research_flow as flow

VERSION = "native-metadata-review-queue-v1"


def _fold(value):
    return unicodedata.normalize("NFC", value or "").casefold().strip()


def discrepancy_kind(row):
    selected_title, actual_title = row.get("selected_title"), row.get("reconstructed_title")
    selected_artist, actual_artist = row.get("selected_artist"), row.get("reconstructed_artist")
    if not actual_title or not actual_artist:
        return "source_display_metadata_missing"
    if not selected_title or not selected_artist:
        return "selected_display_metadata_missing"
    if _fold(selected_title) == _fold(actual_title) and _fold(selected_artist) == _fold(
        actual_artist
    ):
        return "possible_case_or_unicode_representation_change"

    def separators(text):
        return "|".join(_fold(part) for part in re.split(r"\s*[,|]\s*", text))

    if _fold(selected_title) == _fold(actual_title) and separators(selected_artist) == separators(
        actual_artist
    ):
        return "possible_artist_separator_change"
    if selected_title != actual_title:
        return "title_or_version_discrepancy_requires_review"
    return "artist_credit_discrepancy_requires_review"


def build_queue(campaign, output):
    campaign, output = Path(campaign).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError("review output must be a new version directory")
    status_path = campaign / "status.json"
    status_hash = flow.file_hash(status_path)
    status = json.loads(status_path.read_text(encoding="utf-8"))
    records = {k: r for k, r in status["cells"].items() if r["state"] == "completed"}
    groups, reasons, numeric_conflicts = {}, Counter(), []
    hashes = {str(status_path): status_hash}
    for cell, record in sorted(records.items()):
        evidence = Path(record["evidence"]).resolve()
        manifest_path = evidence / "manifest.json"
        artifact_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        comparison = evidence / "selection-comparison.jsonl"
        if (
            flow.file_hash(comparison)
            != artifact_manifest["artifacts"]["selection-comparison.jsonl"]
        ):
            raise ValueError("comparison artifact changed")
        report_path = evidence / "report.json"
        if flow.file_hash(report_path) != record["report_sha256"]:
            raise ValueError("campaign evidence report changed")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if (
            report["selection_sha256"] != status["selection_sha256"]
            or report["scientific_approval"] is not False
        ):
            raise ValueError("comparison is from another selection or claims approval")
        for path in (manifest_path, comparison, report_path):
            hashes[str(path)] = flow.file_hash(path)
        for row in flow.rows(comparison):
            if not row["rank_match"] or not row["metric_match"]:
                numeric_conflicts.append({"cell": cell, **row, "scientific_approval": False})
            if row["metadata_match"]:
                continue
            identity = tuple(
                row.get(k)
                for k in (
                    "candidate_id",
                    "selected_title",
                    "selected_artist",
                    "reconstructed_title",
                    "reconstructed_artist",
                )
            )
            kind = discrepancy_kind(row)
            reasons[kind] += 1
            if identity not in groups:
                groups[identity] = {
                    "review_id": flow.object_hash(identity),
                    "kind": kind,
                    **{
                        k: row.get(k)
                        for k in (
                            "candidate_id",
                            "selected_title",
                            "selected_artist",
                            "reconstructed_title",
                            "reconstructed_artist",
                        )
                    },
                    "memberships": [],
                    "decision": None,
                    "reviewer": None,
                    "scientific_approval": False,
                }
            groups[identity]["memberships"].append(
                {
                    "country_code": row["country_code"],
                    "year": row["year"],
                    "position": row["position"],
                    "row_sha256": row["row_sha256"],
                    "comparison": str(comparison),
                    "evidence_manifest": str(manifest_path),
                }
            )
    if flow.file_hash(status_path) != status_hash:
        raise ValueError("campaign advanced while preparing review; retry from a stable checkpoint")
    for name, digest in hashes.items():
        if flow.file_hash(name) != digest:
            raise ValueError("review input changed")
    output.mkdir(parents=True, exist_ok=False)
    flow.write_rows(
        output / "metadata-review.jsonl",
        sorted(groups.values(), key=lambda r: (r["kind"], r["review_id"])),
    )
    flow.write_rows(output / "rank-metric-conflicts.jsonl", numeric_conflicts)
    report = {
        "version": VERSION,
        "selection_sha256": status["selection_sha256"],
        "campaign_state": status["state"],
        "processed_cells": len(records),
        "affected_memberships": sum(reasons.values()),
        "distinct_review_forms": len(groups),
        "discrepancy_kinds": dict(reasons),
        "rank_metric_conflicts": len(numeric_conflicts),
        "scientific_approval": False,
        "production_writes": 0,
        "warning": "String similarity is only review prioritization, never identity evidence.",
    }
    flow.write_json(output / "report.json", report)
    flow.write_json(
        output / "manifest.json",
        {
            "version": VERSION,
            "input_hashes": hashes,
            "producer_sha256": flow.file_hash(__file__),
            "artifacts": {p.name: flow.file_hash(p) for p in output.iterdir() if p.is_file()},
        },
    )
    return report
