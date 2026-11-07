"""Offline research audit. Reads sources and SQLite in read-only mode; no providers/AI."""

import csv
import gzip
import hashlib
import json
import os
import sqlite3
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/audit/2026-11-06"
BASE = ROOT / "data/derived/annual_revision/reconciled-russia-2018-2026-20261031"


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    def git(*args):
        return subprocess.check_output(
            ["git", *args], cwd=ROOT, text=True, encoding="utf-8"
        ).strip()

    inventory = []
    excluded = {
        ".git",
        ".venv",
        ".venv-origin-preserved",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        "node_modules",
    }
    for current, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in excluded]
        for name in sorted(files):
            p = Path(current) / name
            rel = p.relative_to(ROOT).as_posix()
            if rel.startswith("docs/audit/2026-11-06/") or name.startswith(".env"):
                continue
            try:
                stat = p.stat()
                inventory.append(dict(path=rel, bytes=stat.st_size, suffix=p.suffix))
            except OSError:
                continue
    inventory.sort(key=lambda r: r["path"])
    with gzip.open(OUT / "inventory.csv.gz", "wt", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["path", "bytes", "suffix"])
        w.writeheader()
        w.writerows(inventory)
    (OUT / "git-history.txt").write_text(
        git("log", "--all", "--no-renames", "--date=iso-strict", "--format=%H %ad %s", "--stat"),
        encoding="utf-8",
    )
    (OUT / "git-status.txt").write_text(git("status", "--short"), encoding="utf-8")
    summary = dict(
        head=git("rev-parse", "HEAD"),
        commits_all=int(git("rev-list", "--count", "--all")),
        branches=git("branch", "-a").splitlines(),
        inventoried_files=len(inventory),
        scope=(
            "Inventory is metadata, not proof that every file was read. "
            "Secrets and environment directories excluded."
        ),
    )
    path = BASE / "combined.jsonl"
    rows = [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]
    counts = Counter(r["candidate_id"] for r in rows)
    countries_by_candidate = defaultdict(set)
    for row in rows:
        countries_by_candidate[row["candidate_id"]].add(row["country_code"])
    cells = defaultdict(list)
    for r in rows:
        cells[r["country_code"], r["year"]].append(r)
    summary["selection"] = dict(
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        memberships=len(rows),
        candidates=len(counts),
        markets=len({r["country_code"] for r in rows}),
        cells=len(cells),
        years=sorted({r["year"] for r in rows}),
        status=dict(Counter(r.get("selection_status", "UNSPECIFIED") for r in rows)),
        reused_memberships=len(rows) - len(counts),
        avoided_membership_work_fraction=1 - len(counts) / len(rows),
        repeated_candidates=sum(v > 1 for v in counts.values()),
        membership_multiplicity=dict(Counter(counts.values())),
    )
    summary["selection"]["cross_country_candidates"] = sum(
        len(v) > 1 for v in countries_by_candidate.values()
    )
    summary["selection"]["candidate_country_pairs"] = sum(map(len, countries_by_candidate.values()))
    import polars as pl

    from chart_observatory.ingestion.import_quotas import load_quotas
    from chart_observatory.ingestion.quota_boundary import (
        validate_quota_memberships,
        validate_ranking_positions,
    )

    quotas = load_quotas(BASE / "sources/country_quotas.csv")
    validated = validate_quota_memberships(rows, quotas)
    validate_ranking_positions(rows, pl.read_parquet(BASE / "sources/rankings.parquet").to_dicts())
    summary["quota_checks"] = dict(
        passed=True,
        selected_cells=len(validated),
        planned_cells=len(quotas) * 9,
        annual_target=sum(quotas.values()),
        india=quotas.get("IN"),
        netherlands=quotas.get("NL"),
    )
    with (OUT / "country-year-observations.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f, fieldnames=["country_code", "year", "memberships", "quota", "statuses"]
        )
        w.writeheader()
        for (c, y), group in sorted(cells.items()):
            w.writerow(
                dict(
                    country_code=c,
                    year=y,
                    memberships=len(group),
                    quota=quotas[c],
                    statuses=json.dumps(
                        dict(Counter(r.get("selection_status", "UNSPECIFIED") for r in group))
                    ),
                )
            )
    db = ROOT / "data/derived/lyrics/quota-20261030/acquisition.sqlite"
    with sqlite3.connect(db.as_uri() + "?mode=ro", uri=True, timeout=5) as con:
        con.execute("PRAGMA query_only=ON")
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        summary["sqlite"] = {"tables": {}}
        for table in tables:
            if not table.replace("_", "").isalnum():
                continue
            cols = [r[1] for r in con.execute(f'PRAGMA table_info("{table}")')]
            entry = dict(
                columns=cols, count=con.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
            )
            if "status" in cols:
                entry["statuses"] = dict(
                    con.execute(f'SELECT status,count(*) FROM "{table}" GROUP BY status')
                )
            summary["sqlite"]["tables"][table] = entry
    for label, p in [
        ("staging", ROOT / "data/runtime/postgres-lyric-staging-20261031/status.json"),
        ("boundary", ROOT / "data/runtime/quota-analysis-boundary-20261101.json"),
    ]:
        value = json.loads(p.read_text(encoding="utf-8"))
        summary[label] = {
            k: v for k, v in value.items() if k not in {"cells", "staged_cells", "reference_only"}
        }
    (OUT / "measurements.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
