"""Pack Git data as CSV gzip snapshots; restore runtime files without Git LFS.

Run `python scripts/sync_git_data.py pack` before staging data changes.
Run `python scripts/sync_git_data.py restore` after cloning/pulling snapshots.
Runtime paths stay unchanged so existing importers and collectors keep working.
"""

import argparse
import csv
import gzip
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

csv.field_size_limit(64 * 1024 * 1024)
MANIFEST = "data/git-data-manifest.json"
JSONL = "data/derived/lyrics/gemini_annotations.jsonl"
MAX_BLOB = 95 * 1024 * 1024


def safe_path(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or relative.startswith(('/', '\\')):
        raise ValueError(f"Path outside repository: {relative}")
    return path


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_manifest(root):
    path = root / MANIFEST
    if not path.exists():
        return {"version": 1, "files": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data["version"] != 1:
        raise ValueError("Unsupported data manifest version")
    return data


def unpack(entry, root, destination):
    archive = safe_path(root, entry["archive"])
    if digest(archive) != entry["archive_sha256"]:
        raise ValueError(f"Archive checksum mismatch: {entry['archive']}")
    with destination.open("wb") as target:
        if entry["format"] == "csv":
            with gzip.open(archive, "rb") as source:
                shutil.copyfileobj(source, target)
        elif entry["format"] == "jsonl-record-csv":
            with gzip.open(archive, "rt", encoding="utf-8", newline="") as source:
                reader = csv.reader(source)
                if next(reader, None) != ["record_json"]:
                    raise ValueError("Invalid JSONL CSV header")
                for row in reader:
                    if len(row) != 1:
                        raise ValueError("Invalid JSONL CSV row")
                    target.write(row[0].encode("utf-8"))
        else:
            raise ValueError("Unknown snapshot format")
    if digest(destination) != entry["sha256"]:
        raise ValueError(f"Restored data checksum mismatch: {entry['source']}")


def pack(root, includes=()):
    root = root.resolve()
    previous = read_manifest(root)
    tracked = subprocess.check_output(
        ["git", "-C", str(root), "ls-files", "--cached", "--others",
         "--exclude-standard", "-z", "--", "*.csv"],
    ).decode("utf-8").split("\0")
    sources = sorted(set(filter(None, tracked)) | {e["source"] for e in previous["files"]})
    for relative in includes:
        if not relative.endswith(".csv"):
            raise ValueError("Explicit additions must be CSV files")
        safe_path(root, relative)
    sources = sorted(set(sources) | set(includes))
    if (root / JSONL).exists():
        sources = sorted(set(sources) | {JSONL})
    old = {entry["source"]: entry for entry in previous["files"]}
    entries = []
    for index, relative in enumerate(sources, 1):
        source = safe_path(root, relative)
        if not source.is_file():
            raise ValueError(f"Missing runtime data; restore first: {relative}")
        before = source.stat()
        sha = digest(source)
        if relative in old and sha == old[relative]["sha256"]:
            archive = safe_path(root, old[relative]["archive"])
            if archive.is_file() and digest(archive) == old[relative]["archive_sha256"]:
                entries.append(old[relative])
                continue
        archive_name = relative + ".gz" if relative.endswith(".csv") else relative + ".csv.gz"
        archive = safe_path(root, archive_name)
        if archive.exists() and relative not in old:
            raise ValueError(f"Refusing to overwrite existing archive: {archive_name}")
        temporary = archive.with_name(archive.name + ".part")
        try:
            with (
                temporary.open("wb") as raw,
                gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed,
            ):
                if relative.endswith(".csv"):
                    with source.open("rb") as data:
                        shutil.copyfileobj(data, compressed)
                    kind = "csv"
                else:
                    with io.TextIOWrapper(compressed, encoding="utf-8", newline="") as text:
                        writer = csv.writer(text)
                        writer.writerow(["record_json"])
                        with source.open(encoding="utf-8", newline="") as data:
                            for line in data:
                                # Preserve exact records, whitespace and newlines.
                                writer.writerow([line])
                    kind = "jsonl-record-csv"
            after = source.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ValueError(f"Source changed during compression; retry: {relative}")
            if temporary.stat().st_size >= MAX_BLOB:
                raise ValueError(f"Compressed file exceeds 95 MiB: {relative}")
            entry = {
                "source": relative, "archive": archive_name, "format": kind,
                "sha256": sha, "archive_sha256": digest(temporary),
                "bytes": before.st_size, "compressed_bytes": temporary.stat().st_size,
            }
            # Independently restore the new gzip before publishing it.
            entry_for_check = {**entry, "archive": temporary.relative_to(root).as_posix()}
            with tempfile.TemporaryDirectory() as temp:
                unpack(entry_for_check, root, Path(temp) / "restored")
            temporary.replace(archive)
            entries.append(entry)
        finally:
            temporary.unlink(missing_ok=True)
        if index % 100 == 0:
            print(f"Packed {index}/{len(sources)}", flush=True)
    manifest = root / MANIFEST
    manifest.parent.mkdir(parents=True, exist_ok=True)
    temporary = manifest.with_suffix(".json.part")
    temporary.write_text(json.dumps({"version": 1, "files": entries}, indent=2) + "\n")
    temporary.replace(manifest)
    print(json.dumps({
        "files": len(entries), "bytes": sum(e["bytes"] for e in entries),
        "compressed_bytes": sum(e["compressed_bytes"] for e in entries),
    }))


def restore(root, verify_only=False):
    root = root.resolve()
    entries = read_manifest(root)["files"]
    if not entries:
        raise ValueError("No data snapshots found")
    for entry in entries:
        destination = safe_path(root, entry["source"])
        if not verify_only and destination.exists():
            if digest(destination) != entry["sha256"]:
                raise ValueError(f"Local data differs; refusing to overwrite: {entry['source']}")
            continue
        with tempfile.TemporaryDirectory() as temp:
            restored = Path(temp) / "restored"
            unpack(entry, root, restored)
            if not verify_only:
                destination.parent.mkdir(parents=True, exist_ok=True)
                # Exclusive creation also protects files created by a running collector.
                with destination.open("xb") as output, restored.open("rb") as source:
                    shutil.copyfileobj(source, output)
    print(f"{'Verified' if verify_only else 'Restored'} {len(entries)} snapshots")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["pack", "restore", "verify"])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--include", action="append", default=[], help="New runtime CSV to export")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.command == "pack":
        pack(root, args.include)
    else:
        restore(root, verify_only=args.command == "verify")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1) from None
