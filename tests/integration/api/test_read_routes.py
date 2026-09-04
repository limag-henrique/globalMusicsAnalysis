from fastapi.testclient import TestClient

from chart_observatory.api.app import create_app
from chart_observatory.application import LocalResearchApplication


def test_read_routes_are_available_without_provider_network(tmp_path) -> None:
    client = TestClient(create_app(LocalResearchApplication(tmp_path)))
    assert client.get("/rankings").json() == {"rows": []}
    assert client.get("/coverage").json() == {"cells": []}
    assert client.get("/rights").json()["import_allowed"] is False
    assert client.get("/resolution").json()["status"] == "EMPTY"
