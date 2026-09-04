"""Create reproducible analysis run records."""

import sqlalchemy as sa
from alembic import op

revision = "0008_analysis_exports"
down_revision = "0007_collection_coverage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analysis_runs",
        sa.Column("dataset_name", sa.String(100), nullable=False),
        sa.Column("schema_version", sa.String(30), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("input_snapshot_ids", sa.JSON(), nullable=False),
        sa.Column("output_sha256", sa.String(64), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("date_start", sa.Date(), nullable=False),
        sa.Column("date_end", sa.Date(), nullable=False),
        sa.Column("software_version", sa.String(50), nullable=False),
        sa.Column("git_revision", sa.String(64)),
        sa.Column("dirty", sa.Boolean(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("analysis_runs")
