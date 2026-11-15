import hashlib
import json

import pytest
from sqlalchemy import create_engine, select

from chart_observatory.lyrics.global_import import (
    plan_global,
    seed_exact_native_results,
    stage_global,
)
from chart_observatory.lyrics.quota_acquisition import AcquisitionStore
from chart_observatory.lyrics.quota_staging import candidates, persist_lyric_staging


def setup_selection(tmp_path, *, change_legacy=False):
    legacy = tmp_path / "legacy"
    base = tmp_path / "global"
    legacy.mkdir()
    base.mkdir()
    old = dict(
        candidate_id="SPOTIFY:old",
        country_code="BR",
        year=2025,
        position=1,
        quota_main=100,
        title="Original",
        artist="Artist",
        platform="SPOTIFY",
        metric_value=100,
    )
    new = {**old, "candidate_id": "SPOTIFY:new", "country_code": "NG", "title": "New"}
    (legacy / "combined.jsonl").write_text(json.dumps(old) + "\n")
    members = [{**old, "metric_value": 99} if change_legacy else old, new]
    (base / "combined.jsonl").write_text("".join(json.dumps(r) + "\n" for r in members))
    (base / "countries.json").write_text(
        json.dumps([dict(country_code=c, quota_per_year_main=100) for c in ("BR", "NG")])
    )
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in base.iterdir()}
    (base / "manifest.json").write_text(
        json.dumps(
            dict(
                protocol="worldwide-annual-quotas-v1",
                output_hashes=hashes,
                country_year_cells=18,
                countries=2,
            )
        )
    )
    return base, legacy


def test_global_delta_preserves_original_memberships_without_reacquiring_known_ids(tmp_path):
    base, legacy = setup_selection(tmp_path)
    tasks, delta, summary = plan_global(base, legacy)
    assert delta == {"SPOTIFY:new"} and len(tasks) == 2
    assert summary["memberships"] == 2 and summary["preserved_legacy_memberships"] == 1
    assert not summary["classification_ready"] and summary["paid_calls_authorized"] == 0
    assert all(t["not_for_paid_submission"] for t in tasks)


@pytest.mark.parametrize("change_legacy", [True, False])
def test_rank_changes_and_corrupt_artifacts_fail_closed(tmp_path, change_legacy):
    base, legacy = setup_selection(tmp_path, change_legacy=change_legacy)
    if not change_legacy:
        (base / "combined.jsonl").write_text("{}\n")
    with pytest.raises(ValueError, match="changed"):
        plan_global(base, legacy)


def test_same_native_id_reuse_preserves_bytes_without_approving_recording(tmp_path):
    old = AcquisitionStore(tmp_path / "old")
    new = AcquisitionStore(tmp_path / "new")
    payload = dict(recording_id="SPOTIFY:new", title="Song", artist="Artist")
    old.enqueue("SPOTIFY:new", payload)
    old.finish(
        "SPOTIFY:new",
        dict(
            status="candidate_pending_validation",
            source="LRCLIB",
            text="Original\r\nRefrain\r\nRefrain\r\nEnding",
        ),
    )
    assert seed_exact_native_results(new, [payload], tmp_path / "old") == 1
    assert seed_exact_native_results(new, [payload], tmp_path / "old") == 0
    stored = json.loads(new.conn.execute("SELECT result FROM tasks").fetchone()[0])
    assert not stored["identity_validated"] and not stored["completeness_validated"]
    assert not stored["classification_ready"]
    assert stored["copied_from_exact_native_id"] == "SPOTIFY:new"
    old.conn.close()
    new.conn.close()


def test_global_staging_keeps_legacy_text_and_new_missing_candidate(tmp_path):
    base, legacy = setup_selection(tmp_path)
    engine = create_engine("sqlite://")
    body = "\n".join(f"Original fixture line {i}" for i in range(25))
    digest = hashlib.sha256(body.encode()).hexdigest()
    record = dict(
        candidate_id="SPOTIFY:old",
        text_sha256=digest,
        acquisition_status="candidate_pending_validation",
        payload=dict(title="Original", artist="Artist"),
        source_result=dict(
            source="LRCLIB",
            text_sha256=digest,
            source_metadata=dict(observed_title="Original", observed_artist="Artist"),
        ),
        audit={},
    )
    persist_lyric_staging(engine, dict(selection_root=str(legacy)), [record], {digest: body})
    store = AcquisitionStore(tmp_path / "store")
    store.conn.close()
    result = stage_global(engine, base, legacy, tmp_path / "store")
    assert result["candidates"] == 2 and result["text_candidates"] == 1
    with engine.connect() as conn:
        rows = (
            conn.execute(select(candidates).where(candidates.c.run_id == result["run_id"]))
            .mappings()
            .all()
        )
        assert len(rows) == 2 and not any(r["classification_ready"] for r in rows)
        assert next(r for r in rows if r["candidate_id"] == "SPOTIFY:old")["text_sha256"] == digest
    assert not stage_global(engine, base, legacy, tmp_path / "store")["inserted"]


def fresh_overlay_fixture(tmp_path, *, old_body=None, flagged=False, replacement=None):
    base, legacy = setup_selection(tmp_path)
    engine = create_engine("sqlite://")
    old_hash = hashlib.sha256(old_body.encode()).hexdigest() if old_body else None
    old_result = dict(
        source="LRCLIB",
        text_sha256=old_hash,
        source_metadata=dict(observed_title="Original", observed_artist="Artist"),
        text_quality_flags=["suspected_partial"] if flagged else [],
    )
    old_record = dict(
        candidate_id="SPOTIFY:old",
        text_sha256=old_hash,
        acquisition_status="candidate_pending_validation" if old_body else "unavailable",
        payload=dict(title="Original", artist="Artist"),
        source_result=old_result,
        audit={},
    )
    old_run = persist_lyric_staging(
        engine,
        dict(selection_root=str(legacy)),
        [old_record],
        {old_hash: old_body} if old_body else {},
    )["run_id"]
    store = AcquisitionStore(tmp_path / "store")
    payload = dict(recording_id="SPOTIFY:old", title="Original", artist="Artist")
    store.enqueue("SPOTIFY:old", payload)
    body = "\n".join(f"Fresh synthetic lyric sentence number {i}" for i in range(25))
    provider_row = dict(
        id=41, trackName="Original", artistName="Artist", instrumental=False, plainLyrics=body
    )
    raw = json.dumps(provider_row)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    cache = tmp_path / "http-response.json"
    cache.write_text(
        json.dumps(dict(body=raw, body_sha256=digest, encoding="utf-8")), encoding="utf-8"
    )
    fresh = dict(
        status="candidate_pending_validation",
        source="LRCLIB",
        generated_by_ai=False,
        text_quality_flags=[],
        text=body,
        identity_check="provider_metadata_match",
        source_metadata=dict(id=41, observed_title="Original", observed_artist="Artist"),
        http_evidence=[
            dict(
                status=200,
                url="https://lrclib.net/api/get/41",
                cache_path=str(cache),
                body_sha256=digest,
            )
        ],
    )
    store.finish("SPOTIFY:old", fresh)
    if replacement is not None:
        store.conn.execute(
            "CREATE TABLE recovery_attempts(identity TEXT,method TEXT,state TEXT,"
            "previous_result TEXT,result TEXT,PRIMARY KEY(identity,method))"
        )
        store.conn.execute(
            "INSERT INTO recovery_attempts VALUES (?,?,?,?,?)",
            (
                "SPOTIFY:old",
                "fixture-round1",
                "finished",
                json.dumps(
                    {
                        **old_result,
                        "text_sha256": old_hash if replacement == "current" else "f" * 64,
                    }
                ),
                json.dumps({k: v for k, v in fresh.items() if k != "text"}),
            ),
        )
        store.conn.commit()
    store.conn.close()
    return base, legacy, engine, body, cache, old_run, old_hash


def staged_old(engine, run):
    with engine.connect() as conn:
        return (
            conn.execute(
                select(candidates).where(
                    candidates.c.run_id == run, candidates.c.candidate_id == "SPOTIFY:old"
                )
            )
            .mappings()
            .one()
        )


def test_fresh_global_store_fills_legacy_gap_with_reproduced_source_and_no_approval(tmp_path):
    base, legacy, engine, body, _cache, old_run, _old_hash = fresh_overlay_fixture(tmp_path)
    result = stage_global(engine, base, legacy, tmp_path / "store", evidence_root=tmp_path)
    row = staged_old(engine, result["run_id"])
    assert row["text_sha256"] == hashlib.sha256(body.encode()).hexdigest()
    assert row["source_result"]["global_acquisition_overlay"] is True
    assert row["source_result"]["source_chain_check"]["status"] == "source_chain_matched"
    assert not row["classification_ready"]
    assert result["global_acquisition_gap_fills"] == 1
    assert result["global_acquisition_repairs"] == 0
    assert staged_old(engine, old_run)["text_sha256"] is None
    assert not stage_global(engine, base, legacy, tmp_path / "store", evidence_root=tmp_path)[
        "inserted"
    ]


@pytest.mark.parametrize("binding", [None, "stale"])
def test_fresh_result_cannot_replace_existing_flagged_text_without_old_hash_binding(
    tmp_path, binding
):
    old_body = "\n".join(f"Prior synthetic lyric sentence number {i}" for i in range(25))
    base, legacy, engine, _body, _cache, _old_run, old_hash = fresh_overlay_fixture(
        tmp_path,
        old_body=old_body,
        flagged=True,
        replacement=binding,
    )
    result = stage_global(engine, base, legacy, tmp_path / "store", evidence_root=tmp_path)
    assert staged_old(engine, result["run_id"])["text_sha256"] == old_hash
    assert result["global_acquisition_repairs"] == 0


def test_bound_fresh_repair_preserves_previous_result_and_historical_snapshot(tmp_path):
    old_body = "\n".join(f"Prior synthetic lyric sentence number {i}" for i in range(25))
    base, legacy, engine, body, _cache, old_run, old_hash = fresh_overlay_fixture(
        tmp_path,
        old_body=old_body,
        flagged=True,
        replacement="current",
    )
    result = stage_global(engine, base, legacy, tmp_path / "store", evidence_root=tmp_path)
    row = staged_old(engine, result["run_id"])
    assert row["text_sha256"] == hashlib.sha256(body.encode()).hexdigest()
    assert row["source_result"]["replaces_text_sha256"] == old_hash
    assert row["source_result"]["replaced_unverified_result"]["text_sha256"] == old_hash
    assert staged_old(engine, old_run)["text_sha256"] == old_hash
    assert result["global_acquisition_repairs"] == 1


def test_bound_fresh_result_still_cannot_replace_unflagged_text(tmp_path):
    old_body = "\n".join(f"Prior synthetic lyric sentence number {i}" for i in range(25))
    base, legacy, engine, _body, _cache, _old_run, old_hash = fresh_overlay_fixture(
        tmp_path,
        old_body=old_body,
        replacement="current",
    )
    result = stage_global(engine, base, legacy, tmp_path / "store", evidence_root=tmp_path)
    assert staged_old(engine, result["run_id"])["text_sha256"] == old_hash
    assert result["global_acquisition_repairs"] == 0


def test_corrupted_provider_response_does_not_fill_gap(tmp_path):
    base, legacy, engine, _body, cache, _old_run, _old_hash = fresh_overlay_fixture(tmp_path)
    value = json.loads(cache.read_text())
    value["body"] = "corrupt response"
    cache.write_text(json.dumps(value))
    result = stage_global(engine, base, legacy, tmp_path / "store", evidence_root=tmp_path)
    assert staged_old(engine, result["run_id"])["text_sha256"] is None
    assert result["global_acquisition_overlay_rejections"] == 1


def test_corrupted_fresh_blob_aborts_before_creating_global_snapshot(tmp_path):
    base, legacy, engine, _body, _cache, _old_run, _old_hash = fresh_overlay_fixture(tmp_path)
    for path in (tmp_path / "store/texts").glob("*.txt"):
        path.write_text("corrupted body")
    with pytest.raises(ValueError, match="blob hash mismatch"):
        stage_global(engine, base, legacy, tmp_path / "store", evidence_root=tmp_path)


def test_fresh_payload_of_another_recording_cannot_fill_legacy_gap(tmp_path):
    import sqlite3

    base, legacy, engine, _body, _cache, _old_run, _old_hash = fresh_overlay_fixture(tmp_path)
    with sqlite3.connect(tmp_path / "store/acquisition.sqlite") as db:
        payload = json.loads(db.execute("SELECT payload FROM tasks").fetchone()[0])
        payload["recording_id"] = "SPOTIFY:someone-else"
        db.execute("UPDATE tasks SET payload=?", (json.dumps(payload),))
    result = stage_global(engine, base, legacy, tmp_path / "store", evidence_root=tmp_path)
    assert staged_old(engine, result["run_id"])["text_sha256"] is None
