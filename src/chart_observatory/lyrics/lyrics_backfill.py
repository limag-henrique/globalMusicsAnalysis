"""Massive, resilient lyrics backfill engine for the entire music catalog.

Usage:
    python -m chart_observatory.lyrics.lyrics_backfill [options]

Features:
- Loads canonical tracks directly from ``data/derived/track_master.parquet`` (126,213 tracks)
- Optionally includes extra tracks from Kaggle observations (--include-all, 224k+ tracks)
- Cascades across Genius (API + HTML), Letras.mus.br, LRCLIB, and Lyrics.ovh
  with RapidFuzz validation
- High-quality sanitization of lyrics (no ads, no contributor tags, minimum length)
- Streaming thread-safe append to ``gemini_annotations.jsonl`` (never rewrites 100k+ rows)
- Strict deduplication: songs already recorded are skipped instantly on resume
- Multi-threaded worker pool with per-domain rate limiters
- Continuous non-stop execution with automatic error recovery
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from collections.abc import Mapping
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any, TypedDict, cast

# Force UTF-8 output on Windows (cp1252 can't handle Korean, Arabic, etc.)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx
import polars as pl

from chart_observatory.lyrics.gemini_pipeline import (
    GeminiAnnotationClient,
    LrclibClient,
    LyricsOvhClient,
    normalize_lookup_text,
)
from chart_observatory.lyrics.genius_client import GeniusClient
from chart_observatory.lyrics.letras_client import LetrasClient

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_TRACKS = _PROJECT_ROOT / "data" / "derived" / "track_master.parquet"
_KAGGLE_TRACKS = _PROJECT_ROOT / "data" / "normalized" / "kaggle_spotify_observations.parquet"
_DEFAULT_JSONL = _PROJECT_ROOT / "data" / "derived" / "lyrics" / "gemini_annotations.jsonl"
APPROVED_LYRICS_SOURCES = frozenset({"GENIUS", "LETRAS", "LRCLIB", "LYRICS_OVH"})


class AutomationStats(TypedDict):
    processed: int
    found: int
    missing: int
    errors: int
    by_source: dict[str, int]


def is_valid_lyrics_record(record: Mapping[str, Any]) -> bool:
    """Return whether a JSONL record is a successful, insertable lyric result."""
    if str(record.get("lyrics_status", "")).upper() != "FOUND":
        return False
    source = str(record.get("lyrics_source", "")).upper()
    if source not in APPROVED_LYRICS_SOURCES:
        return False
    lyrics = record.get("original_lyrics")
    return isinstance(lyrics, str) and bool(lyrics.strip())


def _load_dotenv(env_path: Path | None = None) -> None:
    path = env_path or _PROJECT_ROOT / ".env"
    if not path.exists():
        return
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = value


class DomainRateLimiter:
    """Thread-safe rate limiter ensuring minimum interval between calls per domain."""

    def __init__(self, min_interval_seconds: float) -> None:
        self.min_interval = min_interval_seconds
        self.last_call = 0.0
        self.lock = threading.Lock()

    def wait(self) -> None:
        if self.min_interval <= 0:
            return
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_call
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self.last_call = time.monotonic()


class LyricsEngine:
    """Thread-safe orchestrator for multi-source lyrics retrieval."""

    def __init__(
        self,
        genius_token: str | None = None,
        gemini_key: str | None = None,
        gemini_model: str = "gemini-3.8-flash",
        skip_gemini: bool = False,
    ) -> None:
        self.genius_token = genius_token
        self.gemini_key = gemini_key
        self.gemini_model = gemini_model
        self.skip_gemini = skip_gemini

        # Domain rate limiters
        self.rate_genius = DomainRateLimiter(0.8)
        self.rate_letras = DomainRateLimiter(0.8)
        self.rate_lrclib = DomainRateLimiter(0.3)
        self.rate_ovh = DomainRateLimiter(0.4)
        self.rate_gemini = DomainRateLimiter(1.5)

        # Reusable HTTP clients per thread
        self._local = threading.local()

    def _get_clients(self) -> dict[str, Any]:
        if not hasattr(self._local, "clients"):
            http = httpx.Client(timeout=25.0, follow_redirects=True)
            clients: dict[str, Any] = {
                "GENIUS": GeniusClient(access_token=self.genius_token, http_client=http),
                "LETRAS": LetrasClient(http_client=http),
                "LRCLIB": LrclibClient(http_client=http),
                "LYRICS_OVH": LyricsOvhClient(http_client=http),
            }
            if self.gemini_key and not self.skip_gemini:
                clients["GEMINI"] = GeminiAnnotationClient(
                    api_key=self.gemini_key,
                    model=self.gemini_model,
                    http_client=http,
                )
            else:
                clients["GEMINI"] = None
            self._local.clients = clients
        return cast(dict[str, Any], self._local.clients)

    def find_lyrics(self, title: str, artist: str) -> tuple[str | None, str | None, dict[str, Any]]:
        """Try cascading sources in order: Genius -> Letras -> LRCLIB -> Lyrics.ovh."""
        clients = self._get_clients()

        # 1. Genius
        self.rate_genius.wait()
        try:
            lyrics = clients["GENIUS"].fetch(title, artist)
            if lyrics:
                return lyrics, "GENIUS", {}
        except Exception:
            pass

        # 2. Letras.mus.br
        self.rate_letras.wait()
        try:
            lyrics = clients["LETRAS"].fetch(title, artist)
            if lyrics:
                return lyrics, "LETRAS", {}
        except Exception:
            pass

        # 3. LRCLIB
        self.rate_lrclib.wait()
        try:
            res = clients["LRCLIB"].fetch(title, artist)
            if res:
                lyrics, meta = res
                if lyrics:
                    return lyrics, "LRCLIB", meta
        except Exception:
            pass

        # 4. Lyrics.ovh
        self.rate_ovh.wait()
        try:
            lyrics = clients["LYRICS_OVH"].fetch(title, artist)
            if lyrics:
                return lyrics, "LYRICS_OVH", {}
        except Exception:
            pass

        return None, None, {}

    def annotate(self, song_id: str, title: str, artist: str, lyrics: str) -> dict[str, Any] | None:
        clients = self._get_clients()
        gemini = clients.get("GEMINI")
        if not gemini:
            return None

        # Up to 2 retries with backoff on 429 / network glitch
        for attempt in range(2):
            self.rate_gemini.wait()
            try:
                return cast(
                    dict[str, Any],
                    gemini.annotate(
                        song_id=song_id,
                        title=title,
                        artist=artist,
                        lyrics=lyrics,
                    ),
                )
            except Exception as exc:
                err_str = str(exc).lower()
                if "429" in err_str or "resourceexhausted" in err_str:
                    time.sleep(4.0 * (attempt + 1))
                else:
                    break
        return None


def _normalize_song_key(title: str, artist: str) -> tuple[str, str]:
    """Produce normalized lookup key for similarity matching & deduplication."""
    clean_artist = artist.split(",", 1)[0].split("&", 1)[0].strip()
    return (normalize_lookup_text(title), normalize_lookup_text(clean_artist))


def _load_completed(output_path: Path) -> tuple[set[str], set[tuple[str, str]]]:
    """Read IDs and keys only for valid lyric records in the JSONL output."""
    if not output_path.exists():
        return set(), set()
    completed_ids: set[str] = set()
    completed_keys: set[tuple[str, str]] = set()
    with output_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
                if not isinstance(item, dict) or not is_valid_lyrics_record(item):
                    continue
                sid = item.get("song_id")
                if sid:
                    completed_ids.add(str(sid))
                t = str(item.get("title") or "").strip()
                a = str(item.get("artist") or "").strip()
                if t:
                    completed_keys.add(_normalize_song_key(t, a))
            except json.JSONDecodeError:
                continue
    return completed_ids, completed_keys


def _load_tracks(
    tracks_path: Path,
    include_all: bool = True,
    completed_ids: set[str] | None = None,
    completed_keys: set[tuple[str, str]] | None = None,
    limit: int | None = None,
) -> list[dict[str, str]]:
    """Load tracks, filtering completed IDs and similar duplicate songs."""
    comp_ids = completed_ids or set()
    comp_keys = completed_keys or set()
    tracks_to_process: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    seen_keys: set[tuple[str, str]] = set()
    duplicates_filtered = 0

    # 1. Primary catalog: track_master.parquet
    print(f"  Loading primary track catalog from: {tracks_path.name}...")
    df = pl.read_parquet(tracks_path)
    for row in df.iter_rows(named=True):
        sid = str(row["canonical_track_id"])
        raw_title = str(row["title"] or "").strip()
        if not raw_title:
            continue
        artists_val = row["artist_names"]
        if isinstance(artists_val, (list, tuple)):
            raw_artist = ", ".join(str(v) for v in artists_val)
        else:
            raw_artist = str(artists_val or "")

        key = _normalize_song_key(raw_title, raw_artist)

        if sid in comp_ids or key in comp_keys or sid in seen_ids or key in seen_keys:
            duplicates_filtered += 1
            continue

        seen_ids.add(sid)
        seen_keys.add(key)
        tracks_to_process.append({"song_id": sid, "title": raw_title, "artist": raw_artist})

    # 2. Secondary catalog: Kaggle observations (if requested)
    if include_all and _KAGGLE_TRACKS.exists():
        print(f"  Loading extra unique tracks from: {_KAGGLE_TRACKS.name}...")
        df_kg = (
            pl.scan_parquet(_KAGGLE_TRACKS)
            .filter(pl.col("native_id").is_not_null() & pl.col("track_title").is_not_null())
            .select(
                pl.col("native_id").str.split("/").list.last().alias("canonical_track_id"),
                pl.col("track_title").alias("title"),
                pl.col("artist").alias("artist_names"),
            )
            .unique(subset=["canonical_track_id"])
            .collect()
        )
        for row in df_kg.iter_rows(named=True):
            sid = str(row["canonical_track_id"])
            raw_title = str(row["title"] or "").strip()
            if not raw_title:
                continue
            raw_artist = str(row["artist_names"] or "")

            key = _normalize_song_key(raw_title, raw_artist)

            if sid in comp_ids or key in comp_keys or sid in seen_ids or key in seen_keys:
                duplicates_filtered += 1
                continue

            seen_ids.add(sid)
            seen_keys.add(key)
            tracks_to_process.append({
                "song_id": sid,
                "title": raw_title,
                "artist": raw_artist,
            })

    print(f"  Deduplication complete: {duplicates_filtered} similar/duplicate songs removed.")
    print(f"  Total unique songs remaining to search: {len(tracks_to_process)}")

    if limit:
        tracks_to_process = tracks_to_process[:limit]

    return tracks_to_process


def run_full_automation(
    tracks_path: Path = _DEFAULT_TRACKS,
    output_path: Path = _DEFAULT_JSONL,
    workers: int = 6,
    limit: int | None = None,
    include_all: bool = True,
    skip_gemini: bool = False,
    genius_token: str | None = None,
    gemini_key: str | None = None,
    gemini_model: str = "gemini-3.8-flash",
) -> None:
    if workers < 1:
        raise ValueError("workers must be at least 1")

    _load_dotenv()
    genius_token = genius_token or os.environ.get("GENIUS") or os.environ.get("GENIUS_ACCESS_TOKEN")
    gemini_key = gemini_key or os.environ.get("GEMINI") or os.environ.get("GEMINI_API_KEY")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    completed_ids, completed_keys = _load_completed(output_path)

    tracks = _load_tracks(
        tracks_path=tracks_path,
        include_all=include_all,
        completed_ids=completed_ids,
        completed_keys=completed_keys,
        limit=limit,
    )
    total_tracks = len(tracks)

    print(f"\n{'='*65}")
    print("  MASSIVE ROOT LYRICS AUTOMATION ENGINE")
    print(
        f"  Already completed in JSONL: {len(completed_ids)} IDs "
        f"({len(completed_keys)} unique song titles)"
    )
    print(f"  Remaining tracks to process: {total_tracks}")
    print(f"  Output JSONL: {output_path}")
    print(f"  Workers: {workers}")
    print(f"  Genius Token: {'YES' if genius_token else 'NO'}")
    print(f"  Gemini Translation: {'DISABLED' if skip_gemini or not gemini_key else 'ENABLED'}")
    print(f"{'='*65}\n")

    if total_tracks == 0:
        print("  All tracks in the database are already verified! Nothing left to process.")
        return

    engine = LyricsEngine(
        genius_token=genius_token,
        gemini_key=gemini_key,
        gemini_model=gemini_model,
        skip_gemini=skip_gemini,
    )

    stats: AutomationStats = {
        "processed": 0,
        "found": 0,
        "missing": 0,
        "errors": 0,
        "by_source": {"GENIUS": 0, "LETRAS": 0, "LRCLIB": 0, "LYRICS_OVH": 0},
    }
    start_time = time.monotonic()

    def process_single_track(track: dict[str, str]) -> dict[str, Any] | None:
        sid = track["song_id"]
        title = track["title"]
        artist = track["artist"]

        lyrics, source, meta = engine.find_lyrics(title, artist)

        if lyrics and source:
            record: dict[str, Any] = {
                "song_id": sid,
                "title": title,
                "artist": artist,
                "lyrics_status": "FOUND",
                "lyrics_source": source,
                "source_metadata": meta,
                "original_lyrics": lyrics,
                "gemini_model": gemini_model,
            }
            if not skip_gemini and gemini_key:
                analysis = engine.annotate(sid, title, artist, lyrics)
                if analysis:
                    record["analysis"] = analysis
            return record
        return None

    # Open append-only file stream. Only valid FOUND records cross this boundary.
    with output_path.open("a", encoding="utf-8") as out_file, ThreadPoolExecutor(
        max_workers=workers
    ) as executor:
        future_to_track: dict[Any, dict[str, str]] = {}
        track_iter = iter(tracks)

        def submit_next() -> bool:
            try:
                track = next(track_iter)
            except StopIteration:
                return False
            future = executor.submit(process_single_track, track)
            future_to_track[future] = track
            return True

        for _ in range(min(workers, total_tracks)):
            submit_next()

        while future_to_track:
            completed, _ = wait(future_to_track, return_when=FIRST_COMPLETED)
            for future in completed:
                future_to_track.pop(future)
                stats["processed"] += 1
                try:
                    record = future.result()
                except Exception:
                    stats["errors"] += 1
                    record = None

                if record is not None and is_valid_lyrics_record(record):
                    out_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                    out_file.flush()
                    stats["found"] += 1
                    src = str(record["lyrics_source"])
                    stats["by_source"][src] = stats["by_source"].get(src, 0) + 1
                else:
                    stats["missing"] += 1

                submit_next()

            count = stats["processed"]
            if count % 10 == 0 or count == total_tracks or count <= 5:
                elapsed = time.monotonic() - start_time
                speed = (count / elapsed) * 60 if elapsed > 0 else 0
                remaining = total_tracks - count
                eta_minutes = (remaining / speed) if speed > 0 else 0
                found_pct = (stats["found"] / count) * 100

                print(
                    f"  [{count}/{total_tracks}] "
                    f"Found: {stats['found']} ({found_pct:.1f}%) | "
                    f"Not inserted: {stats['missing']} | "
                    f"Errors: {stats['errors']} | "
                    f"Speed: {speed:.1f} tracks/min | "
                    f"ETA: {eta_minutes:.1f} min"
                )

    elapsed_total = time.monotonic() - start_time
    print(f"\n{'='*65}")
    print("  AUTOMATION COMPLETE!")
    print(f"  Total Processed: {stats['processed']}")
    print(
        f"  Total Found:     {stats['found']} "
        f"({(stats['found'] / max(1, stats['processed'])) * 100:.1f}%)"
    )
    print(f"  Total Not Inserted: {stats['missing']}")
    print(f"  Total Errors:     {stats['errors']}")
    print(f"  Sources Breakdown: {stats['by_source']}")
    print(f"  Time Elapsed:    {elapsed_total/60:.1f} minutes")
    print(f"{'='*65}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Massive, resilient lyrics backfill for the entire database."
    )
    parser.add_argument(
        "--tracks", "-t",
        type=Path,
        default=_DEFAULT_TRACKS,
        help="Path to track_master.parquet (default: data/derived/track_master.parquet)",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=_DEFAULT_JSONL,
        help="Path to output JSONL file (default: data/derived/lyrics/gemini_annotations.jsonl)",
    )
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=6,
        help="Number of concurrent worker threads (default: 6)",
    )
    parser.add_argument(
        "--limit", "-n",
        type=int,
        default=None,
        help="Limit number of tracks to process in this run",
    )
    parser.add_argument(
        "--include-all",
        action="store_true",
        default=True,
        help="Include extra unique tracks from Kaggle observations (default: True)",
    )
    parser.add_argument(
        "--master-only",
        action="store_false",
        dest="include_all",
        help="Only search primary track_master.parquet without Kaggle extras",
    )
    parser.add_argument(
        "--skip-gemini",
        action="store_true",
        help=(
            "Skip Gemini English translation / semantic analysis, saving only "
            "verified original lyrics"
        ),
    )
    parser.add_argument(
        "--genius-token",
        default=None,
        help="Genius API access token (or set in .env)",
    )
    parser.add_argument(
        "--gemini-key",
        default=None,
        help="Gemini API key (or set in .env)",
    )
    parser.add_argument(
        "--gemini-model",
        default="gemini-3.8-flash",
        help="Gemini model name",
    )

    args = parser.parse_args()

    run_full_automation(
        tracks_path=args.tracks,
        output_path=args.output,
        workers=args.workers,
        limit=args.limit,
        include_all=args.include_all,
        skip_gemini=args.skip_gemini,
        genius_token=args.genius_token,
        gemini_key=args.gemini_key,
        gemini_model=args.gemini_model,
    )


if __name__ == "__main__":
    main()
