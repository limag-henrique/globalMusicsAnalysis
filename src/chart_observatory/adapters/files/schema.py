from dataclasses import dataclass
from pathlib import Path

import yaml  # type: ignore[import-untyped]


@dataclass(frozen=True)
class ManualSchema:
    version: str
    columns: dict[str, str]
    defaults: dict[str, str]


def load_schema(version: str, config_root: Path) -> ManualSchema:
    path = config_root / "schemas" / f"{version.removesuffix('_v1')}.yaml"
    if not path.exists() and version == "manual_generic_v1":
        path = config_root / "schemas" / "manual_generic.yaml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if payload["version"] != version:
        raise ValueError(f"schema version mismatch: {version}")
    return ManualSchema(payload["version"], payload["columns"], payload["defaults"])
