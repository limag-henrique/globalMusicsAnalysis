"""Bind preserved IPF annual lists to calendar-year primary documentation.

The association between table report year and rule-defined exercise is an explicit
documentary inference. This builder does not certify research approval or promote
this national public-performance stratum into a streaming corpus.
"""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from chart_observatory.research_rankings import verify_published_annual


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf8"))


def jsonl(path, rows):
    path.write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf8"
    )


def build(source, evidence, parent, output):
    raw, documents = read(source / "manifest.json"), read(evidence / "manifest.json")
    for capture in raw["captures"]:
        if sha(source / capture["path"]) != capture["sha256"]:
            raise ValueError("raw IPF capture changed")
    for name, expected in documents["output_hashes"].items():
        if sha(evidence / name) != expected:
            raise ValueError("IPF period evidence changed")
    cells = [
        json.loads(x)
        for x in (parent / "country_years.jsonl").read_text(encoding="utf8").splitlines()
    ]
    quota_cells = {c["year"]: c for c in cells if c["country_code"] == "SI"}
    # The 2019 adopted rules apply from 2020 and retain 2017 rules through 2019.
    rule_for_year = {
        2018: "2017",
        2019: "2017",
        2020: "2020",
        2021: "2020",
        2022: "2021",
        2023: "2022",
        2024: "2023",
        2025: "2023",
    }
    observations, selected, checks, period_links = [], [], [], []
    for year, rule in rule_for_year.items():
        quota = quota_cells[year]["quota"]
        records = []
        for start in range(0, 500, 100):
            payload = read(source / f"{year}-{start}.json")
            if payload["recordsTotal"] != 500 or payload["recordsFiltered"] != 500:
                raise ValueError("IPF published depth changed")
            records.extend(payload["data"])
        if len(records) != 500 or any(r["year"] != year for r in records):
            raise ValueError("IPF year/row count mismatch")
        rows = [
            dict(
                country_code="SI",
                year=year,
                source_report_year=year,
                position=r["rank"],
                candidate_id=f"IPF:{year}:{r['id']}",
                source_native_id=r["id"],
                title=r["performance"],
                artist=r["performer"],
                phonogram_producer=r["phonogramProducer"],
                platform="NATIONAL_PUBLIC_PERFORMANCE",
                provider="IPF",
                metric_value=None,
                period_start=f"{year}-01-01",
                period_end=f"{year}-12-31",
                ranking_kind="published_annual",
                identity_status="chart_entry_pending_recording_review",
                scientifically_verified=False,
                period_status="documentary_inference_from_report_year_and_calendar_exercise_rules",
                source_period_evidence=dict(
                    document=f"rules-{rule}.pdf",
                    page=1,
                    article=2,
                    sha256=sha(evidence / f"rules-{rule}.pdf"),
                ),
                separate_stratum=True,
            )
            for r in records
        ]
        check = verify_published_annual(
            rows,
            country_code="SI",
            year=year,
            platform="NATIONAL_PUBLIC_PERFORMANCE",
            provider="IPF",
            quota=quota,
            expected_depth=500,
            period_start=f"{year}-01-01",
            period_end=f"{year}-12-31",
        )
        if not check["approved"]:
            raise ValueError(f"published annual verification failed: {year}: {check['reasons']}")
        if quota_cells[year]["selected_positions"] != 0:
            raise ValueError("IPF cells are not marginal to frozen parent")
        observations.extend(rows)
        selected.extend(r for r in rows if r["position"] <= quota)
        checks.append(
            {
                **check,
                "rows": [],
                "technical_structure_verified": True,
                "scientific_approval": False,
            }
        )
        period_links.append(
            dict(
                year=year,
                rule_document=f"rules-{rule}.pdf",
                article=2,
                page=1,
                start=f"{year}-01-01",
                end=f"{year}-12-31",
                linkage="inference_from_source_table_year_and_official_exercise_definition",
            )
        )
    output.mkdir(parents=True, exist_ok=False)
    jsonl(output / "observations.jsonl", observations)
    jsonl(output / "quota-candidates.jsonl", selected)
    (output / "verification.json").write_text(
        json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf8"
    )
    (output / "period-evidence.json").write_text(
        json.dumps(
            dict(
                statement="Article 2 defines the calendar year in all inspected IPF rule versions.",
                primary_context="The statistics page links report years to accounting exercises.",
                tables=period_links,
                inspection="AI visual reading of preserved PDF pages; not human adjudication.",
                limitations=[
                    "The chart page does not repeat the exact calendar dates next to each table.",
                    "Accounting definition supplies dates through documented source linkage.",
                    "National public-performance statistics differ from platform streams/views.",
                ],
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf8",
    )
    manifest = dict(
        version="ipf-calendar-documented-separate-stratum-v1",
        created_at=datetime.now(UTC).isoformat(),
        source=str(source.resolve()),
        source_manifest_sha256=sha(source / "manifest.json"),
        period_evidence=str(evidence.resolve()),
        period_evidence_manifest_sha256=sha(evidence / "manifest.json"),
        parent=str(parent.resolve()),
        parent_manifest_sha256=sha(parent / "manifest.json"),
        observations=len(observations),
        quota_candidates=len(selected),
        cells=len(checks),
        technically_verified_published_lists=len(checks),
        promoted_to_main_selection=0,
        scientific_approval=False,
        classification_ready=False,
        remaining_blockers=[
            "source_stratum_protocol_review",
            "documentary_period_linkage_review",
            "recording_identity_and_lyric_edition_review",
        ],
        implementation_hashes={
            str(Path(__file__).resolve()): sha(Path(__file__)),
            "src/chart_observatory/research_rankings.py": sha(
                Path(__file__).resolve().parents[1] / "src/chart_observatory/research_rankings.py"
            ),
        },
        output_hashes={p.name: sha(p) for p in output.iterdir()},
    )
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf8"
    )
    print(
        json.dumps(
            {
                key: manifest[key]
                for key in (
                    "observations",
                    "quota_candidates",
                    "cells",
                    "technically_verified_published_lists",
                    "promoted_to_main_selection",
                    "scientific_approval",
                )
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "evidence", "parent", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    build(args.source, args.evidence, args.parent, args.output)
