from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from chart_observatory.adapters.disabled import DisabledChartSource
from chart_observatory.domain.enums import RightsOperation, SourceCode
from chart_observatory.domain.errors import SourceDisabled
from chart_observatory.rights.gate import RightsGate


@dataclass(frozen=True)
class AdapterRegistration:
    source_code: str
    source_id: UUID
    adapter: Any
    enabled: bool = False


class AdapterRegistry:
    def __init__(self, rights_gate: RightsGate | None = None) -> None:
        self._registrations: dict[str, AdapterRegistration] = {}
        self._rights_gate = rights_gate

    def register(self, registration: AdapterRegistration) -> None:
        self._registrations[registration.source_code] = registration

    def unregister(self, source_code: str) -> None:
        self._registrations.pop(source_code, None)

    def registered_codes(self) -> tuple[str, ...]:
        return tuple(sorted(self._registrations))

    def get_enabled(
        self, source_code: str, operation: RightsOperation, occurred_at: datetime
    ) -> Any:
        registration = self._registrations.get(source_code)
        if registration is None or not registration.enabled:
            raise SourceDisabled(f"{source_code} is disabled")
        if self._rights_gate is not None:
            self._rights_gate.require(registration.source_id, operation, occurred_at)
        return registration.adapter

    def enabled_codes(self) -> tuple[str, ...]:
        return tuple(sorted(code for code, value in self._registrations.items() if value.enabled))

    @classmethod
    def with_disabled_network_sources(cls) -> "AdapterRegistry":
        registry = cls()
        for code in SourceCode:
            if code is SourceCode.MANUAL_AUTHORIZED_FILE:
                continue
            source_id = uuid5(NAMESPACE_URL, f"chart-observatory:{code}")
            registry.register(
                AdapterRegistration(str(code), source_id, DisabledChartSource(str(code)), False)
            )
        return registry
