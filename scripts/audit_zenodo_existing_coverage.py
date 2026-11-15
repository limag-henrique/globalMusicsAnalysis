"""Recheck a frozen Zenodo archive against published checksums and current selection.

This audit never adds existing source positions to coverage a second time.
It binds a newly obtained repository metadata response to immutable local files.
"""

import argparse
import csv
import gzip
import hashlib
import json
import urllib.request
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path


def digest(path, algorithm):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, algorithm).hexdigest()


def audit(source, selection, output):
    output.mkdir(parents=True, exist_ok=False)
    url = "https://zenodo.org/api/records/23645386"
    with urllib.request.urlopen(url, timeout=40) as response:
        metadata_bytes = response.read()
    (output / "record-current.json").write_bytes(metadata_bytes)
    metadata = json.loads(metadata_bytes)
    published = {item["key"]: item for item in metadata["files"]}
    parent = json.loads((selection / "manifest.json").read_text(encoding="utf8"))
    frozen_hashes = parent["source_hashes"]
    receipts, summaries = [], []
    for year in range(2018, 2027):
        filename = f"youtube_top100_positions_{year}.csv.gz"
        path, item = source / filename, published[filename]
        md5, sha256 = digest(path, "md5"), digest(path, "sha256")
        expected = item["checksum"].removeprefix("md5:")
        if md5 != expected or path.stat().st_size != item["size"]:
            raise ValueError(f"published checksum/size mismatch: {filename}")
        references = [
            key
            for key, value in frozen_hashes.items()
            if key.replace("\\", "/").endswith("/" + filename) and value == sha256
        ]
        if not references:
            raise ValueError(f"source not hash-bound to frozen selection: {filename}")
        receipts.append(
            dict(
                file=filename,
                md5=md5,
                sha256=sha256,
                bytes=path.stat().st_size,
                selection_references=references,
            )
        )
        cells = defaultdict(
            lambda: dict(
                periods=set(),
                rows=0,
                keys=Counter(),
                positions=Counter(),
                invalid_keys=0,
                missing_metadata=0,
            )
        )
        with gzip.open(path, "rt", encoding="utf8", newline="") as stream:
            for row in csv.DictReader(stream):
                country, period = row["cc"].upper(), row["week_end"]
                cell = cells[country]
                cell["periods"].add(period)
                cell["rows"] += 1
                cell["keys"][(period, row["key"])] += 1
                cell["positions"][(period, row["rank"])] += 1
                cell["invalid_keys"] += row["key"] in ("", "T:")
                cell["missing_metadata"] += not row["title"].strip() or not row["artists"].strip()
        stop, day, expected_periods = (
            min(date(year, 12, 31), date(2026, 10, 15)),
            date(year, 1, 1),
            set(),
        )
        while day <= stop:
            if day.weekday() == 3:
                expected_periods.add(day.isoformat())
            day += timedelta(days=1)
        for country, cell in sorted(cells.items()):
            summaries.append(
                dict(
                    country_code=country,
                    year=year,
                    rows=cell["rows"],
                    observed_periods=len(cell["periods"]),
                    expected_periods=len(expected_periods),
                    missing_period_ends=sorted(expected_periods - cell["periods"]),
                    unexpected_period_ends=sorted(cell["periods"] - expected_periods),
                    repeated_candidate_period_keys=sum(
                        n - 1 for n in cell["keys"].values() if n > 1
                    ),
                    repeated_source_positions=sum(
                        n - 1 for n in cell["positions"].values() if n > 1
                    ),
                    invalid_native_keys=cell["invalid_keys"],
                    missing_metadata=cell["missing_metadata"],
                )
            )
    (output / "country-year-source-audit.json").write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2) + "\n", encoding="utf8"
    )
    receipt = dict(
        version="zenodo-existing-coverage-audit-v1",
        obtained_at=datetime.now(UTC).isoformat(),
        repository_metadata_url=url,
        doi=metadata["doi"],
        source=str(source.resolve()),
        selection=str(selection.resolve()),
        parent_manifest_sha256=digest(selection / "manifest.json", "sha256"),
        files=receipts,
        inspected_rows=sum(x["rows"] for x in summaries),
        national_rows=sum(x["rows"] for x in summaries if x["country_code"] != "GLOBAL"),
        country_year_cells=len([x for x in summaries if x["country_code"] != "GLOBAL"]),
        source_already_used=True,
        newly_recovered_positions=0,
        promoted_positions=0,
        scientific_approval=False,
        reason=(
            "All nine source files already have identical SHA-256 "
            "in frozen selection source_hashes."
        ),
        implementation_sha256=digest(Path(__file__), "sha256"),
        output_hashes={p.name: digest(p, "sha256") for p in output.iterdir() if p.is_file()},
    )
    (output / "manifest.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf8"
    )
    print(
        json.dumps(
            {
                key: receipt[key]
                for key in (
                    "inspected_rows",
                    "national_rows",
                    "country_year_cells",
                    "source_already_used",
                    "newly_recovered_positions",
                )
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit(args.source, args.selection, args.output)
