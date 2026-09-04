"""Create immutable artifact provenance and audit events."""

import sqlalchemy as sa
from alembic import op

revision = "0006_provenance"
down_revision = "0005_charts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    audit = [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]
    op.create_table(
        "source_artifacts",
        sa.Column("sha256", sa.String(64), unique=True, nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("media_type", sa.String(200), nullable=False),
        sa.Column("source_id", sa.Uuid(), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column(
            "rights_profile_id", sa.Uuid(), sa.ForeignKey("rights_profiles.id"), nullable=False
        ),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("collector_version", sa.String(50), nullable=False),
        sa.Column("schema_version", sa.String(50), nullable=False),
        sa.Column("acquisition_parameters", sa.JSON(), nullable=False),
        *audit,
    )
    op.create_index("ix_source_artifacts_source_id", "source_artifacts", ["source_id"])
    op.create_table(
        "audit_events",
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("actor", sa.String(200), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        *[
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        ],
    )
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])
    op.execute(
        "CREATE FUNCTION reject_provenance_change() RETURNS trigger AS $$ "
        "BEGIN RAISE EXCEPTION 'immutable provenance record'; END; $$ LANGUAGE plpgsql"
    )
    for table in ("source_artifacts", "audit_events"):
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_provenance_change()"
        )


def downgrade() -> None:
    for table in ("source_artifacts", "audit_events"):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_immutable ON {table}")
    op.execute("DROP FUNCTION IF EXISTS reject_provenance_change()")
    op.drop_table("audit_events")
    op.drop_table("source_artifacts")
