import json

from typer.testing import CliRunner

from chart_observatory.cli import app


def test_chartmetric_dates_accepts_provider_all_history_window(monkeypatch) -> None:
    monkeypatch.setenv("CHARTMETRIC_REFRESH_TOKEN", "refresh-token")

    result = CliRunner().invoke(
        app,
        [
            "sources",
            "chartmetric",
            "dates",
            "--streaming-type",
            "spotify_tracks",
            "--from-days-ago",
            "9999",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"provider": "CHARTMETRIC", "status": "NETWORK_DISABLED"}


def test_chartmetric_platform_inventory_command_is_network_gated(monkeypatch) -> None:
    monkeypatch.setenv("CHARTMETRIC_REFRESH_TOKEN", "refresh-token")

    result = CliRunner().invoke(app, ["sources", "chartmetric", "platforms"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"provider": "CHARTMETRIC", "status": "NETWORK_DISABLED"}

