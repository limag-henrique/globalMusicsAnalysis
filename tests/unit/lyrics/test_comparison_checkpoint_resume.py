import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "comparison_resume",
    Path(__file__).resolve().parents[3] / "scripts/resume_web_comparison_checkpoint.py",
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def source_checkpoint(path):
    path.mkdir()
    (path / "owner.lock").write_bytes(b"0")
    (path / "campaign.json").write_text(
        json.dumps(
            dict(
                run_id="run",
                total=3,
                ends_at="2000-01-01T00:00:00+00:00",
                prior_unpublished_proposals_require_reconciliation=1,
            )
        )
    )
    with sqlite3.connect(path / "comparison.sqlite") as db:
        db.executescript(
            "CREATE TABLE inputs(id TEXT,done INTEGER); "
            "CREATE TABLE results(id TEXT,result TEXT); "
            "CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT);"
        )
        db.executemany("INSERT INTO inputs VALUES (?,?)", [("a", 1), ("b", 1), ("c", 0)])
        db.executemany(
            "INSERT INTO results VALUES (?,?)",
            [("a", '{"proposal_file":"a.json"}'), ("b", '{"proposal_file":"b.json"}')],
        )
        db.execute("INSERT INTO meta VALUES ('published','2')")


def test_backup_preserves_done_rows_and_does_not_republish_held_proposals(tmp_path):
    old, new = tmp_path / "source", tmp_path / "new"
    source_checkpoint(old)
    campaign = module.prepare(old, new, 2)
    assert campaign["inherited_completed"] == 2
    assert campaign["inherited_proposals_not_republished"] == 2
    assert campaign["inherited_published"] == 1
    assert campaign["prior_unpublished_proposals_require_reconciliation"] == 1
    with sqlite3.connect(new / "comparison.sqlite") as db:
        assert db.execute("SELECT id FROM inputs WHERE done=0").fetchall() == [("c",)]
        assert db.execute("SELECT value FROM meta WHERE key='published'").fetchone() == ("2",)
    assert json.loads((old / "campaign.json").read_text())["ends_at"] == "2000-01-01T00:00:00+00:00"
    with pytest.raises(ValueError, match="already exists"):
        module.prepare(old, new, 2)


def test_inconsistent_results_checkpoint_is_rejected(tmp_path):
    old = tmp_path / "source"
    source_checkpoint(old)
    with sqlite3.connect(old / "comparison.sqlite") as db:
        db.execute("DELETE FROM results WHERE id='a'")
    with pytest.raises(ValueError, match="inventory"):
        module.prepare(old, tmp_path / "new", 2)
