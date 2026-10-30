"""Attach database artist identities to frozen audit targets without modifying the database."""

import argparse
import json
from collections import defaultdict
from pathlib import Path

from sqlalchemy import create_engine, text

from chart_observatory.config import Settings

ROOT = Path(__file__).resolve().parents[1]


def run(source: Path, destination: Path):
    rows = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    wanted = {row["track_id"] for row in rows}
    artists = defaultdict(list)
    engine = create_engine(Settings.load(ROOT).database_url, connect_args={"connect_timeout": 5})
    with engine.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        # One join, not one subquery per document. The frozen target list stays fixed.
        for track_id, name in conn.execute(text("""
            SELECT ta.track_id, a.name FROM track_artists ta JOIN artists a ON a.id=ta.artist_id
        """)):
            if str(track_id) in wanted:
                artists[str(track_id)].append(name)
    engine.dispose()
    missing = 0
    for row in rows:
        names = sorted(set(artists[row["track_id"]]))
        row["artist"] = row.get("artist") or ", ".join(names) or None
        row["artist_identity_status"] = "linked" if row["artist"] else "missing"
        missing += not bool(row["artist"])
    rows.sort(key=lambda row: (
        "human_report_pending_adjudication" not in row["reasons"],
        not row["article_selected"], row["document_id"],
    ))
    with destination.open("x", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"targets": len(rows), "missing_artist_identity": missing, "database_writes": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.targets, args.output)))
