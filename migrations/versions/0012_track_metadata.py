"""Store artist and recording metadata on platform items."""

import sqlalchemy as sa
from alembic import op

revision = "0012_track_metadata"
down_revision = "0011_synthetic_market_codes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("canonical_tracks", sa.Column("duration_ms", sa.Integer()))
    op.add_column("canonical_tracks", sa.Column("release_date", sa.Date()))
    op.add_column("platform_items", sa.Column("artist", sa.String(1000)))
    op.add_column("platform_items", sa.Column("duration_ms", sa.Integer()))
    op.add_column("platform_items", sa.Column("release_date", sa.Date()))


def downgrade() -> None:
    op.drop_column("platform_items", "release_date")
    op.drop_column("platform_items", "duration_ms")
    op.drop_column("platform_items", "artist")
    op.drop_column("canonical_tracks", "release_date")
    op.drop_column("canonical_tracks", "duration_ms")
