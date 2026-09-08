"""Persist source manifests, capabilities, and native-period coverage."""

import sqlalchemy as sa
from alembic import op

revision = "0009_source_inventory"
down_revision = "0008_analysis_exports"
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
        "source_inventories",
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("origin_platform", sa.String(50), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("artifact_path", sa.String(1000), nullable=False),
        sa.Column("sha256", sa.String(64), unique=True, nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(80), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("countries", sa.JSON(), nullable=False),
        sa.Column("chart_types", sa.JSON(), nullable=False),
        sa.Column("earliest_date", sa.Date()),
        sa.Column("latest_date", sa.Date()),
        sa.Column("number_of_tracks", sa.Integer()),
        sa.Column("number_of_observations", sa.Integer()),
        sa.Column("missing_periods", sa.Integer()),
        sa.Column("parser_version", sa.String(80), nullable=False),
        *_audit(),
    )
    for column in ("provider", "origin_platform", "status", "sha256"):
        op.create_index(f"ix_source_inventories_{column}", "source_inventories", [column])

    op.create_table(
        "source_capabilities",
        sa.Column(
            "source_inventory_id",
            sa.Uuid(),
            sa.ForeignKey("source_inventories.id"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("origin_platform", sa.String(50), nullable=False),
        sa.Column("country_code", sa.String(20), nullable=False),
        sa.Column("country_name", sa.String(160)),
        sa.Column("territory_type", sa.String(30), nullable=False),
        sa.Column("available", sa.Boolean(), nullable=False),
        sa.Column("earliest_date", sa.Date()),
        sa.Column("latest_date", sa.Date()),
        sa.Column("chart_types", sa.JSON(), nullable=False),
        sa.Column("native_frequency", sa.String(20)),
        sa.Column("ranking_depth", sa.Integer()),
        sa.Column("number_of_tracks", sa.Integer()),
        sa.Column("number_of_observations", sa.Integer()),
        sa.Column("coverage_ratio", sa.Float()),
        *_audit(),
        sa.UniqueConstraint(
            "source_inventory_id", "provider", "origin_platform", "country_code"
        ),
    )
    for column in ("source_inventory_id", "provider", "origin_platform", "country_code"):
        op.create_index(f"ix_source_capabilities_{column}", "source_capabilities", [column])

    op.create_table(
        "source_coverage",
        sa.Column(
            "source_inventory_id",
            sa.Uuid(),
            sa.ForeignKey("source_inventories.id"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("origin_platform", sa.String(50), nullable=False),
        sa.Column("country_code", sa.String(20), nullable=False),
        sa.Column("chart_name", sa.String(200), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("reason", sa.String(500)),
        sa.Column("native_frequency", sa.String(20)),
        sa.Column("ranking_depth", sa.Integer()),
        *_audit(),
        sa.UniqueConstraint(
            "source_inventory_id",
            "provider",
            "origin_platform",
            "country_code",
            "chart_name",
            "period_start",
            "period_end",
        ),
    )
    for column in ("source_inventory_id", "provider", "origin_platform", "country_code", "status"):
        op.create_index(f"ix_source_coverage_{column}", "source_coverage", [column])


def downgrade() -> None:
    op.drop_table("source_coverage")
    op.drop_table("source_capabilities")
    op.drop_table("source_inventories")
