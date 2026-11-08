"""Resolve missing new-market titles with exact public Spotify URI proofs only."""

import json
from pathlib import Path

import collect_native_spotify_metadata as collector

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/derived/annual_revision/global-2018-2026-20261108"


def main():
    countries = json.loads((BASE / "countries.json").read_text(encoding="utf-8"))
    new = {c["country_code"] for c in countries if not c["legacy_frozen"]}
    rows = [
        json.loads(line)
        for line in (BASE / "combined.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    wanted = {
        r["candidate_id"]
        for r in rows
        if r["country_code"] in new
        and r["candidate_id"].startswith("SPOTIFY:")
        and (not r.get("title") or not r.get("artist"))
    }
    collector.CACHE = ROOT / "data/raw/metadata_resolution/global-20261108"
    collector.STATE = ROOT / "data/runtime/global-annual-metadata-20261108"
    collector.CACHE.mkdir(parents=True, exist_ok=True)
    collector.STATE.mkdir(parents=True, exist_ok=True)
    if wanted:
        collector.run(BASE, hours=0.04, candidate_ids=wanted)
    print(json.dumps(dict(requested_candidates=len(wanted), paid_calls=0)))


if __name__ == "__main__":
    main()
