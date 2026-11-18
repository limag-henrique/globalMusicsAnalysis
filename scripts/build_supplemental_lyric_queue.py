"""Classify all supplemental songs against canonical catalog & v08 validation and build a resumable lyric queue."""

import argparse
import hashlib
import json
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

_WS_RE = re.compile(r"\s+")
_FEAT_PAREN_RE = re.compile(r"\s*[\(\[（](?:feat\.?|ft\.?|featuring)\s+[^)\]）]+[\)\]）]", re.I)
_ARTIST_SPLIT_RE = re.compile(r"\s*(?:\||,|&|\bfeat\.?\b|\bft\.?\b|\bfeaturing\b)\s*", re.I)


def norm(text: str) -> str:
    return _WS_RE.sub(" ", (text or "").strip().lower())


def collab_key(title: str, artist: str, version_tags: list[str] | None = None) -> tuple:
    base_title = norm(_FEAT_PAREN_RE.sub("", title or ""))
    # Also extract featured artist from title if present
    artists = set()
    for part in _ARTIST_SPLIT_RE.split(artist or ""):
        p = norm(part)
        if p:
            artists.add(p)
    vtags = tuple(sorted(norm(v) for v in (version_tags or [])))
    return (base_title, frozenset(artists), vtags)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--supp-db",
        type=Path,
        default=Path("data/derived/annual_revision/provider_series/supplemental-catalog-20261117-39.sqlite"),
    )
    parser.add_argument(
        "--canon-db",
        type=Path,
        default=Path("data/runtime/final-pipeline/catalog.sqlite"),
    )
    parser.add_argument(
        "--v08",
        type=Path,
        default=Path("data/runtime/priority-full-verification-20261117-12-canonical-catalog-only/decisions.jsonl"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/runtime/supplemental-lyrics-20261117-02"),
    )
    args = parser.parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Load strict verification decisions
    v08_map = {}
    with args.v08.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                v08_map[d["candidate_id"]] = d

    # Load canonical songs
    cdb = sqlite3.connect(args.canon_db.resolve().as_uri() + "?mode=ro", uri=True)
    canon_by_id = {}
    canon_by_title_artist = defaultdict(list)
    canon_by_collab = defaultdict(list)
    for cid, payload_json, result_json in cdb.execute("SELECT id, payload, result FROM songs"):
        payload = json.loads(payload_json)
        result = json.loads(result_json) if result_json else {}
        canon_by_id[cid] = (payload, result)
        key = (norm(payload.get("title", "")), norm(payload.get("artist", "")))
        if key[0] and key[1]:
            canon_by_title_artist[key].append(cid)
            ck = collab_key(payload.get("title", ""), payload.get("artist", ""))
            if ck[0] and ck[1]:
                canon_by_collab[ck].append(cid)
    cdb.close()

    # Load supplemental songs + series priority
    sdb = sqlite3.connect(args.supp_db.resolve().as_uri() + "?mode=ro", uri=True)
    supp_songs = sdb.execute(
        "SELECT song_id, title, artist_credit, native_provider, native_song_id, version_tags_json, featured_artists_json "
        "FROM supplemental_songs"
    ).fetchall()
    # Count memberships & best rank per song_id
    mem_stats = {}
    for sid, cnt, best_rank in sdb.execute(
        "SELECT song_id, count(*), min(position) FROM supplemental_memberships GROUP BY song_id"
    ):
        mem_stats[sid] = (cnt, best_rank)
    sdb.close()

    status_counts = Counter()
    queue_rows = []
    for song_id, title, artist, nat_prov, nat_id, vtags_j, farts_j in supp_songs:
        cnt, best_rank = mem_stats.get(song_id, (0, 999999))
        vtags = json.loads(vtags_j) if vtags_j else []
        farts = json.loads(farts_j) if farts_j else []

        if not (title or "").strip() or not (artist or "").strip():
            state = "unresolved_identity_missing_credit"
            matched_cid = None
        else:
            state = ""
            matched_cid = None
            # 1. Exact native ID match if SPOTIFY
            if nat_prov == "SPOTIFY" and nat_id and f"SPOTIFY:{nat_id}" in canon_by_id:
                matched_cid = f"SPOTIFY:{nat_id}"
            else:
                # 2. Exact normalized (title, artist) match only if unambiguous (1 canonical song)
                candidates = canon_by_title_artist.get((norm(title), norm(artist)), [])
                if not candidates:
                    candidates = canon_by_collab.get(collab_key(title, artist, vtags), [])
                if len(candidates) == 1:
                    matched_cid = candidates[0]
                elif len(candidates) > 1:
                    state = "identity_ambiguous_multiple_canonical"
                    matched_cid = None
                else:
                    matched_cid = None

            if matched_cid is not None:
                _, res = canon_by_id[matched_cid]
                v8 = v08_map.get(matched_cid)
                if v8 and v8.get("provider_supported"):
                    state = "matched_canonical_validated"
                elif res.get("text_sha256"):
                    state = "matched_canonical_needs_validation_or_correction"
                else:
                    state = "matched_canonical_missing_text"
            elif state == "":
                state = "new_requires_acquisition"

        status_counts[state] += 1
        queue_rows.append(
            {
                "song_id": song_id,
                "title": title,
                "artist_credit": artist,
                "native_provider": nat_prov,
                "native_song_id": nat_id,
                "version_tags": vtags,
                "featured_artists": farts,
                "memberships_count": cnt,
                "best_rank": best_rank,
                "state": state,
                "matched_canonical_id": matched_cid,
            }
        )

    # Sort queue by memberships_count desc, best_rank asc, song_id asc
    queue_rows.sort(key=lambda r: (-r["memberships_count"], r["best_rank"], r["song_id"]))
    q_path = args.output_dir / "supplemental-lyric-queue.jsonl"
    with q_path.open("w", encoding="utf-8") as f:
        for r in queue_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    summary = {
        "schema_version": "supplemental-lyric-queue-v1",
        "generated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_supplemental_songs": len(queue_rows),
        "status_counts": dict(status_counts),
        "queue_path": str(q_path),
        "queue_sha256": hashlib.sha256(q_path.read_bytes()).hexdigest(),
    }
    (args.output_dir / "queue-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
