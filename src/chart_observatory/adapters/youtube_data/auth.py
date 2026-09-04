from typing import Protocol


class YouTubeApiKeyProvider(Protocol):
    def api_key(self) -> str: ...
