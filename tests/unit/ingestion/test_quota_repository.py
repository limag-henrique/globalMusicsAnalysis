import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError

from chart_observatory.ingestion.quota_repository import memberships, persist_snapshot, runs


def test_repeated_import_is_idempotent_and_failed_import_is_atomic():
    engine = create_engine("sqlite://")
    row = dict(country_code="IN", year=2025, position=440, candidate_id="SPOTIFY:a")
    first = persist_snapshot(engine, {"quota": 440}, [row])
    assert first["inserted"] is True
    assert persist_snapshot(engine, {"quota": 440}, [row])["inserted"] is False
    with pytest.raises(IntegrityError):
        persist_snapshot(engine, {"quota": 440}, [row, row])
    with engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(memberships)).scalar() == 1
        assert conn.execute(select(func.count()).select_from(runs)).scalar() == 1
    engine.dispose()
