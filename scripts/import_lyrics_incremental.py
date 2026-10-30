"""Import complete appended lyric records in bounded batches, with durable resume."""

import argparse
import json
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from chart_observatory.config import Settings
from chart_observatory.lyrics.legacy_corpus_import import import_legacy_api_lyrics

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/derived/lyrics/gemini_annotations.jsonl"


def write_state(path, state):
    temporary = path.with_suffix(".part")
    temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
    for attempt in range(6):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(0.05 * 2**attempt)


def read_complete_batch(path, offset, limit=500):
    """Never consume a record until its terminating newline has been written."""
    lines = []
    with path.open("rb") as handle:
        handle.seek(offset)
        for _ in range(limit):
            line = handle.readline()
            if not line.endswith(b"\n"):
                break
            lines.append(line)
            offset = handle.tell()
    return b"".join(lines), offset


def import_next(engine, source, checkpoint):
    state = json.loads(checkpoint.read_text(encoding="utf-8")) if checkpoint.exists() else {}
    stat = source.stat()
    identity = {"source": str(source.resolve()), "inode": stat.st_ino}
    if state and any(state.get(key) != value for key, value in identity.items()):
        raise ValueError("Source identity changed; checkpoint requires review")
    offset = state.get("offset", 0)
    if stat.st_size < offset:
        raise ValueError("Source truncated; checkpoint requires review")
    content, end = read_complete_batch(source, offset)
    if not content:
        return False
    chunk = checkpoint.with_suffix(".batch.jsonl")
    chunk.write_bytes(content)
    try:
        with Session(engine) as session:
            summary = import_legacy_api_lyrics(session, chunk)
        # The importer commits before the checkpoint advances. Replays are idempotent.
        write_state(
            checkpoint,
            {
                **identity,
                "offset": end,
                "documents_inserted": state.get("documents_inserted", 0)
                + summary.documents_inserted,
                "updated_at": datetime.now(UTC).isoformat(),
                "last_batch": asdict(summary),
            },
        )
    finally:
        chunk.unlink(missing_ok=True)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--follow", action="store_true")
    args = parser.parse_args()
    source = args.input.resolve()
    checkpoint = source.with_suffix(".import-checkpoint.json")
    pause = source.with_suffix(".import-pause")
    engine = create_engine(Settings.load(ROOT).database_url, connect_args={"connect_timeout": 5})
    try:
        while not pause.exists():
            try:
                if import_next(engine, source, checkpoint):
                    continue
            except (SQLAlchemyError, OSError) as error:
                # No exception text: connection URLs can contain credentials.
                print(
                    json.dumps({"status": "RETRY_IMPORT", "error": type(error).__name__}),
                    flush=True,
                )
                if not args.follow:
                    raise SystemExit(1) from None
            if not args.follow:
                break
            time.sleep(60)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
