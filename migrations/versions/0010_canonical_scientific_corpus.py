"""Add canonical scientific corpus derived tables."""

import sqlalchemy as sa
from alembic import op

revision = "0010_canonical_scientific_corpus"
down_revision = "0009_source_inventory"
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
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.create_table(
        "market_geography",
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("iso3", sa.String(3), nullable=False),
        sa.Column("country_name", sa.String(160), nullable=False),
        sa.Column("m49", sa.String(3), nullable=False),
        sa.Column("region", sa.String(100), nullable=False),
        sa.Column("subregion", sa.String(100), nullable=False),
        sa.Column("intermediate_region", sa.String(100)),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("source_version", sa.String(40), nullable=False),
        *_audit(),
        sa.UniqueConstraint("country_code", "source_version"),
    )
    op.create_table(
        "chart_cell_profiles",
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("platform_code", sa.String(50), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("chart_family", sa.String(100), nullable=False),
        sa.Column("frequency", sa.String(20), nullable=False),
        sa.Column("first_date", sa.Date()),
        sa.Column("last_date", sa.Date()),
        sa.Column("expected_periods", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("observed_periods", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("coverage_ratio", sa.Float(), nullable=False, server_default="0"),
        sa.Column("longest_gap", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("number_of_tracks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("median_chart_depth", sa.Float(), nullable=False, server_default="0"),
        sa.Column("source_quality", sa.Float(), nullable=False, server_default="1"),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *_audit(),
        sa.UniqueConstraint(
            "provider", "platform_code", "country_code", "chart_family", "frequency"
        ),
    )
    op.create_table(
        "canonical_chart_entries",
        sa.Column("origin_platform", sa.String(50), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("chart_family", sa.String(100), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column(
            "canonical_track_id", sa.Uuid(), sa.ForeignKey("canonical_tracks.id"), nullable=False
        ),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("metric_type", sa.String(30), nullable=False),
        sa.Column("metric_value", sa.Numeric(30, 6)),
        sa.Column("selected_provider", sa.String(80), nullable=False),
        sa.Column(
            "selected_chart_entry_id", sa.Uuid(), sa.ForeignKey("chart_entries.id"), nullable=False
        ),
        sa.Column("source_entry_ids", sa.JSON(), nullable=False),
        sa.Column("conflict_status", sa.String(30), nullable=False),
        sa.Column("reconciliation_version", sa.String(40), nullable=False),
        *_audit(),
        sa.UniqueConstraint(
            "origin_platform",
            "country_code",
            "chart_family",
            "period_start",
            "period_end",
            "canonical_track_id",
        ),
    )
    op.create_table(
        "source_conflicts",
        sa.Column(
            "canonical_chart_entry_id",
            sa.Uuid(),
            sa.ForeignKey("canonical_chart_entries.id"),
            nullable=False,
        ),
        sa.Column("conflict_type", sa.String(50), nullable=False),
        sa.Column("source_values", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        *_audit(),
    )
    op.create_table(
        "corpus_versions",
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("version", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("rules", sa.JSON(), nullable=False),
        sa.Column("source_snapshot_ids", sa.JSON(), nullable=False),
        sa.Column("date_start", sa.Date(), nullable=False),
        sa.Column("date_end", sa.Date(), nullable=False),
        sa.Column("manifest_sha256", sa.String(64), nullable=False),
        sa.Column("software_version", sa.String(50), nullable=False),
        sa.Column("git_revision", sa.String(64)),
        sa.Column("dirty", sa.Boolean(), nullable=False),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=False),
        *_audit(),
        sa.UniqueConstraint("name", "version"),
    )
    op.create_table(
        "corpus_memberships",
        sa.Column(
            "corpus_version_id", sa.Uuid(), sa.ForeignKey("corpus_versions.id"), nullable=False
        ),
        sa.Column("member_type", sa.String(30), nullable=False),
        sa.Column("member_key", sa.String(500), nullable=False),
        sa.Column("provider", sa.String(80)),
        sa.Column("platform_code", sa.String(50)),
        sa.Column("country_code", sa.String(2)),
        sa.Column("chart_family", sa.String(100)),
        sa.Column("period_start", sa.Date()),
        sa.Column("period_end", sa.Date()),
        sa.Column("eligible", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(500)),
        *_audit(),
        sa.UniqueConstraint("corpus_version_id", "member_type", "member_key"),
    )
    op.create_table(
        "genre_taxonomy",
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("label", sa.String(160), nullable=False),
        sa.Column("parent_code", sa.String(80)),
        sa.Column("version", sa.String(40), nullable=False),
        *_audit(),
        sa.UniqueConstraint("code", "version"),
    )
    op.create_table(
        "genre_claims",
        sa.Column(
            "canonical_track_id", sa.Uuid(), sa.ForeignKey("canonical_tracks.id"), nullable=False
        ),
        sa.Column("raw_label", sa.String(200), nullable=False),
        sa.Column("normalized_genre", sa.String(80), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("source_version", sa.String(40), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("review_status", sa.String(30), nullable=False),
        *_audit(),
    )
    op.create_table(
        "track_languages",
        sa.Column(
            "canonical_track_id", sa.Uuid(), sa.ForeignKey("canonical_tracks.id"), nullable=False
        ),
        sa.Column("language_code", sa.String(16), nullable=False),
        sa.Column("raw_value", sa.String(100)),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("source_version", sa.String(40), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("is_multilingual", sa.Boolean(), nullable=False),
        *_audit(),
        sa.UniqueConstraint("canonical_track_id", "language_code", "source"),
    )
    op.create_table(
        "lyric_documents",
        sa.Column(
            "canonical_track_id", sa.Uuid(), sa.ForeignKey("canonical_tracks.id"), nullable=False
        ),
        sa.Column("language_code", sa.String(16)),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("source_version", sa.String(40), nullable=False),
        sa.Column("rights_status", sa.String(40), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("text", sa.Text()),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *_audit(),
        sa.UniqueConstraint("canonical_track_id", "source", "content_sha256"),
    )
    op.create_table(
        "semantic_annotations",
        sa.Column(
            "lyric_document_id", sa.Uuid(), sa.ForeignKey("lyric_documents.id"), nullable=False
        ),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float()),
        sa.Column("method", sa.String(100), nullable=False),
        sa.Column("model_version", sa.String(80), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("review_status", sa.String(30), nullable=False),
        *_audit(),
        sa.UniqueConstraint("lyric_document_id", "category", "model_version"),
    )


def downgrade() -> None:
    for name in (
        "semantic_annotations",
        "lyric_documents",
        "track_languages",
        "genre_claims",
        "genre_taxonomy",
        "corpus_memberships",
        "corpus_versions",
        "source_conflicts",
        "canonical_chart_entries",
        "chart_cell_profiles",
        "market_geography",
    ):
        op.drop_table(name)
