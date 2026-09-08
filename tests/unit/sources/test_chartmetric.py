import json
from dataclasses import dataclass
from datetime import date

from typer.testing import CliRunner

from chart_observatory.cli import app
from chart_observatory.sources.chartmetric import ChartmetricClient


@dataclass
class Response:
    status_code: int
    content: bytes
    headers: dict[str, str]


class Transport:
    def __init__(self, responses: list[Response]) -> None:
        self.responses = responses
        self.requests = []

    def send(self, request: object) -> Response:
        self.requests.append(request)
        return self.responses.pop(0)


def response(
    status: int, body: dict[str, object], headers: dict[str, str] | None = None
) -> Response:
    return Response(status, json.dumps(body).encode(), headers or {})


def test_token_is_cached_and_collection_maps_spotify_rows() -> None:
    transport = Transport(
        [
            response(200, {"token": "access", "expires_in": 3600}),
            response(
                200,
                {
                    "obj": [
                        {
                            "rank": 1,
                            "trackName": "Song",
                            "artists": [{"name": "Artist"}],
                            "trackId": 7,
                            "plays": 10,
                        }
                    ]
                },
            ),
        ]
    )
    client = ChartmetricClient("refresh", transport=transport, clock=lambda: 1000)
    rows = client.collect_chart(
        platform="spotify",
        country_code="BR",
        interval="daily",
        chart_type="regional",
        period=date(2022, 1, 1),
    )
    assert rows[0].provider == "CHARTMETRIC"
    assert rows[0].origin_platform == "SPOTIFY"
    assert rows[0].metric_value == 10
    assert len(transport.requests) == 2
    client.access_token()
    assert len(transport.requests) == 2


def test_401_mints_one_new_access_token() -> None:
    transport = Transport(
        [
            response(200, {"token": "first", "expires_in": 3600}),
            response(401, {}),
            response(200, {"token": "second", "expires_in": 3600}),
            response(200, {"obj": []}),
        ]
    )
    client = ChartmetricClient("refresh", transport=transport, clock=lambda: 1000)
    assert client.get("/api/charts/spotify") == {"obj": []}
    assert len(transport.requests) == 4


def test_chart_dates_are_parsed_from_timestamp_rows() -> None:
    transport = Transport(
        [
            response(200, {"token": "access", "expires_in": 3600}),
            response(
                200,
                {
                    "obj": [
                        {"timestp": "2025-04-23T07:00:00.000Z"},
                        {"timestp": "2025-04-13T07:00:00.000Z"},
                        {"timestp": "2025-04-23T07:00:00.000Z"},
                    ]
                },
            ),
        ]
    )
    client = ChartmetricClient("refresh", transport=transport, clock=lambda: 1000)

    dates = client.chart_dates("spotify_track", from_days_ago=30)

    assert dates == (date(2025, 4, 23), date(2025, 4, 13))
    assert transport.requests[1].path == "/api/charts/spotify_track/dates"
    assert transport.requests[1].params == {"fromDaysAgo": 30}


def test_collection_uses_server_page_and_applies_client_limit() -> None:
    transport = Transport(
        [
            response(200, {"token": "access", "expires_in": 3600}),
            response(
                200,
                {
                    "obj": {
                        "length": 200,
                        "data": [
                            {"rank": 1, "trackName": "First", "trackId": 1},
                            {"rank": 2, "trackName": "Second", "trackId": 2},
                        ],
                    }
                },
            ),
        ]
    )
    client = ChartmetricClient("refresh", transport=transport, clock=lambda: 1000)

    rows = client.collect_chart(
        platform="spotify",
        country_code="BR",
        interval="daily",
        chart_type="plays",
        period=date(2025, 4, 23),
        limit=1,
    )

    assert [row.track_title for row in rows] == ["First"]
    assert "limit" not in transport.requests[1].params


def test_collection_maps_current_chartmetric_artist_names() -> None:
    transport = Transport(
        [
            response(200, {"token": "access", "expires_in": 3600}),
            response(
                200,
                {
                    "obj": {
                        "length": 1,
                        "data": [
                            {
                                "rank": 1,
                                "name": "Song",
                                "artist_names": ["Artist One", "Artist Two"],
                                "cm_track": 99,
                            }
                        ],
                    }
                },
            ),
        ]
    )
    client = ChartmetricClient("refresh", transport=transport, clock=lambda: 1000)

    rows = client.collect_chart(
        platform="spotify",
        country_code="BR",
        interval="daily",
        chart_type="plays",
        period=date(2025, 4, 23),
    )

    assert rows[0].artist == "Artist One, Artist Two"


def test_403_is_reported_without_retry() -> None:
    from chart_observatory.sources.chartmetric import ChartmetricError

    transport = Transport(
        [response(200, {"token": "first", "expires_in": 3600}), response(403, {})]
    )
    client = ChartmetricClient("refresh", transport=transport, clock=lambda: 1000)
    try:
        client.get("/api/charts/spotify")
    except ChartmetricError as error:
        assert error.status_code == 403
    else:
        raise AssertionError("expected ChartmetricError")


def test_collect_chart_pages_resumes_from_a_checkpoint(tmp_path) -> None:
    transport = Transport(
        [
            response(200, {"token": "access", "expires_in": 3600}),
            response(
                200,
                {
                    "obj": {
                        "data": [
                            {"rank": 1, "trackName": "First", "trackId": 1},
                        ],
                        "next_offset": 1,
                    }
                },
            ),
            response(200, {"obj": {"data": []}}),
        ]
    )
    checkpoint = tmp_path / "chartmetric-checkpoint.json"
    client = ChartmetricClient("refresh", transport=transport, clock=lambda: 1000)

    rows = client.collect_chart_pages(
        platform="spotify",
        country_code="BR",
        interval="daily",
        chart_type="regional",
        period=date(2022, 1, 1),
        page_size=1,
        checkpoint_path=checkpoint,
    )

    assert [row.track_title for row in rows] == ["First"]
    assert [request.params["offset"] for request in transport.requests[1:]] == [0, 1]
    assert json.loads(checkpoint.read_text(encoding="utf-8"))["status"] == "COMPLETE"
    assert (
        client.collect_chart_pages(
            platform="spotify",
            country_code="BR",
            interval="daily",
            chart_type="regional",
            period=date(2022, 1, 1),
            page_size=1,
            checkpoint_path=checkpoint,
        )
        == ()
    )
    assert len(transport.requests) == 3


def test_collect_chart_pages_keeps_checkpoint_when_page_budget_is_reached(tmp_path) -> None:
    transport = Transport(
        [
            response(200, {"token": "access", "expires_in": 3600}),
            response(
                200,
                {
                    "obj": {
                        "data": [{"rank": 1, "trackName": "First", "trackId": 1}],
                        "next_offset": 1,
                    }
                },
            ),
        ]
    )
    checkpoint = tmp_path / "chartmetric-checkpoint.json"
    client = ChartmetricClient("refresh", transport=transport, clock=lambda: 1000)

    client.collect_chart_pages(
        platform="spotify",
        country_code="BR",
        interval="daily",
        chart_type="regional",
        period=date(2022, 1, 1),
        page_size=1,
        checkpoint_path=checkpoint,
        max_pages=1,
    )

    saved = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert saved["status"] == "PAUSED"
    assert saved["next_offset"] == 1


def test_collect_chart_pages_checkpoints_after_a_page_before_a_later_failure(tmp_path) -> None:
    from chart_observatory.sources.chartmetric import ChartmetricError

    transport = Transport(
        [
            response(200, {"token": "access", "expires_in": 3600}),
            response(
                200,
                {
                    "obj": {
                        "data": [{"rank": 1, "trackName": "First", "trackId": 1}],
                        "next_offset": 1,
                    }
                },
            ),
            response(403, {}),
        ]
    )
    checkpoint = tmp_path / "chartmetric-checkpoint.json"
    client = ChartmetricClient("refresh", transport=transport, clock=lambda: 1000)

    try:
        client.collect_chart_pages(
            platform="spotify",
            country_code="BR",
            interval="daily",
            chart_type="regional",
            period=date(2022, 1, 1),
            page_size=1,
            checkpoint_path=checkpoint,
        )
    except ChartmetricError:
        pass
    else:
        raise AssertionError("expected the second page to fail")

    saved = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert saved["status"] == "PAUSED"
    assert saved["next_offset"] == 1


def test_collect_command_is_bounded_and_requires_network_opt_in() -> None:
    result = CliRunner().invoke(
        app,
        [
            "sources",
            "chartmetric",
            "collect",
            "--platform",
            "spotify",
            "--country-code",
            "BR",
            "--interval",
            "daily",
            "--chart-type",
            "regional",
            "--period",
            "2022-01-01",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "provider": "CHARTMETRIC",
        "status": "NETWORK_DISABLED",
    }


def test_chart_dates_command_requires_network_opt_in() -> None:
    result = CliRunner().invoke(
        app,
        [
            "sources",
            "chartmetric",
            "dates",
            "--streaming-type",
            "spotify_track",
            "--from-days-ago",
            "28",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "provider": "CHARTMETRIC",
        "status": "NETWORK_DISABLED",
    }


def test_auth_and_discover_commands_require_network_opt_in(monkeypatch) -> None:
    monkeypatch.setenv("CHARTMETRIC_REFRESH_TOKEN", "refresh-token")

    class UnexpectedTransport:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("network transport must not be constructed")

    monkeypatch.setattr("chart_observatory.cli.HttpxTransport", UnexpectedTransport)

    for command in ("auth-test", "discover"):
        result = CliRunner().invoke(app, ["sources", "chartmetric", command])
        assert result.exit_code == 0
        assert json.loads(result.stdout) == {
            "provider": "CHARTMETRIC",
            "status": "NETWORK_DISABLED",
        }
