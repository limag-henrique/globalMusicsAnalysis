"""Start the frozen popularity-first queue, preserving the previous acquisition log."""

import argparse
import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cohort: Path, previous: Path):
    cohort, previous = cohort.resolve(), previous.resolve()
    if not cohort.is_relative_to(ROOT) or not previous.is_relative_to(ROOT):
        raise ValueError("acquisition artifacts must remain inside the repository")
    manifest = json.loads((cohort / "manifest.json").read_text(encoding="utf-8"))
    if manifest["target_per_country_year"] != 80 or manifest["year_2026_included"]:
        raise ValueError("unexpected historical cohort protocol")
    output = cohort / "acquisition"
    output.mkdir(exist_ok=False)
    source = previous / "acquisition.jsonl"
    shutil.copy2(source, output / "acquisition.jsonl")
    command = [str(ROOT / ".venv/Scripts/python.exe"), "-u",
               str(ROOT / "scripts/recover_reviewed_lyrics.py"),
               "--targets-jsonl", str(cohort / "recovery-targets.jsonl"),
               "--output-dir", str(output), "--cache-dir", str(previous / "http-cache"),
               "--limit", str(manifest["unique_acquisition_targets"]),
               "--workers", "8", "--all-sources"]
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    with (output / "stdout.log").open("ab") as stdout, (output / "stderr.log").open("ab") as stderr:
        process = subprocess.Popen(
            command, cwd=ROOT, env=env, stdout=stdout, stderr=stderr,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    job = {"pid": process.pid, "started_at": datetime.now(UTC).isoformat(),
           "command": command, "cohort": str(cohort), "previous_ledger": str(source),
           "output": str(output), "status": "started", "gemini_calls": 0}
    (output / "process.json").write_text(json.dumps(job, indent=2), encoding="utf-8")
    print(json.dumps(job), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", required=True, type=Path)
    parser.add_argument("--previous", required=True, type=Path)
    args = parser.parse_args()
    run(args.cohort, args.previous)
