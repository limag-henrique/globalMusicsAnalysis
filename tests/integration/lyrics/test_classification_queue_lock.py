"""Session commits must not strand a PostgreSQL session-level advisory lock."""

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from chart_observatory.lyrics.classification_queue import (
    ClassificationQueueBusy,
    classification_queue_lock,
)


@pytest.mark.integration
def test_queue_lock_stays_exclusive_across_commit_and_releases_afterward() -> None:
    url = os.environ.get("CHART_OBSERVATORY_TEST_DATABASE_URL")
    if not url:
        pytest.skip("requires explicitly configured PostgreSQL test endpoint")
    engine = create_engine(url, pool_size=2, max_overflow=0)
    observer_engine = create_engine(url, poolclass=NullPool)
    try:
        # Two idle pooled connections force checkout to rotate after commit.
        with engine.connect(), engine.connect():
            pass
        with Session(engine) as owner, Session(observer_engine) as observer:
            with classification_queue_lock(owner):
                owner.execute(text("SELECT 1"))
                owner.commit()
                with classification_queue_lock(owner):
                    owner.execute(text("SELECT 1"))
                    owner.commit()
                with pytest.raises(ClassificationQueueBusy), classification_queue_lock(observer):
                    pass
                observer.rollback()
            with classification_queue_lock(observer):
                pass
    finally:
        engine.dispose()
        observer_engine.dispose()
