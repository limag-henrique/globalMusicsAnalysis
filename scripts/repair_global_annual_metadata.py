"""Repair absent new-market titles using exact-ID public historical chart pages."""

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from chart_observatory.ingestion.archive_metadata import archive_proof

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/derived/annual_revision/global-2018-2026-20261108"
CACHE = ROOT / "data/raw/metadata_resolution/global-20261108/kworb"


def main(include_legacy_missing=False):
    CACHE.mkdir(parents=True, exist_ok=True)
    countries = json.loads((BASE / "countries.json").read_text(encoding="utf-8"))
    new = {c["country_code"] for c in countries if not c["legacy_frozen"]}
    rows = [
        json.loads(line)
        for line in (BASE / "combined.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    wanted = sorted(
        {
            r["candidate_id"]
            for r in rows
            if (include_legacy_missing or r["country_code"] in new)
            and (not r.get("title") or not r.get("artist"))
        }
    )
    refs_path = BASE / "archive-display-metadata.json"
    refs = json.loads(refs_path.read_text(encoding="utf-8")) if refs_path.exists() else {}
    failures = []
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for key in wanted:
            try:
                if key not in refs:
                    native = key.removeprefix("SPOTIFY:")
                    url = f"https://kworb.net/spotify/track/{native}.html"
                    response = client.get(url)
                    response.raise_for_status()
                    digest = hashlib.sha256(response.content).hexdigest()
                    path = CACHE / f"{native}-{digest}.html"
                    if not path.exists():
                        path.write_bytes(response.content)
                    refs[key] = dict(
                        native_id=native,
                        source_url=url,
                        response_url=str(response.url),
                        http_status=response.status_code,
                        evidence_file=str(path),
                        evidence_sha256=digest,
                        retrieved_at=datetime.now(UTC).isoformat(),
                    )
                    time.sleep(1.1)
                metadata = archive_proof(key, refs[key])
                print(
                    json.dumps(
                        dict(candidate_id=key, status="verified", **metadata), ensure_ascii=True
                    ),
                    flush=True,
                )
            except (ValueError, OSError, httpx.HTTPError) as exc:
                failures.append(dict(candidate_id=key, error=str(exc)))
                refs.pop(key, None)
            refs_path.write_text(
                json.dumps(refs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
    (BASE / "metadata_repair_collection.json").write_text(
        json.dumps(
            dict(
                wanted=len(wanted),
                verified=len(set(wanted) & refs.keys()),
                failures=failures,
                paid_calls=0,
                recording_identity_adjudicated=False,
            ),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-legacy-missing", action="store_true",
                        help="Repair missing names in the new version of legacy memberships")
    main(include_legacy_missing=parser.parse_args().include_legacy_missing)
