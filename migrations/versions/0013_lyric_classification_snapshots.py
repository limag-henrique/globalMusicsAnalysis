"""Add immutable automatic lyric classification snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "0013_lyric_classification_snapshots"
down_revision = "0012_track_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dialect_name = op.get_bind().dialect.name
    append_order_column = (
        sa.Column("append_order", sa.BigInteger(), sa.Identity(always=True), nullable=False)
        if dialect_name == "postgresql"
        else sa.Column("append_order", sa.BigInteger(), nullable=False, server_default="0")
    )
    op.create_table(
        "lyric_classification_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        append_order_column,
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
        sa.Column("classification_status", sa.String(40), nullable=False),
        sa.Column("confidence", sa.Float()),
        sa.Column("result_json", sa.JSON()),
        sa.Column("error", sa.Text()),
        sa.Column("classified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("thought_tokens", sa.Integer()),
        sa.Column("total_tokens", sa.Integer()),
        sa.Column("estimated_cost_usd", sa.Numeric(20, 10)),
        sa.Column(
            "forced_from_snapshot_id",
            sa.Uuid(),
            sa.ForeignKey("lyric_classification_snapshots.id"),
        ),
    )
    op.create_index(
        "ix_lyric_classification_snapshots_signature",
        "lyric_classification_snapshots",
        ["canonical_track_id", "lyrics_hash", "model_id", "taxonomy_version", "prompt_version"],
    )
    op.create_index(
        "ix_lyric_classification_snapshots_classification_status",
        "lyric_classification_snapshots",
        ["classification_status"],
    )
    if dialect_name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION prevent_lyric_classification_snapshot_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'lyric classification snapshots are immutable';
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            """
            CREATE TRIGGER lyric_classification_snapshots_immutable
            BEFORE UPDATE OR DELETE ON lyric_classification_snapshots
            FOR EACH ROW EXECUTE FUNCTION prevent_lyric_classification_snapshot_mutation();
            """
        )
    elif dialect_name == "sqlite":
        op.execute(
            """
            CREATE TRIGGER lyric_classification_snapshots_append_order
            AFTER INSERT ON lyric_classification_snapshots
            BEGIN
                UPDATE lyric_classification_snapshots
                SET append_order = (
                    SELECT COALESCE(MAX(append_order), 0) + 1
                    FROM lyric_classification_snapshots
                    WHERE id != NEW.id
                )
                WHERE id = NEW.id;
            END
            """
        )
        op.execute(
            """
            CREATE TRIGGER lyric_classification_snapshots_immutable_update
            BEFORE UPDATE ON lyric_classification_snapshots
            WHEN NOT (OLD.append_order = 0 AND NEW.append_order > 0)
            BEGIN
                SELECT RAISE(ABORT, 'lyric classification snapshots are immutable');
            END
            """
        )
        op.execute(
            """
            CREATE TRIGGER lyric_classification_snapshots_immutable_delete
            BEFORE DELETE ON lyric_classification_snapshots
            BEGIN
                SELECT RAISE(ABORT, 'lyric classification snapshots are immutable');
            END
            """
        )


def downgrade() -> None:
    dialect_name = op.get_bind().dialect.name
    if dialect_name == "postgresql":
        op.execute(
            "DROP TRIGGER IF EXISTS lyric_classification_snapshots_immutable "
            "ON lyric_classification_snapshots"
        )
        op.execute("DROP FUNCTION IF EXISTS prevent_lyric_classification_snapshot_mutation()")
    elif dialect_name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS lyric_classification_snapshots_immutable_delete")
        op.execute("DROP TRIGGER IF EXISTS lyric_classification_snapshots_immutable_update")
        op.execute("DROP TRIGGER IF EXISTS lyric_classification_snapshots_append_order")
    op.drop_index(
        "ix_lyric_classification_snapshots_classification_status",
        table_name="lyric_classification_snapshots",
    )
    op.drop_index(
        "ix_lyric_classification_snapshots_signature",
        table_name="lyric_classification_snapshots",
    )
    op.drop_table("lyric_classification_snapshots")
