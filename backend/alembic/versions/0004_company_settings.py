"""Add persistent singleton company settings

Revision ID: 0004_company_settings
Revises: 0003_customer_identifiers
Create Date: 2026-07-27
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_company_settings"
down_revision = "0003_customer_identifiers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_settings",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("company_name", sa.String(length=180), nullable=False),
        sa.Column("company_address", sa.Text(), nullable=False),
        sa.Column("company_phone", sa.String(length=30), nullable=True),
        sa.Column("company_gstin", sa.String(length=15), nullable=True),
        sa.Column("company_state", sa.String(length=100), nullable=True),
        sa.Column("company_gst_state_code", sa.String(length=2), nullable=True),
        sa.Column("company_jurisdiction", sa.String(length=100), nullable=True),
        sa.Column("company_bank_name", sa.String(length=160), nullable=True),
        sa.Column("company_bank_account", sa.String(length=80), nullable=True),
        sa.Column("company_bank_ifsc", sa.String(length=20), nullable=True),
        sa.Column("company_bank_branch", sa.String(length=160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_company_settings_singleton_id"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("company_settings")
