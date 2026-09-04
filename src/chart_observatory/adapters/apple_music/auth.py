from typing import Protocol


class AppleMusicTokenProvider(Protocol):
    """Secret-backed provider; concrete credential loading stays outside the adapter."""

    def developer_token(self) -> str: ...
