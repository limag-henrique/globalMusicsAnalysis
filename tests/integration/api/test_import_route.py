from pathlib import Path

from fastapi.testclient import TestClient

from chart_observatory.api.app import create_app
from chart_observatory.application import LocalResearchApplication


FIXTURE = Path(__file__).parents[2] / "fixtures" / "manual" / "valid_daily.csv"


def test_preview_then_authorized_apply_is_idempotent(tmp_path) -> None:
    client = TestClient(create_app(LocalResearchApplication(tmp_path, manual_authorized=True)))
    preview = client.post("/imports/preview", json={"path": str(FIXTURE)}).json()
    first = client.post("/imports/apply", json={"token": preview["token"]}).json()
    second = client.post("/imports/apply", json={"token": preview["token"]}).json()
    assert first["entry_count"] == 3
    assert second["snapshot_id"] == first["snapshot_id"]
    assert second["entry_count"] == 0
