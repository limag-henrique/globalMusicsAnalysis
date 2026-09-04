"""Create immutable charts, snapshots, and entries."""

import sqlalchemy as sa
from alembic import op

revision = "0005_charts"
down_revision = "0004_resolution_records"
branch_labels = None
depends_on = None


def _audit() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "chart_definitions",
        sa.Column("platform_code", sa.String(50), nullable=False),
        sa.Column("source_code", sa.String(80), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("chart_name", sa.String(200), nullable=False),
        sa.Column("native_frequency", sa.String(20), nullable=False),
        sa.Column("nominal_depth", sa.Integer()),
        sa.Column("methodology_version", sa.String(50), nullable=False),
        *_audit(),
        sa.UniqueConstraint("platform_code", "source_code", "country_code", "chart_name"),
    )
    op.create_table(
        "chart_snapshots",
        sa.Column(
            "chart_definition_id", sa.Uuid(), sa.ForeignKey("chart_definitions.id"), nullable=False
        ),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_start", sa.Date()),
        sa.Column("effective_end", sa.Date()),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("schema_version", sa.String(50), nullable=False),
        sa.Column("collector_version", sa.String(50), nullable=False),
        sa.Column("entry_count", sa.Integer(), nullable=False),
        sa.Column("supersedes_snapshot_id", sa.Uuid(), sa.ForeignKey("chart_snapshots.id")),
        sa.Column("provider_metadata", sa.JSON(), nullable=False),
        *_audit(),
    )
    op.create_index(
        "ix_chart_snapshots_chart_definition_id", "chart_snapshots", ["chart_definition_id"]
    )
    op.create_index("ix_chart_snapshots_checksum", "chart_snapshots", ["checksum"])
    op.create_table(
        "chart_entries",
        sa.Column("snapshot_id", sa.Uuid(), sa.ForeignKey("chart_snapshots.id"), nullable=False),
        sa.Column(
            "platform_item_id", sa.Uuid(), sa.ForeignKey("platform_items.id"), nullable=False
        ),
        sa.Column("canonical_track_id", sa.Uuid(), sa.ForeignKey("canonical_tracks.id")),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("metric_type", sa.String(20), nullable=False),
        sa.Column("metric_value", sa.Numeric(30, 6)),
        sa.Column("raw_fields", sa.JSON(), nullable=False),
        *_audit(),
        sa.UniqueConstraint("snapshot_id", "position"),
    )
    for column in ["snapshot_id", "platform_item_id", "canonical_track_id"]:
        op.create_index(f"ix_chart_entries_{column}", "chart_entries", [column])
    op.execute(
        "CREATE FUNCTION reject_immutable_chart_change() RETURNS trigger AS $$ "
        "BEGIN RAISE EXCEPTION 'immutable chart record'; END; $$ LANGUAGE plpgsql"
    )
    for table in ("chart_snapshots", "chart_entries"):
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_immutable_chart_change()"
        )


def downgrade() -> None:
    for table in ("chart_snapshots", "chart_entries"):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_immutable ON {table}")
    op.execute("DROP FUNCTION IF EXISTS reject_immutable_chart_change()")
    op.drop_table("chart_entries")
    op.drop_table("chart_snapshots")
    op.drop_table("chart_definitions")
