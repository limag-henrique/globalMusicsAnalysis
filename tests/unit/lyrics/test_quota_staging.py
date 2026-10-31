import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select, update
from sqlalchemy.exc import IntegrityError

from chart_observatory.lyrics.quota_staging import blobs, candidates, persist_lyric_staging, runs


def record(key, digest):
    return dict(
        candidate_id=key,
        text_sha256=digest,
        acquisition_status="candidate_pending_validation",
        payload={"artist": "Artist"},
        source_result={"source": "GENIUS"},
        audit={"identity_validated": False},
    )


def test_snapshot_is_idempotent_and_blobs_are_shared_without_approving_candidates():
    engine = create_engine("sqlite://")
    body = "Original full fixture text"
    digest = hashlib.sha256(body.encode()).hexdigest()
    rows = [record("SPOTIFY:one", digest), record("SPOTIFY:two", digest)]
    first = persist_lyric_staging(engine, {"selection": "one"}, rows, {digest: body})
    assert first["inserted"] and first["new_text_blobs"] == 1
    assert not persist_lyric_staging(engine, {"selection": "one"}, rows, {digest: body})["inserted"]
    persist_lyric_staging(engine, {"selection": "two"}, rows, {digest: body})
    with engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(blobs)).scalar() == 1
        assert conn.execute(select(func.count()).select_from(candidates)).scalar() == 4
        assert conn.execute(select(func.count()).select_from(runs)).scalar() == 2
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(update(candidates).values(classification_ready=True))
    with pytest.raises(ValueError, match="hash mismatch"):
        persist_lyric_staging(engine, {}, rows, {digest: "Changed text"})
    engine.dispose()


def test_invalid_snapshot_does_not_add_an_import_run():
    engine = create_engine("sqlite://")
    persist_lyric_staging(engine, {"empty": True}, [], {})
    with pytest.raises(ValueError, match="inventory"):
        persist_lyric_staging(engine, {}, [record("SPOTIFY:one", "a" * 64)], {})
    with engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(runs)).scalar() == 1
    engine.dispose()


def test_staging_terminal_status_accepts_repository_readiness_flag(tmp_path):
    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location(
        "quota_staging_cli", root / "scripts/stage_quota_lyrics.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.STATE = tmp_path
    module.report("staged_pending_review", classification_ready=False, verified_candidates=2)
    status = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    assert status["classification_ready"] is False and status["verified_candidates"] == 2
