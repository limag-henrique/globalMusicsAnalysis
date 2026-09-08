import json

from typer.testing import CliRunner

from chart_observatory.cli import app


def test_network_source_commands_require_explicit_opt_in(monkeypatch) -> None:
    monkeypatch.setenv("YOUTUBE_DATA_API_KEY", "configured")

    class UnexpectedTransport:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("network transport must not be constructed")

    monkeypatch.setattr("chart_observatory.cli.HttpxTransport", UnexpectedTransport)

    result = CliRunner().invoke(app, ["sources", "youtube", "discover"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "provider": "YOUTUBE_DATA_API",
        "status": "NETWORK_DISABLED",
    }


def test_public_source_discovery_requires_explicit_opt_in() -> None:
    result = CliRunner().invoke(app, ["sources", "promusica", "discover"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "provider": "PRO_MUSICA_BRASIL",
        "status": "NETWORK_DISABLED",
    }


def test_kaggle_download_requires_explicit_opt_in(monkeypatch) -> None:
    class UnexpectedSource:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("download must not be attempted")

    monkeypatch.setattr("chart_observatory.cli.KaggleSpotifyChartsSource", UnexpectedSource)

    result = CliRunner().invoke(app, ["sources", "kaggle", "download"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "provider": "KAGGLE_DHRUVILDAVE",
        "status": "NETWORK_DISABLED",
    }
