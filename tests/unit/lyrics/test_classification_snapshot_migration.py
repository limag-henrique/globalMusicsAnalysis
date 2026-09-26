import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateTable

from chart_observatory.db.base import Base
from chart_observatory.db.models.corpus import LyricClassificationSnapshot

MIGRATION_PATH = (
    Path(__file__).parents[3]
    / "migrations"
    / "versions"
    / "0013_lyric_classification_snapshots.py"
)
SIGNATURE_INDEX = (
    "ix_lyric_classification_snapshots_signature",
    ("canonical_track_id", "lyrics_hash", "model_id", "taxonomy_version", "prompt_version"),
)
STATUS_INDEX = (
    "ix_lyric_classification_snapshots_classification_status",
    ("classification_status",),
)


class RecordingOperations:
    def __init__(self, dialect_name: str) -> None:
        self.dialect_name = dialect_name
        self.executed: list[str] = []
        self.indexes: list[tuple[str, tuple[str, ...]]] = []
        self.dropped_indexes: list[str] = []
        self.created_tables: list[str] = []
        self.dropped_tables: list[str] = []

    def get_bind(self) -> SimpleNamespace:
        return SimpleNamespace(dialect=SimpleNamespace(name=self.dialect_name))

    def create_table(self, name: str, *columns: object) -> None:
        self.created_tables.append(name)

    def create_index(self, name: str, table_name: str, columns: list[str]) -> None:
        assert table_name == "lyric_classification_snapshots"
        self.indexes.append((name, tuple(columns)))

    def drop_index(self, name: str, *, table_name: str) -> None:
        assert table_name == "lyric_classification_snapshots"
        self.dropped_indexes.append(name)

    def drop_table(self, name: str) -> None:
        self.dropped_tables.append(name)

    def execute(self, statement: str) -> None:
        self.executed.append(statement)


@pytest.fixture
def migration_module() -> ModuleType:
    specification = importlib.util.spec_from_file_location("snapshot_migration", MIGRATION_PATH)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_snapshot_metadata_indexes_match_migration_contract() -> None:
    """Catches ORM indexes that Alembic would try to add after this migration."""
    indexes = {
        (index.name, tuple(column.name for column in index.columns))
        for index in LyricClassificationSnapshot.__table__.indexes
    }

    assert indexes == {SIGNATURE_INDEX, STATUS_INDEX}


def test_revision_fits_alembic_version_column(migration_module: ModuleType) -> None:
    """Alembic's default version table stores revision IDs in VARCHAR(32)."""
    assert len(migration_module.revision) <= 32


def test_metadata_uses_postgresql_identity_and_sqlite_generated_append_order() -> None:
    """Catches metadata DDL that diverges from the migration's dialect-specific append key."""
    postgresql_ddl = str(
        CreateTable(LyricClassificationSnapshot.__table__).compile(dialect=postgresql.dialect())
    )

    assert "append_order BIGINT GENERATED ALWAYS AS IDENTITY" in postgresql_ddl

    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                """
                INSERT INTO lyric_classification_snapshots (
                    id, lyric_document_id, canonical_track_id, lyrics_hash, model_id,
                    taxonomy_version, prompt_version, classification_status, classified_at
                ) VALUES (
                    '00000000-0000-0000-0000-000000000011',
                    '00000000-0000-0000-0000-000000000012',
                    '00000000-0000-0000-0000-000000000013',
                    'a', 'model', 'taxonomy', 'prompt', 'classified', CURRENT_TIMESTAMP
                )
                """
            )
        )

        assert connection.scalar(
            sa.text("SELECT append_order FROM lyric_classification_snapshots")
        ) == 1


def test_postgresql_migration_adds_and_removes_database_immutability(
    migration_module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Catches a PostgreSQL migration that leaves direct SQL updates or deletes possible."""
    operations = RecordingOperations("postgresql")
    monkeypatch.setattr(migration_module, "op", operations)

    migration_module.upgrade()
    migration_module.downgrade()

    assert operations.indexes == [SIGNATURE_INDEX, STATUS_INDEX]
    assert any(
        "CREATE FUNCTION prevent_lyric_classification_snapshot_mutation" in sql
        for sql in operations.executed
    )
    assert any(
        "CREATE TRIGGER lyric_classification_snapshots_immutable" in sql
        for sql in operations.executed
    )
    assert any(
        "DROP TRIGGER IF EXISTS lyric_classification_snapshots_immutable" in sql
        for sql in operations.executed
    )
    assert any(
        "DROP FUNCTION IF EXISTS prevent_lyric_classification_snapshot_mutation" in sql
        for sql in operations.executed
    )


def test_sqlite_migration_generates_append_order_and_rejects_raw_mutation(
    migration_module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Catches a SQLite migration that permits direct snapshot updates or deletes."""
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        monkeypatch.setattr(
            migration_module,
            "op",
            Operations(MigrationContext.configure(connection)),
        )
        migration_module.upgrade()
        connection.execute(
            sa.text(
                """
                INSERT INTO lyric_classification_snapshots (
                    id, lyric_document_id, canonical_track_id, lyrics_hash, model_id,
                    taxonomy_version, prompt_version, classification_status, classified_at
                ) VALUES (
                    '00000000-0000-0000-0000-000000000001',
                    '00000000-0000-0000-0000-000000000002',
                    '00000000-0000-0000-0000-000000000003',
                    'a', 'model', 'taxonomy', 'prompt', 'classified', CURRENT_TIMESTAMP
                )
                """
            )
        )

        assert connection.scalar(
            sa.text("SELECT append_order FROM lyric_classification_snapshots")
        ) == 1
        with pytest.raises(IntegrityError, match="immutable"):
            connection.execute(
                sa.text(
                    "UPDATE lyric_classification_snapshots SET confidence = 0.5"
                )
            )
        with pytest.raises(IntegrityError, match="immutable"):
            connection.execute(sa.text("DELETE FROM lyric_classification_snapshots"))

        migration_module.downgrade()
