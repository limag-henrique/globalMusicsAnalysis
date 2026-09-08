from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ModelResult:
    model_name: str
    formula: str
    status: str
    n_observations: int
    coefficients: dict[str, float] = field(default_factory=dict)
    ci_low: dict[str, float] = field(default_factory=dict)
    ci_high: dict[str, float] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
