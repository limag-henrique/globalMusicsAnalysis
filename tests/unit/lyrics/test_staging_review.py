import hashlib

import pytest
from sqlalchemy import create_engine, update

from chart_observatory.lyrics.quota_staging import blobs, persist_lyric_staging
from chart_observatory.lyrics.staging_review import browse_pending, list_snapshots, pending_detail


def fixture(engine):
    body = "First fixture line\nFinal fixture line"
    digest = hashlib.sha256(body.encode()).hexdigest()
    records = []
    for key, bindings, sha in [
        (
            "one",
            [{"country_code": "BR", "year": 2020}, {"country_code": "IN", "year": 2021}],
            digest,
        ),
        ("two", [{"country_code": "BR", "year": 2021}], None),
    ]:
        records.append(
            dict(
                candidate_id=key,
                text_sha256=sha,
                acquisition_status="pending_review",
                payload=dict(title="Song " + key, artist="Artist", chart_bindings=bindings),
                source_result={},
                audit={},
            )
        )
    return persist_lyric_staging(engine, {"test": True}, records, {digest: body})


def test_filter_country_and_year_must_match_the_same_binding_and_never_returns_body():
    engine = create_engine("sqlite://")
    run = fixture(engine)
    result = browse_pending(engine, country="BR", year=2021)
    assert [r["candidate_id"] for r in result["rows"]] == ["two"]
    assert not result["rows"][0]["has_text"] and "text" not in result["rows"][0]
    assert browse_pending(engine, has_text=True)["total"] == 1
    assert list_snapshots(engine)[0]["run_id"] == run["run_id"]
    detail = pending_detail(engine, "one", run_id=run["run_id"])
    assert detail["text"].endswith("Final fixture line") and detail["blob_integrity_verified"]
    assert not detail["identity_validated"] and not detail["classification_ready"]
    assert pending_detail(engine, "one", run_id="missing") is None
    engine.dispose()


def test_missing_staging_is_read_only_and_corrupt_body_is_rejected():
    engine = create_engine("sqlite://")
    assert list_snapshots(engine) == [] and browse_pending(engine)["total"] == 0
    fixture(engine)
    with engine.begin() as conn:
        conn.execute(update(blobs).values(body="Corrupt"))
    with pytest.raises(ValueError, match="hash mismatch"):
        pending_detail(engine, "one")
    engine.dispose()


def test_country_year_pagination_uses_matching_rank_before_title():
    engine = create_engine("sqlite://")
    records = []
    for key, title, position in [("later", "A title", 2), ("first", "Z title", 1)]:
        records.append(
            dict(
                candidate_id=key,
                text_sha256=None,
                acquisition_status="pending_review",
                payload=dict(
                    title=title,
                    artist="Artist",
                    chart_bindings=[
                        dict(country_code="BR", year=2021, position=position),
                        dict(country_code="IN", year=2020, position=1),
                    ],
                ),
                source_result={},
                audit={},
            )
        )
    run = persist_lyric_staging(engine, {"test": True}, records, {})
    first = browse_pending(engine, country="BR", year=2021, limit=1)
    second = browse_pending(
        engine, run_id=run["run_id"], country="BR", year=2021, limit=1, offset=1
    )
    assert first["rows"][0]["candidate_id"] == "first"
    assert second["rows"][0]["candidate_id"] == "later"
    assert len(second["rows"][0]["bindings"]) == 1
    engine.dispose()


def test_snapshot_coverage_includes_empty_quota_cells_and_is_scoped():
    from chart_observatory.lyrics.staging_review import coverage_for_run

    engine = create_engine("sqlite://")
    row = dict(
        candidate_id="one",
        text_sha256=None,
        acquisition_status="pending_review",
        payload=dict(
            title="Song",
            artist="Artist",
            chart_bindings=[dict(country_code="BR", year=2020, position=1)],
        ),
        source_result={},
        audit={},
    )
    run = persist_lyric_staging(engine, {"test": "coverage"}, [row], {})
    result = coverage_for_run(engine, {"BR": 2, "AD": 1}, run_id=run["run_id"])
    cells = {(r["country_code"], r["year"]): r for r in result["cells"]}
    assert cells["AD", 2020]["missing_ranking_positions"] == [1]
    assert cells["AD", 2020]["missing_text_positions"] == []
    assert cells["BR", 2020]["missing_text_positions"] == [1]
    assert coverage_for_run(engine, {"BR": 2}, run_id="missing") is None
    engine.dispose()
