"""Reproduce the worldwide research inventory offline; do not change operational selection."""

import csv
import hashlib
import json
from pathlib import Path

from chart_observatory.sources.global_inventory import build_inventory, geographic_universe

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/derived/annual_revision/reconciled-russia-2018-2026-20261031"
OUT = ROOT / "research/global_inventory"


def main():
    paths = {
        "iso": ROOT / "research/geography/iso_3166_20261108.json",
        "m49": ROOT / "research/geography/un_m49_20261108.json",
        "sources": OUT / "source_registry_20261108.json",
        "apple_evidence": OUT / "apple_country_chart_directory_20261108.json",
        "quotas": BASE / "sources/country_quotas.csv",
        "selection": BASE / "combined.jsonl",
    }
    raw = {key: path.read_bytes() for key, path in paths.items()}
    geo = geographic_universe(json.loads(raw["iso"])["rows"], json.loads(raw["m49"])["rows"])
    quotas = {
        r["country_code"]: int(r["quota_per_year_main"])
        for r in csv.DictReader(raw["quotas"].decode("utf-8-sig").splitlines())
    }
    result = build_inventory(
        geo,
        json.loads(raw["sources"])["sources"],
        quotas,
        [
            json.loads(line)
            for line in raw["selection"].decode("utf-8").splitlines()
            if line.strip()
        ],
    )
    OUT.mkdir(parents=True, exist_ok=True)
    for key in ("countries", "country_years"):
        (OUT / f"{key}_20261108.json").write_text(
            json.dumps(result[key], ensure_ascii=False, indent=2), encoding="utf-8"
        )
        with (OUT / f"{key}_20261108.tsv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(result[key][0]), delimiter="\t")
            writer.writeheader()
            for row in result[key]:
                writer.writerow(
                    {
                        k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                        for k, v in row.items()
                    }
                )
    manifest = dict(
        version="worldwide-music-inventory-v1",
        date="2026-11-08",
        years=[2018, 2026],
        existing_campaign_cutoff="2026-10-15",
        scope="Inventory expansion only; no operational quota or ranking changes",
        input_sha256={
            str(paths[key].relative_to(ROOT)): hashlib.sha256(value).hexdigest()
            for key, value in raw.items()
        },
        summary=result["summary"],
    )
    (OUT / "manifest_20261108.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result["summary"], ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
