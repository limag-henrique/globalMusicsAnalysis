import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

SPEC = importlib.util.spec_from_file_location(
    "rebuilt_delta", Path(__file__).resolve().parents[3] / "scripts/recover_v4_lyric_delta.py"
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_corrupt_inherited_text_is_rejected_before_staging():
    payload = dict(recording_id="SPOTIFY:a", title="A", artist="B", chart_bindings=[])
    snapshot = {"SPOTIFY:a": (payload, {}, "text", "0" * 64)}
    with pytest.raises(ValueError, match="hash mismatch"):
        module.stage_records([payload], snapshot, SimpleNamespace())


def test_exact_id_inheritance_retains_new_bindings_without_approval():
    payload = dict(recording_id="SPOTIFY:a", title="A", artist="B", chart_bindings=[])
    body = "A real preserved text"
    digest = hashlib.sha256(body.encode()).hexdigest()
    snapshot = {"SPOTIFY:a": (payload, {}, body, digest)}
    records, texts = module.stage_records([payload], snapshot, SimpleNamespace())
    assert texts == {digest: body}
    assert records[0]["audit"]["classification_ready"] is False
    assert records[0]["payload"] == payload


def test_changed_display_identity_is_flagged_on_exact_id_inheritance():
    payload = dict(recording_id="SPOTIFY:a", title="A", artist="B", chart_bindings=[])
    body = "A real preserved text"
    digest = hashlib.sha256(body.encode()).hexdigest()
    snapshot = {"SPOTIFY:a": ({**payload, "artist": "Another artist"}, {}, body, digest)}
    records, _ = module.stage_records([payload], snapshot, SimpleNamespace())
    assert "retrieval_metadata_requires_reconciliation" in records[0]["audit"]["text_quality_flags"]
