from __future__ import annotations

from typing import Any

import httpx


class HttpxTransport:
    """Adapter from provider request objects to an HTTPX client."""

    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self.client = httpx.Client(base_url=base_url, timeout=timeout)

    def send(self, request: Any) -> httpx.Response:
        params = dict(request.params)
        api_key = getattr(request, "api_key", None)
        if api_key:
            params["key"] = api_key
        return self.client.request(
            request.method,
            request.path,
            params=params,
            json=getattr(request, "body", None),
            headers=getattr(request, "headers", None),
        )

    def close(self) -> None:
        self.client.close()
