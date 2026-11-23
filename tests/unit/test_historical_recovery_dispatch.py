import importlib.util
import json
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location(
    "dispatch_historical_recovery", Path(__file__).parents[2] / "scripts/dispatch_historical_recovery.py"
)
dispatch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dispatch)


def test_claims_are_disjoint_expire_and_retry_without_promoting(tmp_path):
    selection = tmp_path / "selection"
    selection.mkdir()
    (selection / "manifest.json").write_text("{}")
    (selection / "country_years.jsonl").write_text("\n".join(json.dumps({
        "country_code": country, "year": 2020, "quota": gap,
        "missing_positions": gap, "missing_complete_annual_positions": gap,
    }) for country, gap in [("CN", 500), ("BD", 300), ("ET", 200)]))
    c1 = dispatch.connect(tmp_path / "dispatch.sqlite")
    c2 = dispatch.connect(tmp_path / "dispatch.sqlite")
    dispatch.initialize(c1, selection)
    a = dispatch.claim(c1, "codex", 1, 10, now=0)
    b = dispatch.claim(c2, "antigravity", 2, 10, now=0)
    assert [x["task_id"] for x in a] == ["CN-2020"]
    assert not {x["task_id"] for x in a} & {x["task_id"] for x in b}
    assert not dispatch.claim(c1, "third", 3, 10, now=5)
    reclaimed = dispatch.claim(c1, "third", 1, 10, now=11)
    assert reclaimed[0]["task_id"] == "CN-2020"
    assert reclaimed[0]["attempt"] == 2
    assert reclaimed[0]["classification_ready"] is False
    with pytest.raises(ValueError, match="expired|another"):
        dispatch.finish(c1, "CN-2020", "codex", "retry", None, 60)
    (selection / "manifest.json").write_text('{"changed":true}')
    with pytest.raises(ValueError, match="modified"):
        dispatch.initialize(c1, selection)
    c1.close()
    c2.close()


def test_exact_tasks_and_transfer_fail_closed(tmp_path):
    conn = dispatch.connect(tmp_path / "dispatch.sqlite")
    for key, priority in [("ET-2022", 20), ("ET-2023", 30), ("ET-2025", 50), ("ET-2024", 40)]:
        conn.execute("INSERT INTO tasks(task_id,payload,priority) VALUES (?,?,?)",
                     (key, json.dumps({"task_id": key}), priority))
    exact = ["ET-2022", "ET-2023", "ET-2025"]
    rows = dispatch.claim(conn, "proposed", 3, 100, now=0, task_ids=exact)
    assert {r["task_id"] for r in rows} == set(exact)
    assert conn.execute("SELECT status FROM tasks WHERE task_id='ET-2024'").fetchone()[0] == "pending"
    with pytest.raises(ValueError, match="unavailable"):
        dispatch.claim(conn, "other", 3, 100, now=1, task_ids=["ET-2024", "ET-2022"])
    assert conn.execute("SELECT status FROM tasks WHERE task_id='ET-2024'").fetchone()[0] == "pending"
    for owner, tasks, now in [("wrong", exact, 1), ("proposed", ["ET-2022", "ET-2024"], 1),
                               ("proposed", exact, 101)]:
        with pytest.raises(ValueError, match="live claims"):
            dispatch.transfer(conn, tasks, owner, "actual", 50, now=now)
        assert {r[0] for r in conn.execute("SELECT owner FROM tasks WHERE status='claimed'")} == {"proposed"}
    moved = dispatch.transfer(conn, exact, "proposed", "actual", 50, now=2)
    assert {r["task_id"] for r in moved} == set(exact)
    assert all(r["owner"] == "actual" and r["lease_until"] == 52 for r in moved)
    conn.close()
