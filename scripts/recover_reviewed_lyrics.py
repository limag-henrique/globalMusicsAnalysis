"""Resume conventional acquisition of review/audit targets; never promote candidates."""

import argparse
import json
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from itertools import islice
from pathlib import Path
from uuid import uuid4

import httpx

from chart_observatory.lyrics.recovery_web import CachedRecoveryHTTP, recover_candidate
from chart_observatory.lyrics.review_evidence import import_comparison_export


def read_recovery_ledger(path):
    if not path.exists():
        return []
    raw = path.read_bytes()
    rows, offset = [], 0
    lines = raw.splitlines(keepends=True)
    for number, line in enumerate(lines):
        if number == len(lines) - 1 and not line.endswith(b"\n"):
            backup = path.with_name(path.name + f".interrupted-{uuid4()}")
            backup.write_bytes(raw)
            temporary = path.with_suffix(".resume.tmp")
            temporary.write_bytes(raw[:offset])
            temporary.replace(path)
            break
        if line.strip():
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError("recovery ledger row must be an object")
            rows.append(row)
        offset += len(line)
    return rows


def bounded_results(pool, acquire, rows, workers):
    iterator = iter(rows)
    pending = {pool.submit(acquire, row) for row in islice(iterator, workers)}
    try:
        while pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                yield future.result()
                row = next(iterator, None)
                if row is not None:
                    pending.add(pool.submit(acquire, row))
    finally:
        for future in pending:
            future.cancel()


def select_recovery_targets(rows, completed, limit):
    groups = {}
    for row in rows:
        if not all(isinstance(row.get(key), str) and row[key].strip()
                   for key in ("title", "artist")):
            continue
        binding = {"document_id": row["document_id"], "lyrics_hash": row["lyrics_hash"]}
        if (binding["document_id"], binding["lyrics_hash"]) in completed:
            continue
        identity = row.get("track_id") or row.get("recording_id") or row["document_id"]
        key = (identity, row["lyrics_hash"])
        group = groups.setdefault(key, {**row, "original_bindings": []})
        if binding not in group["original_bindings"]:
            group["original_bindings"].append(binding)
    return list(groups.values())[:limit]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviews", type=Path)
    parser.add_argument("--targets-jsonl", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--refresh", action="store_true", help="Replay cached successful lookups")
    parser.add_argument(
        "--all-sources", action="store_true", help="Retain both provider candidates",
    )
    parser.add_argument(
        "--cache-dir", type=Path, help="Reuse raw response cache across bounded runs",
    )
    parser.add_argument("--discover-google", action="store_true", help="Discover source URLs only")
    args = parser.parse_args()
    if bool(args.reviews) == bool(args.targets_jsonl):
        parser.error("choose exactly one input")
    if args.limit < 1 or not 1 <= args.workers <= 8:
        parser.error("positive limit and 1..8 workers required")
    rows = import_comparison_export(args.reviews) if args.reviews else [
        json.loads(line) for line in args.targets_jsonl.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger = args.output_dir / "acquisition.jsonl"
    completed = set()
    for item in read_recovery_ledger(ledger):
        if (
            item["status"] != "http_error" and not args.refresh
            and (not args.all_sources or item.get("lookup_mode") == "all_sources")
        ):
            bindings = item.get("original_bindings") or [{
                "document_id": item["original_document_id"],
                "lyrics_hash": item["original_lyrics_hash"],
            }]
            completed.update((b["document_id"], b["lyrics_hash"]) for b in bindings)
    selected = select_recovery_targets(rows, completed, args.limit)
    with httpx.Client(
        timeout=15, headers={"User-Agent": "ChartObservatory/0.1 lyrics audit"}
    ) as client:
        http = CachedRecoveryHTTP(args.cache_dir or args.output_dir / "http-cache", client)

        def acquire(row):
            try:
                result = recover_candidate(
                    row["title"], row["artist"], http, collect_all=args.all_sources,
                    discover_google=args.discover_google,
                )
            except httpx.HTTPError as exc:
                result = {"status": "http_error", "title": row["title"],
                          "artist": row["artist"], "error_type": type(exc).__name__}
            return {**result, "original_document_id": row["document_id"],
                    "original_lyrics_hash": row["lyrics_hash"],
                    "original_bindings": row["original_bindings"],
                    "track_id": row.get("track_id"),
                    "recording_id": row.get("recording_id"),
                    "chart_bindings": row.get("chart_bindings", []),
                    "cohort_version": row.get("cohort_version"),
                    "identity_status": row.get("identity_status")}

        with (
            ThreadPoolExecutor(max_workers=args.workers) as pool,
            ledger.open("a", encoding="utf-8") as handle,
        ):
            for result in bounded_results(pool, acquire, selected, args.workers):
                handle.write(json.dumps(result, ensure_ascii=False) + "\n")
                handle.flush()
                print(json.dumps({k: result[k] for k in ("title", "status")}), flush=True)


if __name__ == "__main__":
    main()
