"""Read preserved Spotify song dictionaries; write immutable native-ID evidence only."""

import argparse
import gzip
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

from chart_observatory.ingestion.artist_identity_evidence import (
    compile_artist_evidence,
    parse_artist_dictionary,
)

ROOT = Path(__file__).resolve().parents[1]


def immutable_write(path, raw):
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError("existing evidence differs; choose a new output directory")
        return
    part = path.with_suffix(".part")
    part.write_bytes(raw)
    part.replace(path)


def main(base, source, output):
    combined = (base / "combined.jsonl").read_bytes()
    rows = [json.loads(line) for line in combined.decode("utf-8").splitlines() if line]
    selected_manifest = json.loads((base / "combined-manifest.json").read_text(encoding="utf-8"))
    if len(rows) != sum(
        selected_manifest[k] for k in ("definitive_memberships", "provisional_memberships")
    ):
        raise ValueError("selection read is incomplete")
    wanted = {
        row["candidate_id"].split(":", 1)[1]
        for row in rows
        if row["candidate_id"].startswith("SPOTIFY:")
    }
    if any(not re.fullmatch(r"[A-Za-z0-9]{22}", native) for native in wanted):
        raise ValueError("invalid selected native track identifier")
    observations, archives, members = [], {}, []
    seen_members = set()
    paths = sorted(source.glob("raw_spotify_packages_part*.zip"))
    if not paths:
        raise FileNotFoundError("preserved Spotify packages not found")
    for path in paths:
        with path.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        expected = path.with_suffix(path.suffix + ".sha256").read_text().split()[0].lower()
        if digest != expected:
            raise ValueError("source archive hash mismatch")
        archives[path.name] = digest
        with zipfile.ZipFile(path) as archive:
            for member in archive.namelist():
                match = re.fullmatch(
                    r"raw_spotify_packages/spotify_([a-z]{2}|global)_2018_2026\.txt\.gz", member
                )
                if not match:
                    continue
                if member in seen_members:
                    raise ValueError("duplicate source member across archive parts")
                seen_members.add(member)
                with archive.open(member) as zipped, gzip.GzipFile(fileobj=zipped) as compressed:
                    records, stats = parse_artist_dictionary(
                        io.TextIOWrapper(compressed, encoding="utf-8"), match[1], wanted
                    )
                provenance = dict(
                    archive=path.name,
                    archive_sha256=digest,
                    member=member,
                    country_code=match[1].upper(),
                )
                observations.extend({**row, "source": provenance} for row in records)
                members.append({**provenance, **stats})
    tracks, artists = compile_artist_evidence(observations)
    output.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for name, data in (("track-artists.jsonl", tracks), ("artist-names.jsonl", artists)):
        raw = "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in data
        ).encode()
        immutable_write(output / name, raw)
        hashes[name] = hashlib.sha256(raw).hexdigest()
    manifest = dict(
        schema_version=1,
        source_archives=archives,
        source_members=members,
        selection_input_sha256=hashlib.sha256(combined).hexdigest(),
        selected_spotify_candidates=len(wanted),
        matched_candidates=len(tracks),
        missing_candidates=len(wanted) - len(tracks),
        artists=len(artists),
        artists_with_multiple_observed_names=sum(len(a["observed_names"]) > 1 for a in artists),
        conflicting_track_artist_sets=sum(
            t["status"] == "CONFLICTING_NATIVE_ARTIST_IDS" for t in tracks
        ),
        output_hashes=hashes,
        automatic_alias_matching_enabled=False,
        recording_validated=False,
        lyrics_validated=False,
        paid_calls=0,
    )
    immutable_write(
        output / "manifest.json", json.dumps(manifest, indent=2, sort_keys=True).encode()
    )
    print(
        json.dumps(
            {
                key: value
                for key, value in manifest.items()
                if key not in ["source_members", "source_archives", "output_hashes"]
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-root",
        type=Path,
        default=ROOT / "data/derived/annual_revision/reconciled-russia-2018-2026-20261031",
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=ROOT / "data/raw/historical_backfill/20261030/zenodo-23645386",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data/derived/annual_revision/native-artist-identities-20261031",
    )
    args = parser.parse_args()
    main(args.base_root, args.source_root, args.output)
