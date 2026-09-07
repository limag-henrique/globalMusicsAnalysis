import json
from dataclasses import dataclass
from datetime import date

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
