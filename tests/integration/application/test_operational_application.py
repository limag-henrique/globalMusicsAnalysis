from pathlib import Path

from fastapi.testclient import TestClient

from chart_observatory.api.app import create_app
from chart_observatory.application import ResearchApplication


def test_configured_api_application_uses_the_same_database_after_restart(tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'operational.sqlite3').as_posix()}"
    first = ResearchApplication(
        tmp_path / "runtime", database_url=database_url, manual_authorized=True
    )
    client = TestClient(create_app(first))

    assert client.get("/rankings").json() == {"rows": []}

    second_client = TestClient(create_app(database_url=database_url, root=tmp_path / "runtime"))

    assert second_client.get("/rankings").json() == {"rows": []}
