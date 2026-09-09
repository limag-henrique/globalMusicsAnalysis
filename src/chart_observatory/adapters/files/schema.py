from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING

import yaml  # type: ignore[import-untyped]

if TYPE_CHECKING:
    from chart_observatory.adapters.files.manual import ImportMetadata


@dataclass(frozen=True)
class ManualSchema:
    version: str
    columns: dict[str, str]
    defaults: dict[str, str | None]
    optional_columns: tuple[str, ...] = ()

    def with_metadata(self, metadata: ImportMetadata | None) -> ManualSchema:
        defaults = dict(self.defaults)
        if metadata is not None:
            defaults.update(metadata.as_defaults())
        required = (
            "platform_code",
            "source_code",
            "chart_name",
            "native_frequency",
            "metric_type",
        )
        missing = [key for key in required if not defaults.get(key)]
        if missing:
            raise ValueError(f"import metadata is missing: {', '.join(missing)}")
        return replace(self, defaults=defaults)


def load_schema(version: str, config_root: Path) -> ManualSchema:
    path = config_root / "schemas" / f"{version.removesuffix('_v1')}.yaml"
    if not path.exists() and version == "manual_generic_v1":
        path = config_root / "schemas" / "manual_generic.yaml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if payload["version"] != version:
        raise ValueError(f"schema version mismatch: {version}")
    return ManualSchema(
        payload["version"],
        payload["columns"],
        payload.get("defaults", {}),
        tuple(payload.get("optional_columns", ())),
    )
