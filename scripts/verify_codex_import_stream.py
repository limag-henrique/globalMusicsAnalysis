"""Independent online validation worker for the Codex/ChatGPT import stream.

Snapshots the read-only canonical catalog, strict audit baseline, and active
Codex dispatch reservations; verifies candidate recordings and lyric evidence
against live public web sources (Spotify embed/oEmbed, Apple iTunes Search,
YouTube oEmbed, and LRCLIB); persists durable per-item state and captures;
and publishes atomic versioned handoff batches for Codex promotion.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import random
import re
import sqlite3
import time
import unicodedata
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import httpx

PARSER_VERSION = "codex-import-verifier-v2"
USER_AGENT = "PromiscuidadeMusical-Verifier/1.0 (+https://github.com/chart-observatory)"
VERSION_QUALIFIERS = (
    "remix",
    "live",
    "acoustic",
    "instrumental",
    "karaoke",
    "cover",
    "medley",
    "sped up",
    "slowed",
    "radio edit",
    "clean",
    "explicit",
    "remaster",
    "unplugged",
    "demo",
)


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    s = unicodedata.normalize("NFKC", value).lower().strip()
    s = re.sub(r"[\(\[\{].*?[\)\]\}]", " ", s)
    s = re.sub(r"\s+-\s+.*$", " ", s)
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extract_qualifiers(value: str | None) -> set[str]:
    if not value:
        return set()
    low = value.lower()
    return {q for q in VERSION_QUALIFIERS if q in low}


def token_overlap(a: str | None, b: str | None) -> float:
    ta = set(normalize_text(a).split())
    tb = set(normalize_text(b).split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta), len(tb))


class HostPacedClient:
    """HTTP client with per-host pacing, jitter, Retry-After, and raw capture."""

    def __init__(self, captures_dir: Path, min_interval: float = 1.0) -> None:
        self.captures_dir = captures_dir
        self.captures_dir.mkdir(parents=True, exist_ok=True)
        self.min_interval = min_interval
        self._last_host_call: dict[str, float] = {}
        self._host_cooldown_until: dict[str, float] = {}
        self._client = httpx.Client(
            timeout=20.0,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )

    def close(self) -> None:
        self._client.close()

    def fetch(
        self,
        url: str,
        capture_rel: str,
        *,
        max_retries: int = 2,
    ) -> dict[str, Any]:
        capture_path = self.captures_dir / capture_rel
        meta_path = capture_path.with_suffix(capture_path.suffix + ".meta.json")
        if capture_path.exists() and meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["replayed_from_cache"] = True
            meta["capture_path"] = str(capture_path)
            return meta

        host = httpx.URL(url).host or "unknown"
        last_err: str | None = None
        for attempt in range(max_retries + 1):
            now = time.monotonic()
            cd_until = self._host_cooldown_until.get(host, 0.0)
            if now < cd_until:
                time.sleep(min(cd_until - now, 15.0))
            last = self._last_host_call.get(host, 0.0)
            wait = self.min_interval - (time.monotonic() - last)
            if wait > 0:
                time.sleep(wait + random.uniform(0.05, 0.25))

            self._last_host_call[host] = time.monotonic()
            retrieved_at = utc_now()
            try:
                resp = self._client.get(url)
                body = resp.content
                status = resp.status_code
                if status in (429, 503):
                    ra = resp.headers.get("Retry-After")
                    delay = float(ra) if ra and ra.isdigit() else (2.0 ** (attempt + 1))
                    self._host_cooldown_until[host] = time.monotonic() + min(delay, 30.0)
                    last_err = f"HTTP {status}"
                    if attempt < max_retries:
                        time.sleep(min(delay, 10.0) + random.uniform(0.1, 0.5))
                        continue

                capture_path.parent.mkdir(parents=True, exist_ok=True)
                capture_path.write_bytes(body)
                meta = {
                    "request_url": url,
                    "effective_url": str(resp.url),
                    "retrieved_at_utc": retrieved_at,
                    "http_status": status,
                    "content_type": resp.headers.get("content-type", ""),
                    "byte_count": len(body),
                    "sha256": sha256_bytes(body),
                    "parser_version": PARSER_VERSION,
                    "replayed_from_cache": False,
                    "capture_path": str(capture_path),
                    "error": last_err if status >= 400 else None,
                }
                meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
                return meta
            except httpx.HTTPError as exc:
                last_err = f"{type(exc).__name__}: {exc}"
                if attempt < max_retries:
                    time.sleep((2.0 ** attempt) + random.uniform(0.1, 0.4))
                    continue
                return {
                    "request_url": url,
                    "effective_url": url,
                    "retrieved_at_utc": retrieved_at,
                    "http_status": 0,
                    "content_type": "",
                    "byte_count": 0,
                    "sha256": None,
                    "parser_version": PARSER_VERSION,
                    "replayed_from_cache": False,
                    "capture_path": None,
                    "error": last_err,
                }
        return {"request_url": url, "http_status": 0, "error": last_err}


def init_verifier_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS candidate_snapshots (
            candidate_id TEXT PRIMARY KEY,
            platform TEXT NOT NULL,
            native_id TEXT NOT NULL,
            title TEXT,
            artist TEXT,
            membership_count INTEGER NOT NULL,
            memberships_json TEXT NOT NULL,
            evidence_fingerprint TEXT NOT NULL,
            strict_provider_supported INTEGER NOT NULL,
            strict_native_supported INTEGER NOT NULL,
            priority_tier INTEGER NOT NULL,
            updated_at_utc TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS verifications (
            candidate_id TEXT PRIMARY KEY,
            analyzed_fingerprint TEXT NOT NULL,
            verdict TEXT NOT NULL,
            audio_alignment_bound INTEGER NOT NULL,
            native_resolved INTEGER NOT NULL,
            native_metadata_json TEXT NOT NULL,
            lyric_source_json TEXT NOT NULL,
            reason_codes_json TEXT NOT NULL,
            evidence_paths_json TEXT NOT NULL,
            proposed_correction_json TEXT,
            remaining_gates_json TEXT NOT NULL,
            batch_id TEXT,
            codex_ack_status TEXT NOT NULL,
            verified_at_utc TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS handoff_batches (
            batch_id TEXT PRIMARY KEY,
            manifest_path TEXT NOT NULL,
            manifest_sha256 TEXT NOT NULL,
            jsonl_path TEXT NOT NULL,
            jsonl_sha256 TEXT NOT NULL,
            item_count INTEGER NOT NULL,
            verdict_counts_json TEXT NOT NULL,
            created_at_utc TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS poll_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL
        );
        """
    )


def compute_fingerprint(
    candidate_id: str,
    text_sha256: str | None,
    staging_ref: str | None,
    strict_row: dict[str, Any] | None,
    membership_count: int,
) -> str:
    sr = strict_row or {}
    ne = sr.get("native_evidence") or {}
    src = sr.get("source_result") or {}
    raw = {
        "candidate_id": candidate_id,
        "text_sha256": text_sha256,
        "staging_ref": staging_ref,
        "native_duration_ms": ne.get("duration_ms"),
        "native_isrc": ne.get("isrc"),
        "source": src.get("source"),
        "source_record_id": src.get("source_record_id"),
        "raw_response_sha256": src.get("raw_response_sha256"),
        "membership_count": membership_count,
        "verifier": PARSER_VERSION,
    }
    return sha256_text(json.dumps(raw, sort_keys=True))


def load_codex_priority_ids(reservations_path: Path) -> set[str]:
    priority: set[str] = set()
    if reservations_path.exists():
        data = json.loads(reservations_path.read_text(encoding="utf-8"))
        for a in data.get("assignments") or []:
            shard = a.get("shard") or {}
            if shard.get("candidate_id"):
                priority.add(shard["candidate_id"])
            for cid in shard.get("candidate_ids") or []:
                priority.add(cid)
    return priority


def file_revision(path: Path) -> tuple | None:
    try:
        stat = path.stat()
        return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    except FileNotFoundError:
        return None


def read_strict_audit(path: Path) -> dict[str, dict[str, Any]]:
    rows = {}
    if path.exists():
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                if line.strip():
                    row = json.loads(line)
                    rows[row["candidate_id"]] = row
    return rows


class SnapshotRefresh:
    """Refresh on committed catalog changes or changed audit/reservation files."""

    def __init__(self, catalog: Path, audit: Path, reservations: Path):
        self.catalog, self.audit, self.reservations = catalog, audit, reservations
        self.reader = sqlite3.connect(catalog.resolve().as_uri() + "?mode=ro", uri=True)
        self.revision = None
        self.strict_map = {}
        self.audit_revision = None
        self.stats = {}

    def refresh(self, conn: sqlite3.Connection) -> dict[str, int]:
        revision = (
            self.reader.execute("PRAGMA data_version").fetchone()[0],
            file_revision(self.catalog), file_revision(Path(str(self.catalog) + "-wal")),
            file_revision(self.audit), file_revision(self.reservations),
        )
        if revision == self.revision:
            return self.stats
        # Record pre-read revisions: changes during refresh trigger another refresh.
        audit_revision = revision[3]
        strict_map = (read_strict_audit(self.audit)
                      if self.revision is None or audit_revision != self.audit_revision
                      else self.strict_map)
        self.stats = snapshot_catalog_and_audit(
            conn, self.catalog, self.audit, self.reservations, strict_map=strict_map
        )
        self.strict_map = strict_map
        self.audit_revision = audit_revision
        self.revision = revision
        return self.stats

    def close(self) -> None:
        self.reader.close()


def snapshot_catalog_and_audit(
    conn: sqlite3.Connection,
    catalog_path: Path,
    strict_audit_path: Path,
    reservations_path: Path,
    *, strict_map: dict[str, dict[str, Any]] | None = None,
) -> dict[str, int]:
    """Read-only snapshot of catalog.sqlite + v13 decisions.jsonl into verifier.sqlite."""
    if strict_map is None:
        strict_map = read_strict_audit(strict_audit_path)

    codex_priority_ids = load_codex_priority_ids(reservations_path)

    cat = sqlite3.connect(f"file:{catalog_path}?mode=ro", uri=True)
    cat.execute("BEGIN")
    memberships_by_song: dict[str, list[dict[str, Any]]] = {}
    for scope, country, period, platform, rank, song_id in cat.execute(
        "SELECT scope, country, period, platform, rank, song_id FROM memberships"
    ):
        memberships_by_song.setdefault(song_id, []).append(
            {
                "scope": scope,
                "country": country,
                "period": period,
                "platform": platform,
                "rank": rank,
            }
        )

    songs = cat.execute("SELECT id, payload, result FROM songs").fetchall()
    cat.close()

    now = utc_now()
    stats = Counter()
    with conn:
        for sid, payload_raw, result_raw in songs:
            payload = json.loads(payload_raw) if payload_raw else {}
            result = json.loads(result_raw) if result_raw else {}
            mems = memberships_by_song.get(sid) or []
            if sid not in strict_map and sid not in codex_priority_ids:
                continue

            sa = strict_map.get(sid)
            text_sha = result.get("text_sha256") or (sa.get("text_sha256") if sa else None)
            staging_ref = result.get("staging_reference")
            base_fp = compute_fingerprint(sid, text_sha, staging_ref, sa, len(mems))
            fp = sha256_text(json.dumps(
                {"base": base_fp, "payload": payload, "result": result,
                 "strict_audit": sa, "memberships": sorted(
                     mems, key=lambda row: json.dumps(row, sort_keys=True))},
                sort_keys=True, ensure_ascii=False,
            ))

            prov_ok = 1 if (sa and sa.get("provider_supported")) else 0
            nat_ok = 1 if (sa and sa.get("native_and_provider_supported")) else 0
            if sid in codex_priority_ids:
                tier = 1
            elif not prov_ok or not nat_ok:
                tier = 2
            else:
                tier = 3

            platform, _, native_id = sid.partition(":")
            conn.execute(
                """
                INSERT INTO candidate_snapshots (
                    candidate_id, platform, native_id, title, artist,
                    membership_count, memberships_json, evidence_fingerprint,
                    strict_provider_supported, strict_native_supported,
                    priority_tier, updated_at_utc
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(candidate_id) DO UPDATE SET
                    title=excluded.title,
                    artist=excluded.artist,
                    membership_count=excluded.membership_count,
                    memberships_json=excluded.memberships_json,
                    evidence_fingerprint=excluded.evidence_fingerprint,
                    strict_provider_supported=excluded.strict_provider_supported,
                    strict_native_supported=excluded.strict_native_supported,
                    priority_tier=excluded.priority_tier,
                    updated_at_utc=excluded.updated_at_utc
                """,
                (
                    sid,
                    platform,
                    native_id,
                    payload.get("title"),
                    payload.get("artist"),
                    len(mems),
                    json.dumps(mems, ensure_ascii=False),
                    fp,
                    prov_ok,
                    nat_ok,
                    tier,
                    now,
                ),
            )
            stats[f"tier_{tier}"] += 1
            stats["total_snapshotted"] += 1
    return dict(stats)


def parse_spotify_embed(html_bytes: bytes) -> dict[str, Any]:
    text = html_bytes.decode("utf-8", errors="replace")
    m = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        text,
        re.DOTALL,
    )
    if not m:
        return {}
    try:
        data = json.loads(m.group(1))
        entity = (
            data.get("props", {})
            .get("pageProps", {})
            .get("state", {})
            .get("data", {})
            .get("entity", {})
        )
        artists = [
            a.get("name") for a in (entity.get("artists") or []) if a.get("name")
        ]
        return {
            "source": "spotify_embed",
            "title": entity.get("name") or entity.get("title"),
            "artists": artists,
            "duration_ms": entity.get("duration"),
            "release_date": (entity.get("releaseDate") or {}).get("isoString"),
            "is_explicit": entity.get("isExplicit"),
            "uri": entity.get("uri"),
        }
    except Exception:
        return {}


def resolve_native_recording(
    http: HostPacedClient,
    platform: str,
    native_id: str,
    title: str | None,
    artist: str | None,
) -> tuple[dict[str, Any], list[str]]:
    evidence_paths: list[str] = []
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", native_id)
    resolved: dict[str, Any] = {
        "platform": platform,
        "native_id": native_id,
        "title": title,
        "artists": [a.strip() for a in (artist or "").split("|") if a.strip()],
        "duration_ms": None,
        "isrc": None,
        "sources": [],
    }

    if platform == "SPOTIFY":
        embed_url = f"https://open.spotify.com/embed/track/{native_id}"
        meta = http.fetch(embed_url, f"spotify/{safe_id}_embed.html")
        if meta.get("capture_path"):
            evidence_paths.append(meta["capture_path"])
        if meta.get("http_status") == 200 and meta.get("capture_path"):
            parsed = parse_spotify_embed(Path(meta["capture_path"]).read_bytes())
            if parsed.get("title"):
                resolved["title"] = parsed["title"]
            if parsed.get("artists"):
                resolved["artists"] = parsed["artists"]
            if parsed.get("duration_ms"):
                resolved["duration_ms"] = parsed["duration_ms"]
            if parsed.get("release_date"):
                resolved["release_date"] = parsed["release_date"]
            resolved["sources"].append(
                {"type": "spotify_embed", "http_status": 200, "sha256": meta.get("sha256")}
            )

    elif platform == "YOUTUBE":
        yt_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={native_id}&format=json"
        meta = http.fetch(yt_url, f"youtube/{safe_id}_oembed.json")
        if meta.get("capture_path"):
            evidence_paths.append(meta["capture_path"])
        if meta.get("http_status") == 200 and meta.get("capture_path"):
            try:
                yb = json.loads(Path(meta["capture_path"]).read_text(encoding="utf-8"))
                resolved["youtube_oembed_title"] = yb.get("title")
                resolved["youtube_author"] = yb.get("author_name")
                resolved["sources"].append(
                    {"type": "youtube_oembed", "http_status": 200, "sha256": meta.get("sha256")}
                )
            except Exception:
                pass

    # Cross-check with Apple iTunes Search API for duration / release / edition corroboration
    q_artist = resolved["artists"][0] if resolved["artists"] else ""
    q_title = resolved.get("title") or ""
    if q_title:
        term = quote_plus(f"{q_title} {q_artist}".strip())
        itunes_url = f"https://itunes.apple.com/search?term={term}&entity=song&limit=5"
        imeta = http.fetch(itunes_url, f"itunes/{safe_id}_itunes.json")
        if imeta.get("capture_path"):
            evidence_paths.append(imeta["capture_path"])
        if imeta.get("http_status") == 200 and imeta.get("capture_path"):
            try:
                ib = json.loads(Path(imeta["capture_path"]).read_text(encoding="utf-8"))
                for item in ib.get("results") or []:
                    if token_overlap(item.get("trackName"), q_title) >= 0.6 and (
                        not q_artist or token_overlap(item.get("artistName"), q_artist) >= 0.4
                    ):
                        resolved["itunes_match"] = {
                            "trackId": item.get("trackId"),
                            "trackName": item.get("trackName"),
                            "artistName": item.get("artistName"),
                            "trackTimeMillis": item.get("trackTimeMillis"),
                            "releaseDate": item.get("releaseDate"),
                        }
                        if not resolved.get("duration_ms") and item.get("trackTimeMillis"):
                            resolved["duration_ms"] = item["trackTimeMillis"]
                        resolved["sources"].append(
                            {
                                "type": "itunes_search",
                                "http_status": 200,
                                "sha256": imeta.get("sha256"),
                            }
                        )
                        break
            except Exception:
                pass

    return resolved, evidence_paths


def check_text_integrity(text: str | None) -> tuple[bool, list[str]]:
    if not text or not text.strip():
        return False, ["empty_text"]
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    flags: list[str] = []
    if len(lines) < 4 or len(text.strip()) < 80:
        flags.append("short_or_clipped_text")
    low = text.lower()
    if any(m in low for m in ("contributors", "translations", "embed", "you might also like")):
        flags.append("possible_web_navigation_contamination")
    if lines and (lines[-1].endswith("...") or lines[0].startswith("...")):
        flags.append("ellipsis_clipped_boundary")
    return len(flags) == 0, flags


def score_lrclib_candidate(
    rec: dict[str, Any],
    native: dict[str, Any],
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if rec.get("instrumental"):
        reasons.append("lrclib_instrumental")
        return False, reasons
    plain = (rec.get("plainLyrics") or "").strip()
    if not plain:
        reasons.append("lrclib_empty_plain_lyrics")
        return False, reasons

    nt = native.get("title") or ""
    lt = rec.get("trackName") or ""
    if token_overlap(nt, lt) < 0.6:
        reasons.append("title_mismatch")

    n_artists = " ".join(native.get("artists") or [])
    la = rec.get("artistName") or ""
    if n_artists and token_overlap(n_artists, la) < 0.35:
        reasons.append("artist_mismatch")

    nq = extract_qualifiers(nt)
    lq = extract_qualifiers(lt)
    if (lq - nq) & {"remix", "live", "cover", "medley", "acoustic", "karaoke"}:
        reasons.append("edition_qualifier_mismatch")

    nd_ms = native.get("duration_ms")
    ld_s = rec.get("duration")
    if nd_ms and ld_s:
        gap = abs((nd_ms / 1000.0) - float(ld_s))
        if gap > 5.5:
            reasons.append(f"duration_mismatch_{gap:.1f}s")

    ok_text, tflags = check_text_integrity(plain)
    reasons.extend(tflags)
    return len(reasons) == 0, reasons


def verify_candidate(
    http: HostPacedClient,
    row: dict[str, Any],
    strict_row: dict[str, Any] | None,
) -> dict[str, Any]:
    cid = row["candidate_id"]
    platform = row["platform"]
    native_id = row["native_id"]
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", native_id)

    native, evidence_paths = resolve_native_recording(
        http, platform, native_id, row.get("title"), row.get("artist")
    )
    native_resolved = bool(native.get("sources"))

    src_res = (strict_row or {}).get("source_result") or {}
    existing_rec_id = src_res.get("source_record_id")
    existing_source = src_res.get("source")
    imported_sha = (strict_row or {}).get("text_sha256")

    lyric_info: dict[str, Any] = {
        "existing_source": existing_source,
        "existing_record_id": existing_rec_id,
        "imported_text_sha256": imported_sha,
    }
    reason_codes: list[str] = []
    proposed_correction: dict[str, Any] | None = None
    verdict = "pending_independent_evidence"

    # 1. Check existing LRCLIB record directly if present
    if existing_source == "LRCLIB" and existing_rec_id:
        lrc_url = f"https://lrclib.net/api/get/{existing_rec_id}"
        lmeta = http.fetch(lrc_url, f"lrclib/{safe_id}_get_{existing_rec_id}.json")
        if lmeta.get("capture_path"):
            evidence_paths.append(lmeta["capture_path"])
        if lmeta.get("http_status") == 200 and lmeta.get("capture_path"):
            rec = json.loads(Path(lmeta["capture_path"]).read_text(encoding="utf-8"))
            plain = (rec.get("plainLyrics") or "").strip()
            rec_sha = sha256_text(plain) if plain else None
            lyric_info["direct_url"] = lrc_url
            lyric_info["direct_sha256"] = rec_sha
            lyric_info["direct_duration_s"] = rec.get("duration")
            ok, reasons = score_lrclib_candidate(rec, native)
            if imported_sha and rec_sha and imported_sha != rec_sha:
                # Try with trailing newline too (common normalization difference)
                if imported_sha != sha256_text(plain + "\n"):
                    reasons.append("imported_text_hash_mismatch")
                    ok = False
            if ok:
                verdict = "verified_within_evidence_scope"
            else:
                reason_codes.extend(reasons)
                if any(r.startswith("duration_mismatch") or r == "edition_qualifier_mismatch" for r in reasons):
                    verdict = "wrong_recording"
                elif any(r in ("short_or_clipped_text", "ellipsis_clipped_boundary", "possible_web_navigation_contamination") for r in reasons):
                    verdict = "incomplete_text"
                else:
                    verdict = "ambiguous_edition"
        elif lmeta.get("http_status") in (0, 429, 503):
            verdict = "source_inaccessible"
            reason_codes.append(f"lrclib_get_http_{lmeta.get('http_status')}")

    # 2. If not verified yet, search LRCLIB by verified native title & primary artist
    if verdict != "verified_within_evidence_scope" and native.get("title"):
        q_title = native["title"]
        q_artist = native["artists"][0] if native.get("artists") else ""
        search_url = (
            f"https://lrclib.net/api/search?track_name={quote_plus(q_title)}"
            + (f"&artist_name={quote_plus(q_artist)}" if q_artist else "")
        )
        smeta = http.fetch(search_url, f"lrclib/{safe_id}_search.json")
        if smeta.get("capture_path"):
            evidence_paths.append(smeta["capture_path"])
        if smeta.get("http_status") == 200 and smeta.get("capture_path"):
            results = json.loads(Path(smeta["capture_path"]).read_text(encoding="utf-8"))
            best_match = None
            for cand in results[:15]:
                ok, _ = score_lrclib_candidate(cand, native)
                if ok:
                    best_match = cand
                    break
            if best_match:
                plain = (best_match.get("plainLyrics") or "").strip()
                proposed_correction = {
                    "action": "replace_or_adopt_lrclib_record",
                    "source": "LRCLIB",
                    "record_id": best_match.get("id"),
                    "url": f"https://lrclib.net/api/get/{best_match.get('id')}",
                    "trackName": best_match.get("trackName"),
                    "artistName": best_match.get("artistName"),
                    "duration_s": best_match.get("duration"),
                    "text_sha256": sha256_text(plain),
                    "text_chars": len(plain),
                }
                if not imported_sha:
                    verdict = "verified_within_evidence_scope"
                    reason_codes.append("new_authorized_source_found_pending_codex_import")
                elif imported_sha in (sha256_text(plain), sha256_text(plain + "\n")):
                    verdict = "verified_within_evidence_scope"
                    reason_codes.append("lrclib_corroborates_imported_text")
                else:
                    reason_codes.append("proposed_lrclib_replacement_pending_codex_promotion")
            elif not reason_codes:
                reason_codes.append("no_matching_lrclib_record")
        elif smeta.get("http_status") in (0, 429, 503):
            if verdict == "pending_independent_evidence":
                verdict = "source_inaccessible"
            reason_codes.append(f"lrclib_search_http_{smeta.get('http_status')}")

    remaining_gates = ["codex_canonical_promotion"]
    if not native.get("isrc"):
        remaining_gates.append("isrc_or_audio_binding_unverified")
    if verdict != "verified_within_evidence_scope":
        remaining_gates.append("evidence_resolution_required")

    return {
        "candidate_id": cid,
        "platform": platform,
        "native_id": native_id,
        "membership_count": row["membership_count"],
        "memberships_sample": json.loads(row["memberships_json"]),
        "analyzed_fingerprint": row["evidence_fingerprint"],
        "verdict": verdict,
        "audio_alignment_bound": False,
        "native_resolved": native_resolved,
        "native_metadata": native,
        "lyric_source": lyric_info,
        "reason_codes": sorted(set(reason_codes)),
        "evidence_paths": sorted(set(evidence_paths)),
        "proposed_correction": proposed_correction,
        "remaining_gates": remaining_gates,
        "codex_ack_status": "pending_codex_promotion",
        "verified_at_utc": utc_now(),
    }


def publish_handoff_batch(
    conn: sqlite3.Connection,
    collab_dir: Path,
    items: list[dict[str, Any]],
    batch_num: int,
) -> dict[str, Any]:
    batch_id = f"antigravity-codex-import-verification-20261118-batch-{batch_num:04d}"
    jsonl_path = collab_dir / f"{batch_id}.jsonl"
    manifest_path = collab_dir / f"{batch_id}.json"

    jsonl_content = "\n".join(json.dumps(it, ensure_ascii=False) for it in items) + "\n"
    atomic_write_text(jsonl_path, jsonl_content)
    jsonl_sha = sha256_text(jsonl_content)

    verdict_counts = dict(Counter(it["verdict"] for it in items))
    manifest = {
        "schema_version": "antigravity-codex-import-verification-v1",
        "batch_id": batch_id,
        "generated_at_utc": utc_now(),
        "owner": "Antigravity",
        "promotion_owner": "Codex",
        "item_count": len(items),
        "verdict_counts": verdict_counts,
        "jsonl_path": str(jsonl_path),
        "jsonl_sha256": jsonl_sha,
        "codex_ack_status": "pending_codex_promotion",
        "items_summary": [
            {
                "candidate_id": it["candidate_id"],
                "verdict": it["verdict"],
                "membership_count": it["membership_count"],
                "has_proposed_correction": it["proposed_correction"] is not None,
                "reason_codes": it["reason_codes"],
            }
            for it in items
        ],
    }
    manifest_content = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    atomic_write_text(manifest_path, manifest_content)
    manifest_sha = sha256_text(manifest_content)

    with conn:
        for it in items:
            conn.execute(
                "UPDATE verifications SET batch_id=? WHERE candidate_id=?",
                (batch_id, it["candidate_id"]),
            )
        conn.execute(
            """
            INSERT OR REPLACE INTO handoff_batches
            (batch_id, manifest_path, manifest_sha256, jsonl_path, jsonl_sha256, item_count, verdict_counts_json, created_at_utc)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                batch_id,
                str(manifest_path),
                manifest_sha,
                str(jsonl_path),
                jsonl_sha,
                len(items),
                json.dumps(verdict_counts),
                utc_now(),
            ),
        )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=Path("data/runtime/codex-import-verifier-20261118-01"))
    parser.add_argument("--catalog", type=Path, default=Path("data/runtime/final-pipeline/catalog.sqlite"))
    parser.add_argument(
        "--strict-audit",
        type=Path,
        default=Path("data/runtime/priority-full-verification-20261117-13-canonical-live-current-code/decisions.jsonl"),
    )
    parser.add_argument(
        "--reservations",
        type=Path,
        default=Path("data/runtime/parallel-extraction/codex-dispatch-20261117-01-reservations.json"),
    )
    parser.add_argument(
        "--collab-dir",
        type=Path,
        default=Path("data/runtime/antigravity-collaboration-20261115"),
    )
    parser.add_argument("--batch-size", type=int, default=15)
    parser.add_argument("--max-batches", type=int, default=2)
    parser.add_argument("--poll-interval", type=int, default=45)
    parser.add_argument("--http-interval", type=float, default=1.0)
    args = parser.parse_args(argv)

    args.run_dir.mkdir(parents=True, exist_ok=True)
    db_path = args.run_dir / "verifier.sqlite"
    conn = sqlite3.connect(db_path)
    init_verifier_db(conn)

    refresh = SnapshotRefresh(args.catalog, args.strict_audit, args.reservations)

    http = HostPacedClient(args.run_dir / "captures", min_interval=args.http_interval)
    try:
        existing_batches = conn.execute("SELECT COUNT(*) FROM handoff_batches").fetchone()[0]
        batch_num = existing_batches
        batches_done = 0

        while args.max_batches == 0 or batches_done < args.max_batches:
            snap_stats = refresh.refresh(conn)
            strict_map = refresh.strict_map
            # Select candidates whose fingerprint is not yet verified at current revision
            rows = conn.execute(
                """
                SELECT s.candidate_id, s.platform, s.native_id, s.title, s.artist,
                       s.membership_count, s.memberships_json, s.evidence_fingerprint,
                       s.priority_tier
                FROM candidate_snapshots s
                LEFT JOIN verifications v ON s.candidate_id = v.candidate_id
                WHERE v.candidate_id IS NULL
                   OR v.analyzed_fingerprint != s.evidence_fingerprint
                   OR v.verdict = 'source_inaccessible'
                ORDER BY s.priority_tier ASC, s.membership_count DESC, s.candidate_id ASC
                LIMIT ?
                """,
                (args.batch_size,),
            ).fetchall()

            if not rows:
                print(f"[{utc_now()}] Queue caught up ({snap_stats}). Sleeping {args.poll_interval}s...")
                if args.max_batches > 0:
                    break
                time.sleep(args.poll_interval)
                continue

            cols = [
                "candidate_id",
                "platform",
                "native_id",
                "title",
                "artist",
                "membership_count",
                "memberships_json",
                "evidence_fingerprint",
                "priority_tier",
            ]
            batch_items: list[dict[str, Any]] = []
            t0 = time.monotonic()
            for r in rows:
                row_dict = dict(zip(cols, r))
                res = verify_candidate(http, row_dict, strict_map.get(row_dict["candidate_id"]))
                with conn:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO verifications (
                            candidate_id, analyzed_fingerprint, verdict, audio_alignment_bound,
                            native_resolved, native_metadata_json, lyric_source_json,
                            reason_codes_json, evidence_paths_json, proposed_correction_json,
                            remaining_gates_json, batch_id, codex_ack_status, verified_at_utc
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            res["candidate_id"],
                            res["analyzed_fingerprint"],
                            res["verdict"],
                            1 if res["audio_alignment_bound"] else 0,
                            1 if res["native_resolved"] else 0,
                            json.dumps(res["native_metadata"], ensure_ascii=False),
                            json.dumps(res["lyric_source"], ensure_ascii=False),
                            json.dumps(res["reason_codes"], ensure_ascii=False),
                            json.dumps(res["evidence_paths"], ensure_ascii=False),
                            json.dumps(res["proposed_correction"], ensure_ascii=False)
                            if res["proposed_correction"]
                            else None,
                            json.dumps(res["remaining_gates"], ensure_ascii=False),
                            None,
                            res["codex_ack_status"],
                            res["verified_at_utc"],
                        ),
                    )
                batch_items.append(res)

            batch_num += 1
            batches_done += 1
            manifest = publish_handoff_batch(conn, args.collab_dir, batch_items, batch_num)
            elapsed = time.monotonic() - t0
            rate = (len(batch_items) / elapsed) * 60.0 if elapsed > 0 else 0.0
            print(
                f"[{utc_now()}] Published {manifest['batch_id']}: "
                f"{len(batch_items)} items in {elapsed:.1f}s ({rate:.1f}/min) -> {manifest['verdict_counts']}"
            )
    finally:
        refresh.close()
        http.close()
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
