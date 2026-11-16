import importlib.util
from pathlib import Path


def module():
    path = Path(__file__).resolve().parents[2] / "scripts/verify_prioritized_corpus.py"
    spec = importlib.util.spec_from_file_location("priority_audit_test", path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def test_countries_with_more_positions_first_then_rank_and_year():
    audit = module()
    members = [
        ("v5", "BR", "2020", "SPOTIFY", 2, "br2"),
        ("v5", "BR", "2021", "SPOTIFY", 1, "br1new"),
        ("v5", "BR", "2020", "SPOTIFY", 1, "br1old"),
        ("v5", "US", "2020", "SPOTIFY", 1, "us1"),
        ("current", "US", "2026-11-14", "SPOTIFY", 1, "current"),
    ]
    priority, _ = audit.priorities(members)
    assert sorted(priority, key=priority.get) == ["br1old", "br1new", "br2", "us1", "current"]


def test_missing_text_never_passes_automated_validation():
    audit = module()
    result = audit.verify(("SPOTIFY:missing", dict(title="Song", artist="Artist"), {}))
    assert not result["has_text"]
    assert not result["body_hash_verified"]
    assert result["validation"]["identity"]["status"] != "passed"
    assert result["validation"]["completeness"]["status"] != "passed"
