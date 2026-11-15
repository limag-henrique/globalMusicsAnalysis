import importlib.util
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, update


@pytest.fixture
def intake(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[2] / "scripts/persist_frozen_research_selection.py"
    spec = importlib.util.spec_from_file_location("frozen_selection_intake_test", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    selection = tmp_path / "selection"
    selection.mkdir()
    (selection / "manifest.json").write_text("{}", encoding="utf-8")
    (selection / "countries.json").write_text('[{"country_code":"BR"}]', encoding="utf-8")
    hashes = {str(p): module.file_hash(p) for p in selection.iterdir()}
    manifest = {"new_definitive_memberships": 1, "new_provisional_memberships": 0}
    cells = [{"country_code": "BR", "year": 2020, "quota": 1}]
    members = [{"country_code": "BR", "year": 2020, "position": 1, "candidate_id": "song"}]
    monkeypatch.setattr(module, "load_selection", lambda p: (manifest, cells, members, hashes))
    engine = create_engine("sqlite://")
    yield module, tmp_path, selection, engine, hashes
    engine.dispose()


def test_persistence_replays_idempotently_and_keeps_selection_immutable(intake):
    module, root, selection, engine, hashes = intake
    first = module.persist_selection(root, selection, root / "receipt1", engine=engine)
    second = module.persist_selection(root, selection, root / "receipt2", engine=engine)
    assert first["inserted"] and not second["inserted"]
    assert first["run_id"] == second["run_id"]
    assert all(r["all_payloads_equal"] for r in second["comparisons"])
    assert {str(p): module.file_hash(p) for p in selection.iterdir()} == hashes
    assert second["scientific_approval"] is False


def test_existing_partial_or_corrupted_run_cannot_pass_replay(intake):
    module, root, selection, engine, _ = intake
    receipt = module.persist_selection(root, selection, root / "receipt1", engine=engine)
    with engine.begin() as conn:
        conn.execute(update(module.memberships_table).values(payload={"position": 999}))
    with pytest.raises((ValueError, KeyError)):
        module.persist_selection(root, selection, root / "receipt2", engine=engine)
    assert not (root / "receipt2").exists()
    assert json.loads((root / "receipt1/report.json").read_text())["run_id"] == receipt["run_id"]


def test_unhashed_country_inventory_blocks_before_database_writes(intake):
    module, root, selection, engine, hashes = intake
    hashes.pop(str(selection / "countries.json"))
    with pytest.raises(ValueError, match="hashed country"):
        module.persist_selection(root, selection, root / "receipt", engine=engine)
    from sqlalchemy import inspect

    assert inspect(engine).get_table_names() == []


def test_receipt_cannot_modify_the_immutable_selection_directory(intake):
    module, root, selection, engine, _ = intake
    with pytest.raises(ValueError, match="outside the immutable selection"):
        module.persist_selection(root, selection, selection / "receipt", engine=engine)
    assert not (selection / "receipt").exists()
