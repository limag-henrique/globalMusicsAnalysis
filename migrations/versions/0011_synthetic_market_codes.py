"""Allow synthetic market codes such as GLOBAL."""

from alembic import op
import sqlalchemy as sa


revision = "0011_synthetic_market_codes"
down_revision = "0010_canonical_scientific_corpus"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table, column in (
        ("chart_definitions", "country_code"),
        ("chart_cell_profiles", "country_code"),
        ("canonical_chart_entries", "country_code"),
        ("corpus_memberships", "country_code"),
    ):
        op.alter_column(
            table,
            column,
            existing_type=sa.String(2),
            type_=sa.String(20),
            existing_nullable=table != "corpus_memberships",
        )


def downgrade() -> None:
    for table, column in (
        ("chart_definitions", "country_code"),
        ("chart_cell_profiles", "country_code"),
        ("canonical_chart_entries", "country_code"),
        ("corpus_memberships", "country_code"),
    ):
        op.alter_column(
            table,
            column,
            existing_type=sa.String(20),
            type_=sa.String(2),
            existing_nullable=table != "corpus_memberships",
        )
