"""Build an immutable separate-stratum supplement from preserved IPF responses."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(source, output, parent):
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf8"))
    for item in manifest["captures"]:
        if sha(source / item["path"]) != item["sha256"]:
            raise ValueError("raw source capture changed")
    cells = [
        json.loads(x)
        for x in (parent / "country_years.jsonl").read_text(encoding="utf8").splitlines()
    ]
    quotas = {c["year"]: c for c in cells if c["country_code"] == "SI"}
    observations, selected = [], []
    for year in range(2018, 2026):
        records = []
        for start in range(0, 500, 100):
            payload = json.loads((source / f"{year}-{start}.json").read_text(encoding="utf8"))
            if payload["recordsTotal"] != 500 or payload["recordsFiltered"] != 500:
                raise ValueError("source total differs")
            records.extend(payload["data"])
        if [r["rank"] for r in records] != list(range(1, 501)):
            raise ValueError("positions differ from complete published list")
        if len({r["id"] for r in records}) != 500 or any(r["year"] != year for r in records):
            raise ValueError("source ID/year mismatch")
        for r in records:
            if any(
                not isinstance(r[k], str) or not r[k].strip() for k in ("performance", "performer")
            ):
                raise ValueError("source identity missing")
            row = dict(
                country_code="SI",
                year=year,
                source_report_year=year,
                position=r["rank"],
                title=r["performance"],
                artist=r["performer"],
                candidate_id=f"IPF:{year}:{r['id']}",
                source_native_id=r["id"],
                platform="NATIONAL_PUBLIC_PERFORMANCE",
                provider="IPF",
                phonogram_producer=r["phonogramProducer"],
                metric_value=None,
                period_start=None,
                period_end=None,
                period_status="source_year_only_bounds_unconfirmed",
                identity_status="chart_entry_pending_recording_review",
                scientifically_verified=False,
                separate_stratum=True,
            )
            observations.append(row)
            if row["position"] <= quotas[year]["quota"]:
                if quotas[year]["selected_positions"] != 0:
                    raise ValueError("supplement is not marginal to frozen parent")
                selected.append(row)
    output.mkdir(parents=True, exist_ok=False)
    for name, rows in [("observations.jsonl", observations), ("quota-candidates.jsonl", selected)]:
        (output / name).write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf8"
        )
    packages = ["requests", "beautifulsoup4", "pypdf", "pdfplumber", "pypdfium2", "pdfminer.six"]
    (output / "requirements-extraction.txt").write_text(
        "\n".join(f"{p}=={version(p)}" for p in packages) + "\n", encoding="utf8"
    )
    result = dict(
        version="ipf-annual-separate-stratum-v1",
        created_at=datetime.now(UTC).isoformat(),
        source=str(source),
        parent=str(parent),
        parent_sha256=sha(parent / "manifest.json"),
        input_manifest_sha256=sha(source / "manifest.json"),
        raw_capture_hashes={r["path"]: r["sha256"] for r in manifest["captures"]},
        rows=len(observations),
        recovered_quota_positions=len(selected),
        newly_observed_cells=8,
        raw_marginal_positions=880,
        promoted_to_main_selection=0,
        scientific_approval=False,
        source_metric="published_public_performance_statistics_not_stream_counts",
        period_bounds=None,
        source_report_years=list(range(2018, 2026)),
        blockers=[
            "source_period_bounds_unconfirmed",
            "source_population_methodology_review",
            "chart_entry_recording_identity_review",
            "separate_stratum_not_main_corpus",
        ],
        supersedes_inferred_period_fields_in_raw_extractor_observations=True,
        implementation_hashes={str(Path(__file__)): sha(Path(__file__))},
        output_hashes={p.name: sha(p) for p in output.iterdir()},
    )
    (output / "manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf8"
    )
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "rows",
                    "recovered_quota_positions",
                    "newly_observed_cells",
                    "promoted_to_main_selection",
                    "scientific_approval",
                )
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--parent", type=Path, required=True)
    args = parser.parse_args()
    build(args.source, args.output, args.parent)
