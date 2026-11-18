"""Lineage-preserving identity and denominator registry for supplemental provider series."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

_PARENS_RE = re.compile(r"\(([^)]+)\)|（([^）]+)）|\[([^\]]+)\]")
_VERSION_KEYWORDS = ("live", "remix", "ver", "version", "acoustic", "inst", "instrumental", "edit", "mix", "現場", "现场", "版")
_FEAT_KEYWORDS = ("feat", "ft.", "featuring")


def _norm(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def parse_title_and_artist(title: str, artist: str) -> dict[str, Any]:
    """Extract version/remix/live markers and featured artists without losing originals."""
    version_tags: list[str] = []
    featured_artists: list[str] = []
    for m in _PARENS_RE.finditer(title or ""):
        inner = next((g for g in m.groups() if g), "").strip()
        low = inner.lower()
        if any(k in low for k in _FEAT_KEYWORDS):
            featured_artists.append(inner)
        elif any(k in low for k in _VERSION_KEYWORDS):
            version_tags.append(inner)
    return {
        "title": (title or "").strip(),
        "artist_credit": (artist or "").strip(),
        "version_tags": version_tags,
        "featured_artists": featured_artists,
    }


def compute_song_id(
    provider_code: str,
    title: str,
    artist_credit: str,
    native_song_id: str | None = None,
    version_tags: list[str] | None = None,
) -> str:
    """Compute a lineage-preserving song ID that separates native IDs and version markers."""
    if native_song_id:
        return f"{provider_code}:{native_song_id}"
    version_key = "|".join(sorted(_norm(v) for v in (version_tags or [])))
    key = f"{_norm(title)}|{_norm(artist_credit)}|{version_key}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return f"SUPP:{digest}"


def verify_packet_hashes(packet_dir: Path, manifest: dict[str, Any]) -> list[str]:
    """Verify SHA-256 hashes declared in a provider-series manifest."""
    errors: list[str] = []

    def _check_file(ref: str, expected_sha: str) -> None:
        fp = Path(ref)
        if not fp.is_absolute() and not fp.exists():
            fp = packet_dir / ref
        if not fp.exists():
            errors.append(f"missing:{ref}")
            return
        actual = hashlib.sha256(fp.read_bytes()).hexdigest()
        if actual != expected_sha:
            errors.append(f"sha256_mismatch:{ref}")

    for item in manifest.get("source_artifacts") or []:
        if isinstance(item, dict) and item.get("local_path") and item.get("sha256"):
            _check_file(item["local_path"], item["sha256"])

    checked_snapshots: set[tuple[str, str]] = set()
    for snapshot_key in ("snapshots", "source_snapshots"):
        for fname, meta in (manifest.get(snapshot_key) or {}).items():
            if isinstance(meta, dict) and meta.get("sha256"):
                snapshot = (fname, meta["sha256"])
                if snapshot not in checked_snapshots:
                    _check_file(*snapshot)
                    checked_snapshots.add(snapshot)

    if manifest.get("ranking_file") and manifest.get("ranking_sha256"):
        _check_file(manifest["ranking_file"], manifest["ranking_sha256"])

    return errors


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS supplemental_series (
            series_id TEXT PRIMARY KEY,
            packet_name TEXT NOT NULL,
            provider_code TEXT NOT NULL,
            chart_family TEXT NOT NULL,
            reporting_year INTEGER NOT NULL,
            publisher_country_code TEXT NOT NULL,
            chart_market_code TEXT,
            reported_depth INTEGER,
            imported_positions INTEGER NOT NULL,
            normalized_identity_keys INTEGER NOT NULL,
            ties_or_gaps_json TEXT NOT NULL,
            evidence_status TEXT NOT NULL,
            manifest_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS supplemental_songs (
            song_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            artist_credit TEXT NOT NULL,
            native_provider TEXT,
            native_song_id TEXT,
            version_tags_json TEXT NOT NULL,
            featured_artists_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS supplemental_memberships (
            membership_id TEXT PRIMARY KEY,
            series_id TEXT NOT NULL,
            song_id TEXT NOT NULL,
            position INTEGER NOT NULL,
            published_rank TEXT NOT NULL,
            score TEXT,
            native_metric TEXT,
            source_url TEXT,
            source_sha256 TEXT,
            raw_json TEXT NOT NULL,
            FOREIGN KEY(series_id) REFERENCES supplemental_series(series_id),
            FOREIGN KEY(song_id) REFERENCES supplemental_songs(song_id)
        );
        CREATE INDEX IF NOT EXISTS idx_supp_memberships_song ON supplemental_memberships(song_id);
        CREATE INDEX IF NOT EXISTS idx_supp_memberships_series ON supplemental_memberships(series_id);
        """
    )


def _normalize_row(row: dict[str, Any], packet_name: str) -> dict[str, Any]:
    """Normalize CAVCA, TME UNI, and Circle Chart row schemas into a common membership record."""
    if "artist_credit" in row:
        title = row["title"]
        artist = row["artist_credit"]
        provider_code = row["provider_code"]
        chart_family = row.get("chart_family") or provider_code
        series_id = row["series_id"]
        year = int(row["reporting_year"])
        pos = int(row["position"])
        pub_rank = str(row.get("published_rank") or pos)
        native_id = row.get("native_song_id") or None
        pub_country = row["publisher_country_code"]
        mkt_country = row.get("chart_market_code")
        score = str(row["score"]) if row.get("score") is not None else None
        metric = row.get("native_metric")
        src_url = row.get("source_url")
        src_sha = row.get("source_sha256")
    else:
        title = row["title_original"]
        if row.get("artists_original"):
            artist = " / ".join(row["artists_original"])
        else:
            artist = row.get("artists_original_string") or row.get("artist_handle_original") or ""
        provider_code = row.get("provider_id") or "TME_UNI_CHART"
        chart_family = row.get("provider_name") or provider_code
        series_id = row["series_id"]
        year = int(row["report_year"])
        pos = int(row["rank"])
        pub_rank = str(row["rank"])
        native_id = None
        pub_country = row["publisher_country_code"]
        mkt_country = row.get("chart_market_code")
        score = str(row["score"]) if row.get("score") is not None else None
        metric = row.get("score_label") or row.get("score_label_original")
        src_url = row.get("source_url") or row.get("publisher_report_page_url")
        src_sha = row.get("source_pdf_sha256") or row.get("source_post_sha256")
        if row.get("source_api_sha256"):
            src_url = row.get("source_api_url") or src_url
            src_sha = row["source_api_sha256"]
        elif row.get("source_page_sha256"):
            src_url = row.get("source_page_url") or src_url
            src_sha = row["source_page_sha256"]

    parsed = parse_title_and_artist(title, artist)
    song_id = compute_song_id(
        provider_code,
        parsed["title"],
        parsed["artist_credit"],
        native_song_id=native_id,
        version_tags=parsed["version_tags"],
    )
    membership_id = row.get("membership_id") or f"{series_id}:{pos}:{song_id}"
    return {
        "membership_id": membership_id,
        "series_id": series_id,
        "packet_name": packet_name,
        "provider_code": provider_code,
        "chart_family": chart_family,
        "reporting_year": year,
        "publisher_country_code": pub_country,
        "chart_market_code": mkt_country,
        "position": pos,
        "published_rank": pub_rank,
        "song_id": song_id,
        "title": parsed["title"],
        "artist_credit": parsed["artist_credit"],
        "native_song_id": native_id,
        "version_tags": parsed["version_tags"],
        "featured_artists": parsed["featured_artists"],
        "score": score,
        "native_metric": metric,
        "source_url": src_url,
        "source_sha256": src_sha,
        "raw": row,
    }


def import_verified_provider_series(
    base_dir: Path,
    db_path: Path,
    *,
    packet_names: list[str] | None = None,
) -> dict[str, Any]:
    """Import verified supplemental provider series into a separate lineage-preserving SQLite catalog."""
    if db_path.exists():
        db_path.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    _init_db(conn)

    imported_series: list[dict[str, Any]] = []
    review_only_series: list[dict[str, Any]] = []
    skipped_packets: list[dict[str, Any]] = []

    dirs = (
        [base_dir / name for name in packet_names]
        if packet_names
        else sorted(p for p in base_dir.iterdir() if p.is_dir())
    )

    with conn:
        for p in dirs:
            manifest_path = p / "manifest.json"
            if not manifest_path.exists():
                skipped_packets.append({"packet": p.name, "reason": "no_manifest"})
                continue
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            hash_errors = verify_packet_hashes(p, manifest)
            if hash_errors:
                raise ValueError(f"Hash verification failed for {p.name}: {hash_errors}")

            if "review" in p.name or (p / "candidate-rankings.jsonl").exists():
                review_only_series.append(
                    {
                        "packet": p.name,
                        "series_id": manifest.get("series_id"),
                        "reason": "review_only_unresolved_source_notes",
                    }
                )
                continue

            rankings_path = p / "rankings.jsonl"
            if not rankings_path.exists():
                skipped_packets.append({"packet": p.name, "reason": "no_rankings_jsonl"})
                continue

            rows = [
                _normalize_row(json.loads(line), p.name)
                for line in rankings_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            by_series: dict[str, list[dict[str, Any]]] = {}
            for r in rows:
                by_series.setdefault(r["series_id"], []).append(r)

            for series_id, srows in by_series.items():
                identity_key_count = len({r["song_id"] for r in srows})
                ranks = [r["position"] for r in srows]
                ties = sorted({r for r in ranks if ranks.count(r) > 1})
                evidence_status = manifest.get("evidence_status") or manifest.get("status")
                manifest_series = None
                for manifest_series in manifest.get("series") or []:
                    if manifest_series.get("series_id") == series_id:
                        evidence_status = manifest_series.get("status") or evidence_status
                        break
                else:
                    manifest_series = None
                evidence_status = evidence_status or "primary_source_verified"
                declared_depth = (
                    manifest_series.get("reported_depth") if manifest_series else None
                )
                if declared_depth is None:
                    reported_depth = None
                elif isinstance(declared_depth, int) and not isinstance(declared_depth, bool):
                    reported_depth = declared_depth
                elif isinstance(declared_depth, str) and declared_depth.isdecimal():
                    reported_depth = int(declared_depth)
                else:
                    raise ValueError(
                        f"invalid reported chart depth in {p.name}/{series_id}: "
                        f"{declared_depth!r}"
                    )
                if reported_depth is not None and reported_depth < max(ranks, default=0):
                    raise ValueError(
                        f"reported chart depth {reported_depth} is below an observed rank "
                        f"in {p.name}/{series_id}"
                    )
                observed_rank_count = (
                    manifest_series.get("observed_ranked_entries")
                    if manifest_series
                    else None
                )
                if observed_rank_count is not None and int(observed_rank_count) != len(srows):
                    raise ValueError(
                        f"observed rank count disagrees with rows in {p.name}/{series_id}"
                    )
                unobserved_positions = (
                    sorted(set(range(1, reported_depth + 1)) - set(ranks))
                    if reported_depth is not None
                    else None
                )
                published_ties_or_gaps = (
                    manifest_series.get("ties_or_gaps_as_published", [])
                    if manifest_series
                    else []
                )
                published_missing_positions = (
                    manifest_series.get("missing_positions", []) if manifest_series else []
                )
                published_depth_conflict = (
                    manifest.get("published_depth_conflict")
                    or (manifest_series.get("published_depth_conflict") if manifest_series else None)
                )
                conn.execute(
                    """
                    INSERT INTO supplemental_series VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        series_id,
                        p.name,
                        srows[0]["provider_code"],
                        srows[0]["chart_family"],
                        srows[0]["reporting_year"],
                        srows[0]["publisher_country_code"],
                        srows[0]["chart_market_code"],
                        reported_depth,
                        len(srows),
                        identity_key_count,
                        json.dumps(
                            {
                                "tied_ranks": ties,
                                "published_ties_or_gaps": published_ties_or_gaps,
                                "missing_positions": published_missing_positions,
                                "observed_positions": sorted(ranks),
                                "unobserved_positions": unobserved_positions,
                                "published_depth_conflict": published_depth_conflict,
                            }
                        ),
                        evidence_status,
                        json.dumps(manifest, ensure_ascii=False),
                    ),
                )
                for r in srows:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO supplemental_songs VALUES (?,?,?,?,?,?,?)
                        """,
                        (
                            r["song_id"],
                            r["title"],
                            r["artist_credit"],
                            r["provider_code"],
                            r["native_song_id"],
                            json.dumps(r["version_tags"], ensure_ascii=False),
                            json.dumps(r["featured_artists"], ensure_ascii=False),
                        ),
                    )
                    conn.execute(
                        """
                        INSERT INTO supplemental_memberships VALUES (?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            r["membership_id"],
                            r["series_id"],
                            r["song_id"],
                            r["position"],
                            r["published_rank"],
                            r["score"],
                            r["native_metric"],
                            r["source_url"],
                            r["source_sha256"],
                            json.dumps(r["raw"], ensure_ascii=False),
                        ),
                    )
                imported_series.append(
                    {
                        "series_id": series_id,
                        "packet": p.name,
                        "provider_code": srows[0]["provider_code"],
                        "reporting_year": srows[0]["reporting_year"],
                        "publisher_country_code": srows[0]["publisher_country_code"],
                        "chart_market_code": srows[0]["chart_market_code"],
                        "reported_depth": reported_depth,
                        "imported_positions": len(srows),
                        "normalized_identity_keys": identity_key_count,
                        "evidence_status": evidence_status,
                        "tied_ranks": ties,
                        "published_ties_or_gaps": published_ties_or_gaps,
                        "missing_positions": published_missing_positions,
                        "observed_positions": sorted(ranks),
                        "unobserved_positions": unobserved_positions,
                        "published_depth_conflict": published_depth_conflict,
                    }
                )

    total_positions = sum(s["imported_positions"] for s in imported_series)
    total_reported_depth = sum(s["reported_depth"] or 0 for s in imported_series)
    reported_depth_unknown_series = sum(s["reported_depth"] is None for s in imported_series)
    total_identity_keys = conn.execute("SELECT count(*) FROM supplemental_songs").fetchone()[0]
    conn.close()
    return {
        "schema_version": "supplemental-series-denominators-v3",
        "merged_into_150k_spotify_youtube_selection": False,
        "series_count": len(imported_series),
        "total_supplemental_positions": total_positions,
        "total_reported_chart_depth": total_reported_depth,
        "reported_depth_unknown_series": reported_depth_unknown_series,
        "total_normalized_identity_keys": total_identity_keys,
        "identity_key_definition": (
            "Provider-native IDs where available; otherwise normalized provider, title, "
            "artist credit, and version tags. These keys are not adjudicated canonical songs."
        ),
        "series": imported_series,
        "review_only_series": review_only_series,
        "skipped_packets": skipped_packets,
    }
