import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HttpPolicy:
    max_attempts: int = 4
    base_delay: float = 0.5
    connect_timeout: float = 5.0
    read_timeout: float = 20.0

    def should_retry(self, status_code: int, attempt: int) -> bool:
        return attempt < self.max_attempts and (status_code == 429 or status_code >= 500)

    def retry_delay(
        self, status_code: int, attempt: int, headers: dict[str, str] | None = None
    ) -> float:
        headers = headers or {}
        retry_after = next(
            (value for key, value in headers.items() if key.casefold() == "retry-after"), None
        )
        if status_code == 429 and retry_after is not None:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                pass
        ceiling = self.base_delay * (2 ** max(0, attempt - 1))
        return random.uniform(ceiling / 2, ceiling)


def execute_http(
    transport: Any,
    request: object,
    policy: HttpPolicy,
    *,
    sleep: Callable[[float], object] = time.sleep,
    on_attempt: Callable[[], object] | None = None,
) -> Any:
    for attempt in range(1, policy.max_attempts + 1):
        if on_attempt is not None:
            on_attempt()
        try:
            response = transport.send(request)
        except TimeoutError:
            if attempt >= policy.max_attempts:
                raise
            sleep(policy.retry_delay(503, attempt))
            continue
        if not policy.should_retry(response.status_code, attempt):
            return response
        sleep(policy.retry_delay(response.status_code, attempt, response.headers))
    raise RuntimeError("HTTP retry loop ended without a response")
