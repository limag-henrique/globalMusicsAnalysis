"""Resume acquisition of every known missing ranked lyric in country/rank order."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import UTC, datetime
from pathlib import Path

import httpx
from verify_prioritized_corpus import initialize, load_inputs, priorities, verify

from chart_observatory.final_pipeline import catalog, encode, save
from chart_observatory.lyrics.quota_acquisition import AcquisitionStore, PacedHTTP
from chart_observatory.lyrics.quota_discovery import recover_with_fallback
from chart_observatory.lyrics.recovery_pipeline import (
    apply_native_proof_to_record,
    load_native_spotify_proofs,
)
from chart_observatory.research_flow import load_selection

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=3, choices=range(1, 5))
    parser.add_argument("--selection", type=Path)
    parser.add_argument(
        "--stage",
        action="append",
        default=[],
        metavar="DATABASE|RUN_ID",
        help="Override configured staging inputs; repeat once per immutable staging run.",
    )
    parser.add_argument("--cache", action="append", default=[], type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to(ROOT / "data/runtime"):
        raise ValueError("output must remain in runtime")
    out.mkdir(parents=True, exist_ok=True)
    config = json.loads((ROOT / "config/final_pipeline.json").read_text())
    stages = config["staging"]
    if args.stage:
        stages = []
        for value in args.stage:
            database, separator, run_id = value.partition("|")
            if not separator or not database or not run_id:
                parser.error("--stage must be DATABASE|RUN_ID")
            stages.append(dict(database=database, run_id=run_id))
    selection = (args.selection or (ROOT / config["population_selection"])).resolve()
    _, _, selection_rows, _ = load_selection(selection)
    jobs, members = load_inputs(
        ROOT / "data/runtime/final-pipeline/catalog.sqlite",
        stages,
        selection_rows=selection_rows,
        selection_scope=selection,
    )
    policy = str(selection)
    priority, scope = priorities(members)
    if policy:
        summary = json.loads((ROOT / policy / "allocation-summary.json").read_text())
        country_order = {
            country: index for index, country in enumerate(summary["priority_countries"])
        }
        priority = {}
        for _, country, year, platform, rank, cid in members:
            key = (country_order[country], rank, year, country, platform, cid)
            priority[cid] = min(key, priority.get(cid, key))
    selected = [
        key
        for key in sorted(jobs, key=lambda k: priority.get(k, (2, k)))
        if not jobs[key][2].get("text_sha256")
    ]
    import gzip

    proof_file = out / "native-proof-snapshot.json.gz"
    if not proof_file.exists():
        proof_file.write_bytes(
            gzip.compress(encode(load_native_spotify_proofs(ROOT)).encode(), mtime=0)
        )
    initialize(str(proof_file))
    proofs = json.loads(gzip.decompress(proof_file.read_bytes()))
    for cid in selected:
        import copy

        candidate = copy.deepcopy(jobs[cid][1])
        native_ok, flags, _ = apply_native_proof_to_record(cid, candidate, None, proofs)
        if native_ok and not flags:
            jobs[cid][1] = candidate
    cache_sources = [Path(s) / "http-cache" for s in config["stores"]]
    cache_sources.extend(path.resolve() for path in args.cache)
    cache_sources.extend(
        (Path(stage["database"]).resolve().parent.parent / "http-cache") for stage in stages
    )
    with catalog(out / "control"):
        store = AcquisitionStore(out)
        for cid in selected:
            store.enqueue(cid, jobs[cid][1])
        # The OS lock establishes that these running tasks belong to an interrupted own run.
        with store.conn:
            store.conn.execute("UPDATE tasks SET status='pending' WHERE status='running'")
        completed = 0
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            http = PacedHTTP(out / "http-cache", client, cache_sources=cache_sources, interval=1.0)

            def acquire(cid):
                payload = jobs[cid][1]
                try:
                    result = recover_with_fallback(
                        payload["title"],
                        payload["artist"],
                        http,
                        first_time=True,
                        metadata_resolution=payload.get("metadata_resolution"),
                    )
                except Exception as exc:
                    result = dict(status="acquisition_error", error_type=type(exc).__name__)
                return cid, result

            iterator = iter(selected)
            pending = {}
            with ThreadPoolExecutor(max_workers=args.workers) as pool:

                def schedule():
                    for cid in iterator:
                        if store.claim(cid):
                            pending[pool.submit(acquire, cid)] = cid
                            return True
                    return False

                for _ in range(args.workers):
                    schedule()
                while pending:
                    done, _ = wait(pending, timeout=15, return_when=FIRST_COMPLETED)
                    for future in done:
                        cid, result = future.result()
                        del pending[future]
                        store.finish(cid, result)
                        saved = json.loads(
                            store.conn.execute(
                                "SELECT result FROM tasks WHERE identity=?", (cid,)
                            ).fetchone()[0]
                        )
                        decision = verify((cid, jobs[cid][1], saved))
                        decisions = out / "verification"
                        decisions.mkdir(exist_ok=True)
                        from chart_observatory.final_pipeline import digest

                        save(decisions / (digest(cid.encode()) + ".json"), decision)
                        completed += 1
                        schedule()
                    status = dict(
                        stage="acquiring" if pending else "completed",
                        target_songs=len(selected),
                        completed_this_run=completed,
                        statuses=store.summary(),
                        priority_scope=scope,
                        paid_calls=0,
                        updated_at=datetime.now(UTC).isoformat(),
                    )
                    save(out / "status.json", status)
                    if done:
                        print(encode(status), flush=True)
        store.conn.close()


if __name__ == "__main__":
    main()
