"""Add queue indexes for incremental lyric classification."""

import sqlalchemy as sa
from alembic import op

revision = "0014_lyric_classification_queue"
down_revision = "0013_lyrics_classification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dialect_name = op.get_bind().dialect.name
    if dialect_name == "postgresql":
        op.create_index(
            "ix_lyric_documents_authorized_queue",
            "lyric_documents",
            ["created_at", "id", "canonical_track_id"],
            postgresql_where=sa.text(
                "rights_status IN "
                "('LICENSED','RESEARCH_AUTHORIZED','PUBLIC_DOMAIN','AUTHORIZED')"
            ),
        )
    else:
        op.create_index(
            "ix_lyric_documents_authorized_queue",
            "lyric_documents",
            ["created_at", "id", "canonical_track_id"],
        )
    op.create_index(
        "ix_lyric_classification_snapshots_track_status",
        "lyric_classification_snapshots",
        ["canonical_track_id", "classification_status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_lyric_classification_snapshots_track_status",
        table_name="lyric_classification_snapshots",
    )
    op.drop_index("ix_lyric_documents_authorized_queue", table_name="lyric_documents")
