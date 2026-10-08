import importlib.util
from pathlib import Path

from chart_observatory.db.models.lyrics_batch import (
    LyricClassificationBatchItem,
    LyricClassificationBatchRun,
)


def test_batch_metadata_has_active_signature_index() -> None:
    index = next(
        item
        for item in LyricClassificationBatchItem.__table__.indexes
        if item.name == "uq_lyric_batch_items_active_signature"
    )

    assert index.unique is True
    assert index.dialect_options["postgresql"]["where"] is not None


def test_migration_follows_queue_revision_and_has_safe_revision_length() -> None:
    path = (
        Path(__file__).parents[3]
        / "migrations"
        / "versions"
        / "0015_gemini_batch_classification.py"
    )
    specification = importlib.util.spec_from_file_location("batch_migration", path)
    assert specification is not None and specification.loader is not None
    migration = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(migration)

    assert migration.down_revision == "0014_lyric_classification_queue"
    assert len(migration.revision) <= 32


def test_run_ledger_records_exact_provider_output_object_names() -> None:
    assert "output_object_names" in LyricClassificationBatchRun.__table__.columns
