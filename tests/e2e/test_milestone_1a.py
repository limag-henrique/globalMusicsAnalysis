from pathlib import Path

from fastapi.testclient import TestClient

from chart_observatory.api.app import create_app
from chart_observatory.application import LocalResearchApplication

FIXTURE = Path(__file__).parents[1] / "fixtures" / "manual" / "valid_daily.csv"


def test_milestone_1a_without_spotify(tmp_path) -> None:
    service = LocalResearchApplication(tmp_path, manual_authorized=True)
    client = TestClient(create_app(service))
    preview = client.post("/imports/preview", json={"path": str(FIXTURE)}).json()
    assert preview["valid_rows"] == 3
    result = client.post("/imports/apply", json={"token": preview["token"]}).json()
    assert result["entry_count"] == 3
    assert client.get("/rankings", params={"country": "BR"}).json()["rows"]
    assert client.get("/coverage", params={"country": "BR"}).json()["cells"]
    assert client.get("/provenance").json()["artifacts"]
    assert client.get("/resolution").json()["unresolved"] == 3
    exported = client.post(
        "/exports", json={"dataset_name": "chart_observations", "format": "parquet"}
    ).json()
    assert len(exported["manifest_sha256"]) == 64
