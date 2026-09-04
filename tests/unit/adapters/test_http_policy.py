from dataclasses import dataclass

from chart_observatory.adapters.http import HttpPolicy, execute_http


def test_retry_after_takes_precedence_and_auth_is_permanent() -> None:
    policy = HttpPolicy(max_attempts=3, base_delay=1.0)
    assert policy.retry_delay(429, 1, {"Retry-After": "7"}) == 7.0
    assert policy.should_retry(401, 1) is False
    assert policy.should_retry(403, 1) is False
    assert policy.should_retry(429, 1) is True
    assert policy.should_retry(500, 3) is False


@dataclass
class Response:
    status_code: int
    headers: dict[str, str]


class SequenceTransport:
    def __init__(self, responses: list[Response]) -> None:
        self.responses = responses
        self.calls = 0

    def send(self, request: object) -> Response:
        response = self.responses[self.calls]
        self.calls += 1
        return response


class TimeoutThenSuccessTransport:
    def __init__(self) -> None:
        self.calls = 0

    def send(self, request: object) -> Response:
        self.calls += 1
        if self.calls == 1:
            raise TimeoutError("synthetic timeout")
        return Response(200, {})


def test_executor_honors_retry_after_then_returns_success() -> None:
    transport = SequenceTransport([Response(429, {"Retry-After": "7"}), Response(200, {})])
    delays: list[float] = []
    response = execute_http(transport, object(), HttpPolicy(max_attempts=3), sleep=delays.append)
    assert response.status_code == 200
    assert transport.calls == 2
    assert delays == [7.0]


def test_executor_never_retries_permanent_authorization_failure() -> None:
    transport = SequenceTransport([Response(401, {})])
    response = execute_http(transport, object(), HttpPolicy(max_attempts=3), sleep=lambda _: None)
    assert response.status_code == 401
    assert transport.calls == 1


def test_executor_retries_timeout_within_attempt_bound() -> None:
    transport = TimeoutThenSuccessTransport()
    delays: list[float] = []
    response = execute_http(
        transport,
        object(),
        HttpPolicy(max_attempts=2, base_delay=0),
        sleep=delays.append,
    )
    assert response.status_code == 200
    assert transport.calls == 2
    assert delays == [0.0]
