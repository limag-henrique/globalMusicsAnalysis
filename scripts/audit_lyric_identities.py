"""Read-only collision audit; never merge different songs just because texts coincide."""

import json
import sqlite3
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from chart_observatory.lyrics.quota_acquisition import identity

ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "data/derived/lyrics/quota-20261030/acquisition.sqlite"
OUTPUT = ROOT / "data/derived/lyrics/quota-20261030/identity-audit"


def audit():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    hashes, missing = defaultdict(list), []
    with sqlite3.connect(f"file:{DATABASE.as_posix()}?mode=ro", uri=True) as conn:
        for key, payload, state, result in conn.execute(
            "SELECT identity,payload,status,result FROM tasks"
        ):
            p, r = json.loads(payload), json.loads(result) if result else {}
            binding = dict(
                identity=key,
                title=p.get("title"),
                artist=p.get("artist"),
                source=r.get("source"),
                status=state,
                chart_bindings=p.get("chart_bindings", []),
                text_path=r.get("text_path"),
            )
            if not identity(binding["title"]) or not identity(binding["artist"]):
                missing.append(binding)
            if r.get("text_sha256"):
                hashes[r["text_sha256"]].append(binding)
    collisions, targets = [], []
    for digest, bindings in hashes.items():
        if len({identity(row["title"]) for row in bindings}) > 1:
            collisions.append(
                dict(
                    text_sha256=digest,
                    bindings=bindings,
                    decision="recording_and_edition_review_required",
                )
            )
            targets.extend(
                {**row, "reason": "same_text_different_titles", "text_sha256": digest}
                for row in bindings
            )
    for name, values in (
        ("collisions", collisions),
        ("missing-metadata", missing),
        ("repair-targets", targets),
    ):
        part = OUTPUT / f"{name}.part"
        with part.open("w", encoding="utf-8") as handle:
            for row in values:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        part.replace(OUTPUT / f"{name}.jsonl")
    summary = dict(
        audited_at=datetime.now(UTC).isoformat(),
        collision_groups=len(collisions),
        affected_bindings=len(targets),
        missing_metadata=len(missing),
        automatic_validation=False,
    )
    (OUTPUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(audit()))
