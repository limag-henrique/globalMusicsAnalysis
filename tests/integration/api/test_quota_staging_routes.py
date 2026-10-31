import hashlib

from fastapi.testclient import TestClient

from chart_observatory.api.app import create_app
from chart_observatory.application import LocalResearchApplication
from chart_observatory.lyrics.quota_staging import persist_lyric_staging


def test_pending_import_routes_are_read_only_and_snapshot_scoped(tmp_path):
    application = LocalResearchApplication(tmp_path)
    client = TestClient(create_app(application))
    assert client.get("/quota-staging/snapshots").json()["snapshots"] == []
    body = "First fixture line\nFinal fixture line"
    digest = hashlib.sha256(body.encode()).hexdigest()
    result = persist_lyric_staging(
        application.engine,
        {"test": True},
        [
            dict(
                candidate_id="SPOTIFY:one",
                text_sha256=digest,
                acquisition_status="candidate_pending_validation",
                payload=dict(
                    title="Fixture Song",
                    artist="Artist",
                    chart_bindings=[dict(country_code="BR", year=2021, position=1)],
                ),
                source_result={},
                audit={},
            )
        ],
        {digest: body},
    )
    page = client.get("/quota-staging/candidates", params=dict(country="BR", year=2021)).json()
    assert page["total"] == 1 and page["run_id"] == result["run_id"]
    assert "text" not in page["rows"][0]
    detail = client.get(
        "/quota-staging/candidates/SPOTIFY:one", params=dict(run_id=result["run_id"])
    ).json()
    assert detail["text"].endswith("Final fixture line") and detail["blob_integrity_verified"]
    assert not detail["classification_ready"]
    assert (
        client.post(
            "/quota-staging/candidates/SPOTIFY:one", json={"classification_ready": True}
        ).status_code
        == 405
    )
    assert client.get("/quota-staging/candidates?limit=1000").status_code == 422
    assert client.get("/quota-staging/candidates/missing").status_code == 404
    application.session.close()
    application.engine.dispose()
