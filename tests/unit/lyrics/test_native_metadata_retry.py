import importlib.util
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "responses,expected_calls,expected_waits,min_delay",
    [
        ([{"status": 504, "resolved_progress": 10}] * 3 + [None], 4, 3, 60),
        ([{"status": 504, "resolved_progress": 0}] * 3, 3, 2, 60),
        ([{"status": 403, "resolved_progress": 10}], 1, 0, 0),
        ([{"status": 429, "resolved_progress": 10}] * 3, 3, 2, 900),
    ],
)
def test_native_retry_distinguishes_progress_access_denial_and_rate_limit(
    tmp_path, monkeypatch, responses, expected_calls, expected_waits, min_delay
):
    root = Path(__file__).resolve().parents[3]
    monkeypatch.syspath_prepend(str(root / "scripts"))
    spec = importlib.util.spec_from_file_location(
        "native_metadata_retry_worker", root / "scripts/collect_native_spotify_metadata.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.STATE = tmp_path
    responses = iter(responses)
    calls = []
    waits = []

    def collect(base, deadline):
        calls.append(base)
        return next(responses)

    monkeypatch.setattr(module, "collect", collect)
    monkeypatch.setattr(
        module, "wait_until", lambda deadline: waits.append(deadline - module.time.time())
    )
    module.run(tmp_path)
    assert len(calls) == expected_calls and len(waits) == expected_waits
    assert all(delay >= min_delay - 1 for delay in waits)
