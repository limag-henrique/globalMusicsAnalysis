"""Create retained collection attempts and append-only coverage cells."""

import sqlalchemy as sa
from alembic import op

revision = "0007_collection_coverage"
down_revision = "0006_provenance"
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
        "collection_runs",
        sa.Column(
            "chart_definition_id", sa.Uuid(), sa.ForeignKey("chart_definitions.id"), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("error_code", sa.String(100)),
        sa.Column("parameters", sa.JSON(), nullable=False),
        *_audit(),
    )
    op.create_index(
        "ix_collection_runs_chart_definition_id", "collection_runs", ["chart_definition_id"]
    )
    op.create_table(
        "coverage_cells",
        sa.Column(
            "chart_definition_id", sa.Uuid(), sa.ForeignKey("chart_definitions.id"), nullable=False
        ),
        sa.Column("collection_run_id", sa.Uuid(), sa.ForeignKey("collection_runs.id")),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("reason", sa.String(500)),
        *_audit(),
    )
    op.create_index(
        "ix_coverage_cells_chart_definition_id", "coverage_cells", ["chart_definition_id"]
    )


def downgrade() -> None:
    op.drop_table("coverage_cells")
    op.drop_table("collection_runs")
