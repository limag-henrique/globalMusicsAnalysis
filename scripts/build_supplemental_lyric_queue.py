"""Classify all supplemental songs against canonical catalog & v13 strict audit and build a resumable lyric queue."""

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
        "--strict-audit",
        type=Path,
        default=Path("data/runtime/priority-full-verification-20261117-13-canonical-live-current-code/decisions.jsonl"),
    )
    parser.add_argument("--strict-audit-version", default="v13")
    parser.add_argument("--exclude-processed-db", type=Path)
    parser.add_argument("--native-match-only", action="store_true")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/runtime/supplemental-lyrics-20261118-01"),
    )
    args = parser.parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if any((args.output_dir / name).exists() for name in (
        "supplemental-lyric-queue.jsonl", "queue-summary.json"
    )):
        raise ValueError("queue outputs already exist; use a new versioned directory")
    processed = set()
    if args.exclude_processed_db:
        with sqlite3.connect(args.exclude_processed_db.resolve().as_uri() + "?mode=ro", uri=True) as db:
            processed = {row[0] for row in db.execute("SELECT song_id FROM supplemental_lyrics")}

    audit_sha = hashlib.sha256(args.strict_audit.read_bytes()).hexdigest()
    strict_map = {}
    with args.strict_audit.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                strict_map[d["candidate_id"]] = d

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

    sdb = sqlite3.connect(args.supp_db.resolve().as_uri() + "?mode=ro", uri=True)
    supp_songs = sdb.execute(
        "SELECT song_id, title, artist_credit, native_provider, native_song_id, version_tags_json, featured_artists_json "
        "FROM supplemental_songs"
    ).fetchall()
    total_provider_identity_keys = len(supp_songs)
    if len(strict_map) + total_provider_identity_keys > 150_000:
        raise ValueError("conservative combined candidate budget exceeds 150000")
    mem_stats = {
        sid: (cnt, best_rank)
        for sid, cnt, best_rank in sdb.execute(
            "SELECT song_id, count(*), min(position) FROM supplemental_memberships GROUP BY song_id"
        )
    }
    duration_by_song: dict[str, int] = {}
    for sid, raw_j in sdb.execute("SELECT song_id, raw_json FROM supplemental_memberships"):
        if sid in duration_by_song:
            continue
        try:
            raw = json.loads(raw_j)
        except Exception:
            continue
        if raw.get("duration_ms"):
            duration_by_song[sid] = int(raw["duration_ms"])
        elif isinstance(raw.get("source_entry"), dict):
            dur = (raw["source_entry"].get("track") or {}).get("duration")
            if dur:
                duration_by_song[sid] = int(float(dur) * 1000)
    sdb.close()

    status_counts = Counter()
    queue_rows = []
    for song_id, title, artist, nat_prov, nat_id, vtags_j, farts_j in supp_songs:
        if song_id in processed:
            continue
        cnt, best_rank = mem_stats.get(song_id, (0, 999999))
        vtags = json.loads(vtags_j) if vtags_j else []
        farts = json.loads(farts_j) if farts_j else []
        dur_ms = duration_by_song.get(song_id)

        state = ""
        matched_cid = None
        if not (title or "").strip() or not (artist or "").strip():
            state = "unresolved_identity_missing_credit"
        elif nat_prov and nat_id and f"{nat_prov}:{nat_id}" in canon_by_id:
            matched_cid = f"{nat_prov}:{nat_id}"
        elif not args.native_match_only:
            candidates = canon_by_title_artist.get((norm(title), norm(artist)), [])
            if not candidates:
                candidates = canon_by_collab.get(collab_key(title, artist, vtags), [])
            if len(candidates) == 1:
                matched_cid = candidates[0]
            elif len(candidates) > 1:
                # Try duration disambiguation (+-3000ms) if dur_ms is known
                if dur_ms:
                    dur_matches = []
                    for ccid in candidates:
                        cp, _ = canon_by_id[ccid]
                        cdur = (cp.get("metadata_resolution") or {}).get("duration_ms") or cp.get("duration_ms")
                        if cdur and abs(int(cdur) - dur_ms) <= 3000:
                            dur_matches.append(ccid)
                    if len(dur_matches) == 1:
                        matched_cid = dur_matches[0]
                if matched_cid is None:
                    state = "identity_ambiguous_multiple_canonical"

        if matched_cid is not None:
            _, res = canon_by_id[matched_cid]
            sa = strict_map.get(matched_cid)
            if sa and sa.get("provider_supported"):
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
                "duration_ms": dur_ms,
                "memberships_count": cnt,
                "best_rank": best_rank,
                "state": state,
                "matched_canonical_id": matched_cid,
            }
        )

    queue_rows.sort(key=lambda r: (-r["memberships_count"], r["best_rank"], r["song_id"]))
    q_path = args.output_dir / "supplemental-lyric-queue.jsonl"
    with q_path.open("w", encoding="utf-8") as f:
        for r in queue_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    summary = {
        "schema_version": "supplemental-lyric-queue-v2",
        "generated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "strict_audit_version": args.strict_audit_version,
        "strict_audit_path": str(args.strict_audit),
        "strict_audit_sha256": audit_sha,
        "total_supplemental_songs": len(queue_rows),
        "total_provider_identity_keys": total_provider_identity_keys,
        "excluded_processed": total_provider_identity_keys - len(queue_rows),
        "native_match_only": args.native_match_only,
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
