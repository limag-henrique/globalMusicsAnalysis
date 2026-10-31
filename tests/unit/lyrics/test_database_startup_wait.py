import importlib.util
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import OperationalError


def worker_module():
    path = Path(__file__).resolve().parents[3] / "scripts/autonomous_lyrics.py"
    spec = importlib.util.spec_from_file_location("startup_wait_worker", path)
    worker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(worker)
    return worker


def test_startup_waits_for_database_recovery_then_disposes_probe_engine(monkeypatch):
    worker = worker_module()
    calls, statuses, disposed = [], [], []

    def connect():
        calls.append(1)
        if len(calls) < 3:
            raise OperationalError("SELECT 1", {}, Exception("starting up"))
        return nullcontext(
            SimpleNamespace(execute=lambda statement: SimpleNamespace(scalar_one=lambda: 1))
        )

    engine = SimpleNamespace(connect=connect, dispose=lambda: disposed.append(True))
    monkeypatch.setattr(worker, "create_engine", lambda *args, **kwargs: engine)
    monkeypatch.setattr(worker, "report", lambda stage, **kwargs: statuses.append(stage))
    monkeypatch.setattr(worker.time, "sleep", lambda seconds: None)
    worker.wait_for_database()
    assert len(calls) == 3 and disposed == [True]
    assert statuses == ["waiting_for_database", "waiting_for_database"]


def test_startup_stops_before_queue_preparation_if_database_stays_unavailable(monkeypatch):
    worker = worker_module()
    disposed = []

    def unavailable():
        raise OperationalError("SELECT 1", {}, Exception("starting up"))

    monkeypatch.setattr(
        worker,
        "create_engine",
        lambda *args, **kwargs: SimpleNamespace(
            connect=unavailable, dispose=lambda: disposed.append(True)
        ),
    )
    with pytest.raises(TimeoutError, match="did not become ready"):
        worker.wait_for_database(timeout=0)
    assert disposed == [True]
