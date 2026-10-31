"""One-owner overnight download, annual recomputation and quota import; no Gemini."""

import json
import msvcrt
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "data/runtime/overnight-chart-import-20261030"
DERIVED = ROOT / "data/derived/annual_revision/backfill-2018-2026-20261030"


def save_status(status, **details):
    payload = dict(status=status, pid=os.getpid(), observed_at=datetime.now(UTC).isoformat(),
                   start_year=2018, end_year=2026, cutoff="2026-10-15", paid_calls=0, **details)
    part = STATE / "status.part"
    part.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    part.replace(STATE / "status.json")


def run_stage(stage, arguments, log):
    save_status("running", stage=stage)
    result = subprocess.run([sys.executable, "-u", *arguments], cwd=ROOT,
                            stdout=log, stderr=subprocess.STDOUT, check=False)
    if result.returncode:
        raise RuntimeError(f"{stage} failed with exit code {result.returncode}")


def main():
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / "owner.lock").open("a+b") as owner, (STATE / "execution.log").open("ab") as log:
        owner.seek(0)
        if not owner.read(1):
            owner.write(b"0")
            owner.flush()
        owner.seek(0)
        msvcrt.locking(owner.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            os.environ["PYTHONIOENCODING"] = "utf-8"
            os.environ["POLARS_MAX_THREADS"] = "2"
            save_status("running", stage="downloads")
            children = [subprocess.Popen(
                [sys.executable, "-u", "scripts/download_historical_charts.py", "--source", source],
                cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
            ) for source in ("zenodo", "kaggle")]
            while any(child.poll() is None for child in children):
                save_status("running", stage="downloads", child_pids=[c.pid for c in children],
                            child_returncodes=[c.poll() for c in children])
                time.sleep(15)
            if any(c.returncode for c in children):
                raise RuntimeError("a public archive download failed; partial downloads preserved")
            source = DERIVED / "sources"
            run_stage("annual_recomputation", ["scripts/build_historical_backfill.py",
                      "--include-kaggle", "--output", str(source)], log)
            selected = DERIVED / "selection"
            args = ["scripts/prepare_quota_import.py", "--source", str(source),
                    "--output", str(selected), "--start-year", "2018", "--end-year", "2026",
                    "--metadata-only-overflow", "--apply"]
            if (selected / "manifest.json").exists():
                args.append("--prepared")
            run_stage("quota_import", args, log)
            coverage = [json.loads(line) for line in
                        (selected / "coverage.jsonl").read_text(encoding="utf-8").splitlines()]
            manifest = json.loads((selected / "manifest.json").read_text(encoding="utf-8"))
            summary = dict(
                candidate_identities=manifest["candidate_identities"],
                selected_memberships=manifest["selected_memberships"], cells=len(coverage),
                country_year_deficits=[r for r in coverage if r["quota_shortfall"]],
                pending_cells=sum(r["quota_shortfall"] > 0 for r in coverage),
                complete_annual_cells=sum(r["status"] == "CALENDAR_ELIGIBLE" for r in coverage),
                partial_2026_cells=sum(r["status"] == "PARTIAL_YEAR" for r in coverage),
                selection_directory=str(selected), classification_ready=False,
            )
            (STATE / "result.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
            save_status("completed_with_deficits" if summary["pending_cells"] else "completed",
                        stage="finished", summary=summary)
        except Exception as exc:
            save_status("failed", error=str(exc))
            raise
        finally:
            owner.seek(0)
            msvcrt.locking(owner.fileno(), msvcrt.LK_UNLCK, 1)


if __name__ == "__main__":
    main()
