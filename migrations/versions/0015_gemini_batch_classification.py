"""Add the Gemini batch operational ledger and snapshot traceability."""

import sqlalchemy as sa
from alembic import op

revision = "0015_gemini_batch"
down_revision = "0014_lyric_classification_queue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lyric_classification_batch_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("model_id", sa.String(160), nullable=False),
        sa.Column("provider_model_version", sa.String(200)),
        sa.Column("taxonomy_version", sa.String(80), nullable=False),
        sa.Column("prompt_version", sa.String(80), nullable=False),
        sa.Column("thinking_level", sa.String(16), nullable=False),
        sa.Column("project_id", sa.String(200), nullable=False),
        sa.Column("location", sa.String(40), nullable=False),
        sa.Column("bucket_name", sa.String(222), nullable=False),
        sa.Column("source_uri", sa.Text()),
        sa.Column("source_generation", sa.BigInteger()),
        sa.Column("source_sha256", sa.String(64)),
        sa.Column("source_byte_count", sa.BigInteger()),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_uri_prefix", sa.Text()),
        sa.Column("output_object_names", sa.JSON()),
        sa.Column("provider_job_name", sa.Text(), unique=True),
        sa.Column("expected_cost_usd", sa.Numeric(20, 10)),
        sa.Column("conservative_cost_usd", sa.Numeric(20, 10)),
        sa.Column("known_cost_usd", sa.Numeric(20, 10)),
        sa.Column("provider_successful_count", sa.Integer()),
        sa.Column("provider_failed_count", sa.Integer()),
        sa.Column("imported_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("job_error_code", sa.String(100)),
        sa.Column("job_error_message", sa.Text()),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("terminal_at", sa.DateTime(timezone=True)),
        sa.Column("imported_at", sa.DateTime(timezone=True)),
        sa.Column("cleaned_at", sa.DateTime(timezone=True)),
        sa.Column("pilot_accepted_at", sa.DateTime(timezone=True)),
        sa.Column("pilot_accepted_by", sa.String(200)),
        sa.Column("summary_written", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_lyric_batch_runs_kind", "lyric_classification_batch_runs", ["kind"])
    op.create_index("ix_lyric_batch_runs_state", "lyric_classification_batch_runs", ["state"])
    op.create_table(
        "lyric_classification_batch_items",
        sa.Column("opaque_key", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "batch_run_id",
            sa.Uuid(),
            sa.ForeignKey("lyric_classification_batch_runs.id"),
            nullable=False,
        ),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column(
            "lyric_document_id", sa.Uuid(), sa.ForeignKey("lyric_documents.id"), nullable=False
        ),
        sa.Column(
            "canonical_track_id", sa.Uuid(), sa.ForeignKey("canonical_tracks.id"), nullable=False
        ),
        sa.Column("lyrics_hash", sa.String(64), nullable=False),
        sa.Column("model_id", sa.String(160), nullable=False),
        sa.Column("taxonomy_version", sa.String(80), nullable=False),
        sa.Column("prompt_version", sa.String(80), nullable=False),
        sa.Column("request_sha256", sa.String(64)),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column(
            "snapshot_id",
            sa.Uuid(),
            sa.ForeignKey("lyric_classification_snapshots.id"),
            unique=True,
        ),
        sa.Column(
            "retry_of_snapshot_id", sa.Uuid(), sa.ForeignKey("lyric_classification_snapshots.id")
        ),
        sa.Column("provider_status", sa.String(80)),
        sa.Column("error_code", sa.String(100)),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("imported_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("batch_run_id", "line_number", name="uq_lyric_batch_item_line"),
    )
    for name, columns in (
        ("ix_lyric_batch_items_run", ["batch_run_id"]),
        ("ix_lyric_batch_items_document", ["lyric_document_id"]),
        ("ix_lyric_batch_items_track", ["canonical_track_id"]),
        ("ix_lyric_batch_items_state", ["state"]),
    ):
        op.create_index(name, "lyric_classification_batch_items", columns)
    op.create_index(
        "uq_lyric_batch_items_active_signature",
        "lyric_classification_batch_items",
        ["canonical_track_id", "lyrics_hash", "model_id", "taxonomy_version", "prompt_version"],
        unique=True,
        postgresql_where=sa.text("state IN ('reserved','submitted','running')"),
        sqlite_where=sa.text("state IN ('reserved','submitted','running')"),
    )
    op.add_column(
        "lyric_classification_snapshots", sa.Column("provider_model_version", sa.String(200))
    )
    op.add_column(
        "lyric_classification_snapshots",
        sa.Column("execution_mode", sa.String(16), nullable=False, server_default="online"),
    )
    op.add_column(
        "lyric_classification_snapshots", sa.Column("batch_run_id", sa.Uuid(), nullable=True)
    )
    op.add_column(
        "lyric_classification_snapshots", sa.Column("batch_item_key", sa.Uuid(), nullable=True)
    )
    op.create_foreign_key(
        "fk_lyric_snapshot_batch_run",
        "lyric_classification_snapshots",
        "lyric_classification_batch_runs",
        ["batch_run_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_lyric_snapshot_batch_item",
        "lyric_classification_snapshots",
        "lyric_classification_batch_items",
        ["batch_item_key"],
        ["opaque_key"],
    )
    op.create_index(
        "ix_lyric_classification_snapshots_batch_run_id",
        "lyric_classification_snapshots",
        ["batch_run_id"],
    )
    op.create_index(
        "ix_lyric_classification_snapshots_batch_item_key",
        "lyric_classification_snapshots",
        ["batch_item_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_lyric_classification_snapshots_batch_item_key",
        table_name="lyric_classification_snapshots",
    )
    op.drop_index(
        "ix_lyric_classification_snapshots_batch_run_id",
        table_name="lyric_classification_snapshots",
    )
    op.drop_constraint(
        "fk_lyric_snapshot_batch_item", "lyric_classification_snapshots", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_lyric_snapshot_batch_run", "lyric_classification_snapshots", type_="foreignkey"
    )
    for column in ("batch_item_key", "batch_run_id", "execution_mode", "provider_model_version"):
        op.drop_column("lyric_classification_snapshots", column)
    op.drop_index(
        "uq_lyric_batch_items_active_signature", table_name="lyric_classification_batch_items"
    )
    for name in (
        "ix_lyric_batch_items_state",
        "ix_lyric_batch_items_track",
        "ix_lyric_batch_items_document",
        "ix_lyric_batch_items_run",
    ):
        op.drop_index(name, table_name="lyric_classification_batch_items")
    op.drop_table("lyric_classification_batch_items")
    op.drop_index("ix_lyric_batch_runs_state", table_name="lyric_classification_batch_runs")
    op.drop_index("ix_lyric_batch_runs_kind", table_name="lyric_classification_batch_runs")
    op.drop_table("lyric_classification_batch_runs")
