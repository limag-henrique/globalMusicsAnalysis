import json
from pathlib import Path

import pytest

from chart_observatory.lyrics.quota_acquisition import AcquisitionStore
from chart_observatory.lyrics.quota_replay_import import import_cached_candidates


def setup_store(tmp_path):
    store = AcquisitionStore(tmp_path / "store")
    store.conn.executescript("""
        CREATE TABLE recovery_attempts(identity TEXT,method TEXT,state TEXT,
            previous_result TEXT,result TEXT,PRIMARY KEY(identity,method));
        CREATE TABLE evidence_audits(identity TEXT PRIMARY KEY,audit TEXT);
    """)
    directory = tmp_path / "replays"
    directory.mkdir()
    payload = dict(
        recording_id="SPOTIFY:one",
        title="Song",
        artist="Artist",
        requires_metadata_reconciliation=True,
        chart_bindings=[dict(country_code="BR", year=2021, position=1)],
    )
    store.enqueue(payload["recording_id"], payload)
    store.finish(
        payload["recording_id"],
        dict(source="LETRAS", status="reused_pending_validation", text="Old fixture text"),
    )
    old = json.loads(store.conn.execute("SELECT result FROM tasks").fetchone()[0])
    return store, directory, payload, old


def proposal(payload, old, text="New fixture text"):
    return dict(
        payload=payload,
        replay_kind="flagged_repair",
        replaces_text_sha256=old["text_sha256"],
        result=dict(
            source="LRCLIB",
            status="candidate_pending_validation",
            text=text,
            generated_by_ai=False,
            source_metadata=dict(
                observed_title=payload["title"], observed_artist=payload["artist"]
            ),
        ),
    )


def test_owner_import_preserves_history_fills_gap_and_does_not_repeat(tmp_path):
    store, directory, payload, old = setup_store(tmp_path)
    (directory / "one.json").write_text(json.dumps(proposal(payload, old)), encoding="utf-8")
    second = {**payload, "recording_id": "SPOTIFY:two", "title": "Other Song"}
    store.enqueue(second["recording_id"], second)
    replay = proposal(second, old, "Other fixture text")
    replay.update(replay_kind="missing_text", replaces_text_sha256=None)
    (directory / "two.json").write_text(json.dumps(replay), encoding="utf-8")
    result = import_cached_candidates(
        store, {payload["recording_id"], second["recording_id"]}, directory
    )
    assert result["repairs"] == 1 and result["gaps"] == 1
    assert Path(old["text_path"]).read_text() == "Old fixture text"
    saved = json.loads(
        store.conn.execute(
            "SELECT result FROM tasks WHERE identity=?", (payload["recording_id"],)
        ).fetchone()[0]
    )
    assert saved["replaced_unverified_result"] == old
    assert saved["source"] == "LRCLIB" and not saved["classification_ready"]
    assert not json.loads(store.conn.execute("SELECT payload FROM tasks LIMIT 1").fetchone()[0])[
        "requires_metadata_reconciliation"
    ]
    previous = store.conn.execute(
        "SELECT previous_result FROM recovery_attempts WHERE identity=?", (payload["recording_id"],)
    ).fetchone()[0]
    assert json.loads(previous) == old
    assert (
        import_cached_candidates(
            store, {payload["recording_id"], second["recording_id"]}, directory
        )["imported"]
        == 0
    )
    assert len(list(store.blobs.glob("*.txt"))) == 3
    store.conn.close()


def test_conflicting_proposals_preserve_old_candidate_without_reserving_attempt(tmp_path):
    store, directory, payload, old = setup_store(tmp_path)
    for name, body in [("one", "First alternative"), ("two", "Divergent alternative")]:
        (directory / f"{name}.json").write_text(json.dumps(proposal(payload, old, body)))
    result = import_cached_candidates(store, {payload["recording_id"]}, directory)
    assert result["conflicts"] == 1 and result["imported"] == 0
    assert json.loads(store.conn.execute("SELECT result FROM tasks").fetchone()[0]) == old
    assert store.conn.execute("SELECT count(*) FROM recovery_attempts").fetchone()[0] == 0
    store.conn.close()


def test_import_refuses_active_queue_and_corrupt_previous_blob(tmp_path):
    store, directory, payload, old = setup_store(tmp_path)
    (directory / "one.json").write_text(json.dumps(proposal(payload, old)))
    with store.conn:
        store.conn.execute("UPDATE tasks SET status='running'")
    with pytest.raises(RuntimeError, match="drained"):
        import_cached_candidates(store, {payload["recording_id"]}, directory)
    with store.conn:
        store.conn.execute("UPDATE tasks SET status='reused_pending_validation'")
    Path(old["text_path"]).write_text("Corrupt old body")
    with pytest.raises(ValueError, match="previous lyric hash mismatch"):
        import_cached_candidates(store, {payload["recording_id"]}, directory)
    assert store.conn.execute("SELECT count(*) FROM recovery_attempts").fetchone()[0] == 0
    store.conn.close()
