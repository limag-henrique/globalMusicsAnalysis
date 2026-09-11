"""Lyrics backfill pipeline — scrape missing lyrics from multiple sources and annotate with Gemini.

Usage:
    python -m chart_observatory.lyrics.lyrics_backfill [options]

Reads songs with ``lyrics_status: MISSING`` from ``gemini_annotations.jsonl``,
tries Genius → Letras.mus.br → Lyrics.ovh → LRCLIB in cascade, and when found,
sends the lyrics to Gemini for English translation and semantic analysis.

Results are written **in-place** back to ``gemini_annotations.jsonl``, replacing
the MISSING entries with FOUND entries. A timestamped backup is created first.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

# Force UTF-8 output on Windows (cp1252 can't handle Korean, Arabic, etc.)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx

from chart_observatory.lyrics.gemini_pipeline import (
    GeminiAnnotationClient,
    GeminiApiError,
    LrclibClient,
    LyricsOvhClient,
    throttle,
)
from chart_observatory.lyrics.genius_client import GeniusClient
from chart_observatory.lyrics.letras_client import LetrasClient


# ── Defaults ─────────────────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_JSONL = _PROJECT_ROOT / "data" / "derived" / "lyrics" / "gemini_annotations.jsonl"

_THROTTLE_SCRAPE = 1.5   # seconds between scrape requests
_THROTTLE_GEMINI = 2.0   # seconds between Gemini API calls


# ── Env loading ──────────────────────────────────────────────────────────────

def _load_dotenv(env_path: Path | None = None) -> None:
    """Minimal .env loader — no external dependency needed."""
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


# ── Source registry ──────────────────────────────────────────────────────────

def _build_sources(
    genius_token: str | None = None,
) -> list[tuple[str, Any]]:
    """Build ordered list of (source_name, client) for cascading lookup."""
    http = httpx.Client(timeout=30.0, follow_redirects=True)
    sources: list[tuple[str, Any]] = [
        ("GENIUS", GeniusClient(access_token=genius_token, http_client=http)),
        ("LETRAS", LetrasClient(http_client=http)),
        ("LYRICS_OVH", LyricsOvhClient(http_client=http)),
        ("LRCLIB", LrclibClient(http_client=http)),
    ]
    return sources


def _fetch_from_source(
    source_name: str, client: Any, title: str, artist: str,
) -> tuple[str | None, dict[str, Any]]:
    """Try fetching lyrics from a single source. Returns (lyrics, metadata)."""
    try:
        if source_name == "LRCLIB":
            result = client.fetch(title, artist)
            if result is None:
                return None, {}
            lyrics, meta = result
            return lyrics, meta
        else:
            lyrics = client.fetch(title, artist)
            return lyrics, {}
    except Exception as exc:
        print(f"         [!] {source_name} error: {exc}")
        return None, {}


# ── JSONL I/O ────────────────────────────────────────────────────────────────

def _load_all_entries(path: Path) -> list[dict[str, Any]]:
    """Load every line of the JSONL as a dict."""
    entries: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def _write_all_entries(path: Path, entries: list[dict[str, Any]]) -> None:
    """Overwrite the JSONL with the full list of entries."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _backup(path: Path) -> Path:
    """Create a timestamped backup of the file."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_suffix(f".backup_{ts}.jsonl")
    shutil.copy2(path, backup)
    return backup


# ── Core pipeline ────────────────────────────────────────────────────────────

def run_backfill(
    jsonl_path: Path = _DEFAULT_JSONL,
    genius_token: str | None = None,
    gemini_key: str | None = None,
    gemini_model: str = "gemini-3.8-flash",
    limit: int | None = None,
    dry_run: bool = False,
    skip_gemini: bool = False,
) -> dict[str, int]:
    """Run the full backfill pipeline in-place on the JSONL.

    Returns a dict with counters: found, still_missing, errors, skipped.
    """
    # Load .env for API keys
    _load_dotenv()

    # Resolve API keys
    genius_token = genius_token or os.environ.get("GENIUS") or os.environ.get("GENIUS_ACCESS_TOKEN")
    gemini_key = gemini_key or os.environ.get("GEMINI") or os.environ.get("GEMINI_API_KEY")

    # Load all entries
    entries = _load_all_entries(jsonl_path)
    total_entries = len(entries)

    # Find MISSING indices
    missing_indices: list[int] = [
        i for i, e in enumerate(entries)
        if isinstance(e, dict) and e.get("lyrics_status") == "MISSING"
    ]

    if limit:
        missing_indices = missing_indices[:limit]

    total = len(missing_indices)

    print(f"\n{'='*60}")
    print(f"  LYRICS BACKFILL PIPELINE")
    print(f"  Total entries in JSONL: {total_entries}")
    print(f"  Songs MISSING to process: {total}")
    print(f"  File: {jsonl_path}")
    print(f"  Dry run: {dry_run}")
    print(f"  Skip Gemini: {skip_gemini}")
    print(f"  Genius token: {'YES' if genius_token else 'NO (HTML scraping only)'}")
    print(f"{'='*60}\n")

    if total == 0:
        print("  Nothing to do -- no MISSING entries found.")
        return {"found": 0, "still_missing": 0, "errors": 0, "skipped": 0}

    # Backup before modifying
    if not dry_run:
        backup_path = _backup(jsonl_path)
        print(f"  Backup created: {backup_path.name}")

    # Build source clients
    sources = _build_sources(genius_token)
    source_names = [name for name, _ in sources]
    print(f"  Sources: {' -> '.join(source_names)}")

    # Build Gemini client (if needed)
    gemini: GeminiAnnotationClient | None = None
    if not skip_gemini and not dry_run:
        if gemini_key:
            gemini = GeminiAnnotationClient(api_key=gemini_key, model=gemini_model)
            print(f"  Gemini model: {gemini_model}")
        else:
            print("  [!] No Gemini API key -- lyrics will be saved without analysis")

    print()

    # Counters
    stats = {"found": 0, "still_missing": 0, "errors": 0, "skipped": 0}
    modified = False

    for seq, idx in enumerate(missing_indices, 1):
        entry = entries[idx]
        song_id = entry.get("song_id", "???")
        title = entry.get("title", "Unknown")
        artist = entry.get("artist", "Unknown")
        progress = f"[{seq}/{total}]"

        print(f"  {progress} Searching: {artist} - {title}")

        # Try each source in cascade
        found_lyrics: str | None = None
        found_source: str | None = None
        found_meta: dict[str, Any] = {}

        for source_name, client in sources:
            lyrics, meta = _fetch_from_source(source_name, client, title, artist)
            if lyrics:
                found_lyrics = lyrics
                found_source = source_name
                found_meta = meta
                print(f"         [OK] Found on {source_name} ({len(lyrics)} chars)")
                break
            throttle(_THROTTLE_SCRAPE)

        if dry_run:
            if found_lyrics:
                stats["found"] += 1
                print(f"         [DRY RUN] Would save from {found_source}")
            else:
                stats["still_missing"] += 1
                print(f"         [X] Not found on any source")
            continue

        if found_lyrics and found_source:
            # Build the updated record, preserving existing fields
            updated: dict[str, Any] = {
                "song_id": song_id,
                "title": title,
                "artist": artist,
                "lyrics_status": "FOUND",
                "lyrics_source": found_source,
                "source_metadata": found_meta,
                "original_lyrics": found_lyrics,
                "gemini_model": gemini_model,
            }

            # Annotate with Gemini if available
            if gemini:
                try:
                    throttle(_THROTTLE_GEMINI)
                    analysis = gemini.annotate(
                        song_id=song_id,
                        title=title,
                        artist=artist,
                        lyrics=found_lyrics,
                    )
                    updated["analysis"] = analysis
                    print(f"         [OK] Gemini analysis complete")
                except GeminiApiError as exc:
                    print(f"         [!] Gemini error: {exc}")
                    stats["errors"] += 1
                except Exception as exc:
                    print(f"         [!] Gemini unexpected error: {exc}")
                    stats["errors"] += 1

            # Replace entry in-place
            entries[idx] = updated
            modified = True
            stats["found"] += 1

            # Incremental save every 10 found songs (crash safety)
            if stats["found"] % 10 == 0:
                _write_all_entries(jsonl_path, entries)
                print(f"         [SAVE] Incremental save ({stats['found']} found so far)")
        else:
            stats["still_missing"] += 1
            print(f"         [X] Not found on any source")

    # Final write
    if modified and not dry_run:
        _write_all_entries(jsonl_path, entries)

    # Summary
    print(f"\n{'='*60}")
    print(f"  BACKFILL COMPLETE")
    print(f"  Found:   {stats['found']}")
    print(f"  Missing: {stats['still_missing']}")
    print(f"  Errors:  {stats['errors']}")
    print(f"{'='*60}\n")

    return stats


# ── CLI entrypoint ───────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill missing lyrics from Genius, Letras.mus.br, and more."
    )
    parser.add_argument(
        "--input", "-i",
        type=Path,
        default=_DEFAULT_JSONL,
        help="JSONL file with song metadata (default: gemini_annotations.jsonl)",
    )
    parser.add_argument(
        "--genius-token",
        default=None,
        help="Genius API access token (or set GENIUS env var)",
    )
    parser.add_argument(
        "--gemini-key",
        default=None,
        help="Gemini API key (or set GEMINI env var)",
    )
    parser.add_argument(
        "--gemini-model",
        default="gemini-3.8-flash",
        help="Gemini model to use for analysis",
    )
    parser.add_argument(
        "--limit", "-n",
        type=int,
        default=None,
        help="Limit number of songs to process (for testing)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Search only -- don't write results or call Gemini",
    )
    parser.add_argument(
        "--skip-gemini",
        action="store_true",
        help="Save found lyrics without Gemini analysis",
    )

    args = parser.parse_args()

    run_backfill(
        jsonl_path=args.input,
        genius_token=args.genius_token,
        gemini_key=args.gemini_key,
        gemini_model=args.gemini_model,
        limit=args.limit,
        dry_run=args.dry_run,
        skip_gemini=args.skip_gemini,
    )


if __name__ == "__main__":
    main()
