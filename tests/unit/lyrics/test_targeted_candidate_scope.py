import importlib.util
import json
from pathlib import Path

import pytest


def module():
    path = Path(__file__).resolve().parents[3] / "scripts/autonomous_lyrics.py"
    spec = importlib.util.spec_from_file_location("targeted_scope_test", path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def test_targeted_filter_preserves_payloads_and_excludes_other_candidates(tmp_path):
    script = module()
    rows = [
        dict(
            recording_id="SPOTIFY:a",
            title="Song (Live)",
            chart_bindings=[dict(country_code="IL", year=2024, position=120)],
        ),
        dict(recording_id="SPOTIFY:b"),
    ]
    path = tmp_path / "ids.jsonl"
    path.write_text(json.dumps(dict(candidate_id="SPOTIFY:a")) + "\n", encoding="utf-8")
    selected, digest = script.filter_targeted_candidates(rows, path)
    assert selected == rows[:1]
    assert selected[0] is rows[0]
    assert len(digest) == 64


@pytest.mark.parametrize("content", ["", '{"candidate_id":"outside-selection"}\n'])
def test_empty_or_foreign_candidate_scope_rejected(tmp_path, content):
    script = module()
    path = tmp_path / "ids.jsonl"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="within current selection"):
        script.filter_targeted_candidates([dict(recording_id="SPOTIFY:a")], path)
