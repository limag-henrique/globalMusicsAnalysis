import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def updater(monkeypatch):
    scripts = Path(__file__).resolve().parents[3] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location(
        "validation_update_test", scripts / "import_validation_updates.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_first_snapshot_is_imported_and_unchanged_state_never_duplicates(updater):
    state = dict(fingerprint="same", with_text=100)
    assert updater.needs_refresh(None, state, 0)
    assert not updater.needs_refresh(state, state, 100000)


def test_new_texts_refresh_at_threshold_without_waiting_for_collector_end(updater):
    previous = dict(fingerprint="before", with_text=100)
    assert updater.needs_refresh(previous, dict(fingerprint="after", with_text=200), 1)
    assert not updater.needs_refresh(previous, dict(fingerprint="after", with_text=101), 60)


def test_repaired_version_with_same_count_is_eventually_imported(updater):
    previous = dict(fingerprint="old-text", with_text=100)
    current = dict(fingerprint="corrected-text", with_text=100)
    assert not updater.needs_refresh(previous, current, 60)
    assert updater.needs_refresh(previous, current, 1800)


def test_offline_recovery_is_imported_even_before_live_collector_applies_it(updater):
    previous = dict(fingerprint="before", with_text=100, offline_proposals=0)
    current = dict(fingerprint="after", with_text=100, offline_proposals=3)
    assert updater.needs_refresh(previous, current, 1)
