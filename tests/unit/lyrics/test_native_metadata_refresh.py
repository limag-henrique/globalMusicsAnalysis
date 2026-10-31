import hashlib
import importlib.util
import json
from pathlib import Path

from chart_observatory.lyrics.quota_acquisition import AcquisitionStore


def test_round_refresh_preserves_existing_text_and_bindings_and_is_idempotent(tmp_path):
    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location(
        "quota_refresh_worker", root / "scripts/autonomous_lyrics.py"
    )
    worker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(worker)
    store = AcquisitionStore(tmp_path / "store")
    payload = dict(
        recording_id="SPOTIFY:one",
        title="Song",
        artist="Old Artist",
        chart_bindings=[dict(country_code="BR", year=2021, position=230)],
    )
    store.enqueue("SPOTIFY:one", payload)
    store.finish(
        "SPOTIFY:one", dict(status="candidate_pending_validation", text="Saved fixture text")
    )
    original = store.conn.execute("SELECT status,result FROM tasks").fetchone()
    proof = dict(
        status=200,
        source_url="https://open.spotify.com/embed/track/one",
        metadata=dict(uri="spotify:track:one", title="Song", artist="Verified Artist"),
    )
    raw = json.dumps(proof).encode()
    evidence = tmp_path / "proof.json"
    evidence.write_bytes(raw)
    mapping = tmp_path / "mapping.json"
    mapping.write_text(
        json.dumps(
            {
                "SPOTIFY:one": dict(
                    evidence_file=str(evidence), evidence_sha256=hashlib.sha256(raw).hexdigest()
                )
            }
        ),
        encoding="utf-8",
    )
    refreshed = worker.refresh_native_metadata(store, {"SPOTIFY:one"}, mapping)
    assert refreshed["changed_names"] == 1
    saved = json.loads(store.conn.execute("SELECT payload FROM tasks").fetchone()[0])
    assert saved["artist"] == "Verified Artist" and saved["requires_metadata_reconciliation"]
    assert saved["chart_bindings"] == payload["chart_bindings"]
    assert store.conn.execute("SELECT status,result FROM tasks").fetchone() == original
    # A drained queue must use the new names, without re-enqueuing completed IDs,
    # consuming an attempt or losing the earlier saved text.
    pending, details = worker.refresh_pending_native_metadata(
        store,
        {"SPOTIFY:one"},
        mapping,
        [("SPOTIFY:one", payload, original[0], original[1])],
    )
    assert [item[0] for item in pending] == ["SPOTIFY:one"]
    assert pending[0][1]["artist"] == "Verified Artist"
    assert pending[0][1]["chart_bindings"] == payload["chart_bindings"]
    assert pending[0][2:] == original
    assert details["updated_queued_candidates"] == 1
    assert store.conn.execute("SELECT status,result FROM tasks").fetchone() == original
    assert worker.refresh_pending_native_metadata(store, {"SPOTIFY:one"}, mapping, [])[0] == []
    again = worker.refresh_native_metadata(store, {"SPOTIFY:one"}, mapping)
    assert again["updated_payloads"] == again["changed_names"] == 0
    store.conn.close()


def test_restart_preserves_all_name_revisions_and_updates_selection_bindings():
    from chart_observatory.lyrics.quota_acquisition import reconcile_reindexed_task

    first = dict(recording_id="SPOTIFY:one", title="Song", artist="Old",
                 metadata_revision_history=[dict(title="Initial", artist="Initial")],
                 requires_metadata_reconciliation=True,
                 previous_display_metadata=dict(title="Initial", artist="Initial"),
                 chart_bindings=[dict(year=2020, position=10)])
    current = dict(recording_id="SPOTIFY:one", title="Song", artist="New",
                   chart_bindings=[dict(year=2021, position=3)])
    merged = reconcile_reindexed_task(first, current)
    assert merged["metadata_revision_history"][0] == first["metadata_revision_history"][0]
    assert merged["metadata_revision_history"][-1]["artist"] == "Old"
    assert merged["chart_bindings"] == current["chart_bindings"]
    assert merged["requires_metadata_reconciliation"]
    assert reconcile_reindexed_task(merged, current) == merged
    assert first["artist"] == "Old" and len(first["metadata_revision_history"]) == 1
