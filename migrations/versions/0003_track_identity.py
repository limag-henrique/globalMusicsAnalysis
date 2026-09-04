"""Create recording identity tables."""

import sqlalchemy as sa
from alembic import op

revision = "0003_track_identity"
down_revision = "0002_rights_profiles"
branch_labels = None
depends_on = None


def _audit_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table("artists", sa.Column("name", sa.String(500), nullable=False), *_audit_columns())
    op.create_table(
        "canonical_tracks", sa.Column("title", sa.String(1000), nullable=False), *_audit_columns()
    )
    op.create_table(
        "track_artists",
        sa.Column("track_id", sa.Uuid(), sa.ForeignKey("canonical_tracks.id"), primary_key=True),
        sa.Column("artist_id", sa.Uuid(), sa.ForeignKey("artists.id"), primary_key=True),
    )
    op.create_table(
        "platform_items",
        sa.Column("platform_code", sa.String(50), nullable=False),
        sa.Column("native_id", sa.String(500), nullable=False),
        sa.Column("item_kind", sa.String(40), nullable=False),
        sa.Column("title", sa.String(1000)),
        *_audit_columns(),
        sa.UniqueConstraint("platform_code", "native_id"),
    )
    op.create_table(
        "external_id_claims",
        sa.Column("namespace", sa.String(50), nullable=False),
        sa.Column("raw_value", sa.String(500), nullable=False),
        sa.Column("normalized_value", sa.String(500), nullable=False),
        sa.Column("source_code", sa.String(80), nullable=False),
        sa.Column("canonical_track_id", sa.Uuid(), sa.ForeignKey("canonical_tracks.id")),
        sa.Column("platform_item_id", sa.Uuid(), sa.ForeignKey("platform_items.id")),
        *_audit_columns(),
    )
    op.create_index("ix_external_id_claims_namespace", "external_id_claims", ["namespace"])
    op.create_index(
        "ix_external_id_claims_normalized_value", "external_id_claims", ["normalized_value"]
    )
    op.create_table(
        "platform_item_track_links",
        sa.Column(
            "canonical_track_id", sa.Uuid(), sa.ForeignKey("canonical_tracks.id"), nullable=False
        ),
        sa.Column(
            "platform_item_id", sa.Uuid(), sa.ForeignKey("platform_items.id"), nullable=False
        ),
        sa.Column("evidence", sa.String(100), nullable=False),
        *_audit_columns(),
        sa.UniqueConstraint("canonical_track_id", "platform_item_id"),
    )


def downgrade() -> None:
    for table in [
        "platform_item_track_links",
        "external_id_claims",
        "platform_items",
        "track_artists",
        "canonical_tracks",
        "artists",
    ]:
        op.drop_table(table)
