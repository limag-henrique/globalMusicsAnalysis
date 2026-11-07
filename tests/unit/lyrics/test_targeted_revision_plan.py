import hashlib
import importlib.util
import json
import sqlite3
from pathlib import Path


def test_saved_scope_hash_matches_actual_bytes_on_windows(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[3] / "scripts/run_targeted_revision.py"
    spec = importlib.util.spec_from_file_location("targeted_plan_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    store, state = tmp_path / "store", tmp_path / "state"
    (store / "review-inventory").mkdir(parents=True)
    state.mkdir()
    monkeypatch.setattr(module, "STORE", store)
    monkeypatch.setattr(module, "STATE", state)
    coverage = dict(
        missing_text_candidates=[
            dict(candidate_id="SPOTIFY:a", selected_memberships=3, best_position=1)
        ]
    )
    (store / "review-inventory/staging-coverage.json").write_text(json.dumps(coverage))
    with sqlite3.connect(store / "acquisition.sqlite") as conn:
        conn.execute("CREATE TABLE tasks(identity TEXT, result TEXT)")
        conn.execute("INSERT INTO tasks VALUES (?,?)", ("SPOTIFY:a", "{}"))
    module.plan_missing(limit=1)
    saved = (state / "candidate-ids.jsonl").read_bytes()
    plan = json.loads((state / "missing-plan.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(saved).hexdigest() == plan["candidate_filter_sha256"]
    assert len(saved.splitlines()) == 1
    assert plan["annual_position_changes"] == 0
