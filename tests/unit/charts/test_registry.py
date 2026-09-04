from datetime import UTC, datetime
from uuid import uuid4

import pytest

from chart_observatory.charts.registry import AdapterRegistration, AdapterRegistry
from chart_observatory.domain.enums import RightsOperation
from chart_observatory.domain.errors import SourceDisabled


class NeverCalledAdapter:
    called = False

    def fetch_current(self, request):
        self.called = True
        raise AssertionError("transport must not be reached")


def test_disabled_adapter_fails_before_transport() -> None:
    adapter = NeverCalledAdapter()
    registry = AdapterRegistry()
    registry.register(AdapterRegistration("SPOTIFY_CHARTS", uuid4(), adapter, enabled=False))
    with pytest.raises(SourceDisabled):
        registry.get_enabled(
            "SPOTIFY_CHARTS", RightsOperation.FETCH, datetime(2026, 9, 3, tzinfo=UTC)
        )
    assert adapter.called is False


def test_all_network_adapters_start_disabled() -> None:
    registry = AdapterRegistry.with_disabled_network_sources()
    assert registry.enabled_codes() == ()


def test_core_registry_still_operates_after_spotify_is_removed() -> None:
    registry = AdapterRegistry.with_disabled_network_sources()
    registry.unregister("SPOTIFY_CHARTS")
    registry.unregister("SPOTIFY_WEB_API")
    assert all("SPOTIFY" not in code for code in registry.registered_codes())
