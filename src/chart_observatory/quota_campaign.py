"""Local time budget and immutable ranking/country policy for an unattended campaign."""

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAMPAIGN = ROOT / "data/runtime/quota-supervisor-20261031/campaign.json"


def campaign():
    configured = os.environ.get("CHART_OBSERVATORY_CAMPAIGN_PATH")
    path = Path(configured).resolve() if configured else CAMPAIGN
    if configured and not path.is_relative_to(ROOT.resolve()):
        raise ValueError("campaign manifest outside repository")
    if configured and not path.is_file():
        raise FileNotFoundError("configured campaign manifest is missing")
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def remaining_seconds(now=None):
    config = campaign()
    if not config:
        return None
    end = datetime.fromisoformat(config["ends_at"])
    if end.tzinfo is None:
        raise ValueError("campaign deadline requires timezone")
    return max(0, (end - (now or datetime.now(UTC))).total_seconds())


def verify_frozen_inputs():
    config = campaign()
    for relative, expected in config.get("frozen_inputs", {}).items():
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT):
            raise ValueError("campaign input outside repository")
        with path.open("rb") as handle:
            actual = hashlib.file_digest(handle, "sha256").hexdigest()
        if actual != expected:
            raise ValueError("frozen ranking, quota or selection changed: " + relative)
