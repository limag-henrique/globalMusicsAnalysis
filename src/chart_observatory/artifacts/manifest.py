import json
from dataclasses import asdict, is_dataclass
from typing import Any

_SECRET_KEYS = {"authorization", "token", "password", "secret", "api_key"}


def deterministic_manifest(value: Any) -> bytes:
    payload = asdict(value) if is_dataclass(value) else value  # type: ignore[arg-type]

    def scrub(item: Any) -> Any:
        if isinstance(item, dict):
            return {
                str(key): scrub(val)
                for key, val in sorted(item.items())
                if str(key).casefold() not in _SECRET_KEYS
            }
        if isinstance(item, (list, tuple)):
            return [scrub(element) for element in item]
        if hasattr(item, "isoformat"):
            return item.isoformat()
        return str(item) if item.__class__.__module__ == "uuid" else item

    return json.dumps(
        scrub(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
