"""Create auditable resolution records."""

import sqlalchemy as sa
from alembic import op

revision = "0004_resolution_records"
down_revision = "0003_track_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "resolution_records",
        sa.Column(
            "platform_item_id", sa.Uuid(), sa.ForeignKey("platform_items.id"), nullable=False
        ),
        sa.Column("canonical_track_id", sa.Uuid(), sa.ForeignKey("canonical_tracks.id")),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("rule_version", sa.String(40), nullable=False),
        sa.Column("evidence", sa.String(80), nullable=False),
        sa.Column("score", sa.Float()),
        sa.Column("candidates", sa.JSON(), nullable=False),
        sa.Column("reviewer", sa.String(200)),
        sa.Column("reviewer_decision", sa.String(40)),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_resolution_records_platform_item_id", "resolution_records", ["platform_item_id"]
    )


def downgrade() -> None:
    op.drop_table("resolution_records")
