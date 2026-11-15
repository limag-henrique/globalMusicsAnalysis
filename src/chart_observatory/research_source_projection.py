"""Project native MGD files into independent G1 evidence without approving research."""

from __future__ import annotations

import csv
import json
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from chart_observatory import research_flow as flow
from chart_observatory import research_rankings
from chart_observatory.research_rankings import reconstruct_chart_sum

VERSION = "mgd-native-reconstruction-v1"


def _integer(raw, *, grouped=False):
    value = str(raw or "").strip()
    if re.fullmatch(r"\d+", value) or (grouped and re.fullmatch(r"\d{1,3}(?:,\d{3})+", value)):
        return int(value.replace(",", ""))
    return None


def project_mgd_cell(
    *, project, selection, raw_source, output, country, year, source_manifest=None
):
    project, output, raw_source = (Path(p).resolve() for p in (project, output, raw_source))
    if output.exists():
        raise ValueError("use a new reconstruction output directory")
    if not output.is_relative_to(project):
        raise ValueError("reconstruction evidence must remain inside project")
    if not raw_source.is_relative_to(project):
        raise ValueError("native source must remain inside project for traceable evidence")
    country = country.upper()
    manifest, cells, selected, selection_inputs = flow.load_selection(selection)
    cell = next((r for r in cells if (r["country_code"], r["year"]) == (country, year)), None)
    if cell is None or cell["quota"] is None:
        raise ValueError("country/year quota is not defined in frozen selection")
    members = [r for r in selected if (r["country_code"], r["year"]) == (country, year)]
    if not members or any((r["provider"], r["platform"]) != ("MGD", "SPOTIFY") for r in members):
        raise ValueError("selected primary source for this cell is not MGD Spotify")
    source_manifest = Path(
        source_manifest or project / "research/mgd_source_manifest.json"
    ).resolve()
    inventory = json.loads(source_manifest.read_text(encoding="utf-8-sig"))
    source_entry = next(
        (r for r in inventory["files"] if (project / r["path"]).resolve() == raw_source), None
    )
    actual_hash = flow.file_hash(raw_source)
    if source_entry is None or actual_hash != source_entry.get("sha256"):
        raise ValueError("native file does not match frozen MGD source inventory")
    if source_entry.get("provider") != "MGD" or source_entry.get("origin_platform") != "SPOTIFY":
        raise ValueError("source inventory identifies a different provider/platform")
    inputs = {
        **selection_inputs,
        str(raw_source): actual_hash,
        str(source_manifest): flow.file_hash(source_manifest),
        str(Path(__file__).resolve()): flow.file_hash(__file__),
        str(Path(flow.__file__).resolve()): flow.file_hash(flow.__file__),
        str(Path(research_rankings.__file__).resolve()): flow.file_hash(research_rankings.__file__),
    }
    start = date(year, 1, 1)
    end = min(date(year, 12, 31), date.fromisoformat(manifest["cutoff"]))
    observations, invalid_dates = [], []
    with raw_source.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        required = {"ID", "Track", "Artist", "Position", "Streams", "Date", "Chart", "market"}
        if not required <= set(reader.fieldnames or ()):
            raise ValueError("MGD native columns are missing")
        for line, row in enumerate(reader, 2):
            if str(row.get("market", "")).upper() != country or row.get("Chart") != "Top 200":
                continue
            try:
                period = date.fromisoformat(row["Date"])
            except (ValueError, TypeError):
                invalid_dates.append({"source_row_number": line, "reason": "invalid_date"})
                continue
            if not start <= period <= end:
                continue
            native = row.get("ID", "")
            candidate = "SPOTIFY:" + native if re.fullmatch(r"[A-Za-z0-9]{22}", native) else None
            observations.append(
                {
                    "country_code": country,
                    "provider": "MGD",
                    "platform": "SPOTIFY",
                    "period_start": period.isoformat(),
                    "period_end": period.isoformat(),
                    "candidate_id": candidate,
                    "position": _integer(row.get("Position")),
                    "metric_value": _integer(row.get("Streams"), grouped=True),
                    "title": row.get("Track"),
                    "artist": row.get("Artist"),
                    "source_artifact": str(raw_source.relative_to(project)),
                    "source_row_number": line,
                }
            )
    reconstruction = reconstruct_chart_sum(
        observations,
        country_code=country,
        year=year,
        platform="SPOTIFY",
        provider="MGD",
        quota=cell["quota"],
        expected_depth=200,
        frequency="daily",
        cutoff=manifest["cutoff"],
    )
    by_id = {r["candidate_id"]: r for r in reconstruction["rows"]}
    comparisons = []
    for row in members:
        actual = by_id.get(row["candidate_id"])
        rank_match = bool(
            actual and actual["position"] == row["position"] and not actual["tie_group"]
        )
        metric_match = bool(
            actual and Decimal(str(actual["metric_value"])) == Decimal(str(row["metric_value"]))
        )
        metadata_match = bool(actual and all(actual[k] == row.get(k) for k in ("title", "artist")))
        comparisons.append(
            {
                "country_code": country,
                "year": year,
                "position": row["position"],
                "candidate_id": row["candidate_id"],
                "row_sha256": flow.object_hash(row),
                "rank_match": rank_match,
                "metric_match": metric_match,
                "metadata_match": metadata_match,
                "selected_title": row.get("title"),
                "selected_artist": row.get("artist"),
                "reconstructed_title": actual["title"] if actual else None,
                "reconstructed_artist": actual["artist"] if actual else None,
            }
        )
    for path, digest in inputs.items():
        if flow.file_hash(path) != digest:
            raise ValueError("input changed during native reconstruction")
    output.mkdir(parents=True, exist_ok=False)
    flow.write_rows(output / "observations.jsonl", observations)
    flow.write_rows(output / "invalid-source-rows.jsonl", invalid_dates)
    flow.write_json(output / "reconstruction.json", reconstruction)
    flow.write_rows(output / "selection-comparison.jsonl", comparisons)
    flow.write_csv(output / "selection-comparison.csv", comparisons, list(comparisons[0]))
    observation_ref = {
        "path": str((output / "observations.jsonl").relative_to(project)),
        "sha256": flow.file_hash(output / "observations.jsonl"),
    }
    flow.write_json(
        output / "source-definition.draft.json",
        {
            "country_code": country,
            "platform": "SPOTIFY",
            "provider": "MGD",
            "frequency": "daily",
            "metric": "streams_observed_in_top200",
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "depth": 200,
            "quota": cell["quota"],
            "observation_artifact": observation_ref,
            "source_url": None,
            "retrieved_at": None,
            "ranking_kind": "observed_chart_sum",
            "calendar_verified": False,
            "depth_verified": False,
            "identity_verified": False,
            "boundary_tie_resolved": False,
            "status": "draft_requires_source_and_scientific_review",
        },
    )
    report = {
        "version": VERSION,
        "country_code": country,
        "year": year,
        "selection_sha256": inputs[str(Path(selection).resolve() / "manifest.json")],
        "source_sha256": actual_hash,
        "observations": len(observations),
        "invalid_dates": len(invalid_dates),
        "selected_positions": len(members),
        "reconstruction_approved": reconstruction["approved"] and not invalid_dates,
        "missing_display_metadata_observations": reconstruction["counts"][
            "missing_display_metadata_observations"
        ],
        "rank_and_metric_matches": sum(r["rank_match"] and r["metric_match"] for r in comparisons),
        "metadata_exact_matches": sum(r["metadata_match"] for r in comparisons),
        "all_fields_match": sum(
            r["rank_match"] and r["metric_match"] and r["metadata_match"] for r in comparisons
        ),
        "scientific_approval": False,
        "paid_calls": 0,
        "production_writes": 0,
        "blockers": ["independent_source_definition_and_identity_review_required"],
        "reconstruction_reasons": reconstruction["reasons"],
        "input_hashes": inputs,
    }
    flow.write_json(output / "report.json", report)
    flow.write_json(
        output / "manifest.json",
        {
            "version": VERSION,
            "input_hashes": inputs,
            "artifacts": {p.name: flow.file_hash(p) for p in output.iterdir() if p.is_file()},
        },
    )
    return report
