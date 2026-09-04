"""Create effective-dated rights profiles and grants."""

import sqlalchemy as sa
from alembic import op

revision = "0002_rights_profiles"
down_revision = "0001_reference_entities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rights_profiles",
        sa.Column("source_id", sa.Uuid(), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True)),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_rights_profiles_source_id", "rights_profiles", ["source_id"])
    op.create_table(
        "rights_grants",
        sa.Column("profile_id", sa.Uuid(), sa.ForeignKey("rights_profiles.id"), nullable=False),
        sa.Column("operation", sa.String(40), nullable=False),
        sa.Column("allowed", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("profile_id", "operation"),
    )
    op.create_index("ix_rights_grants_profile_id", "rights_grants", ["profile_id"])


def downgrade() -> None:
    op.drop_table("rights_grants")
    op.drop_table("rights_profiles")
