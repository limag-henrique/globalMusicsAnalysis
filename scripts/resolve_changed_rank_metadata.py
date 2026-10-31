"""Resolve changed display names by the exact public Spotify track URI, without fuzzy aliases."""

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
from resolve_public_track_metadata import spotify_entity

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/raw/metadata_resolution/20261031"


def resolve(base):
    inventory = ROOT / "data/derived/lyrics/quota-20261030/review-inventory/candidates.jsonl"
    wanted = set()
    for line in inventory.open(encoding="utf-8"):
        row = json.loads(line)
        if row["candidate_id"].startswith("SPOTIFY:") and any(
            flag in row["review_flags"]
            for flag in (
                "stored_artist_requires_reconciliation",
                "stored_title_requires_reconciliation",
                "provider_performer_or_version_mismatch",
            )
        ):
            wanted.add(row["candidate_id"])
    path = base / "native-display-metadata.json"
    resolutions = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    failed = []
    with httpx.Client(timeout=20, follow_redirects=True) as client:
        for key in sorted(wanted):
            native = key.removeprefix("SPOTIFY:")
            evidence = CACHE / f"rank-change-{native}.json"
            if evidence.exists():
                proof = json.loads(evidence.read_text(encoding="utf-8"))
            else:
                url = f"https://open.spotify.com/embed/track/{native}"
                try:
                    response = client.get(url)
                    proof = dict(
                        source_url=url,
                        status=response.status_code,
                        body_sha256=hashlib.sha256(response.content).hexdigest(),
                        retrieved_at=datetime.now(UTC).isoformat(),
                        metadata=spotify_entity(response.text, native)
                        if response.status_code == 200
                        else None,
                    )
                except httpx.HTTPError as exc:
                    proof = dict(source_url=url, error_type=type(exc).__name__, metadata=None)
                evidence.write_text(
                    json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                time.sleep(0.5)
            if (
                proof.get("metadata", {})
                and proof["metadata"].get("uri") == f"spotify:track:{native}"
            ):
                resolutions[key] = dict(
                    evidence_file=str(evidence),
                    evidence_sha256=hashlib.sha256(evidence.read_bytes()).hexdigest(),
                )
            else:
                failed.append(key)
            if proof.get("status") in (401, 403, 429):
                break
    part = path.with_suffix(".part")
    part.write_text(json.dumps(resolutions, ensure_ascii=False, indent=2), encoding="utf-8")
    part.replace(path)
    return dict(
        requested=len(wanted),
        resolved=len(resolutions),
        failed=failed,
        session_tokens_saved=False,
        recording_and_lyrics_validated=False,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(resolve(args.base_root.resolve())))
