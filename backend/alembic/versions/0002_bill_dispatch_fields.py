"""Add bill header and dispatch snapshot fields

Revision ID: 0002_bill_dispatch_fields
Revises: 0001_initial_schema
Create Date: 2026-07-25
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_bill_dispatch_fields"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("materials", sa.Column("hsn_code", sa.String(length=20), nullable=True))

    op.add_column("invoices", sa.Column("delivery_note", sa.String(length=120), nullable=True))
    op.add_column("invoices", sa.Column("other_reference", sa.String(length=160), nullable=True))
    op.add_column(
        "invoices", sa.Column("buyer_order_number", sa.String(length=120), nullable=True)
    )
    op.add_column("invoices", sa.Column("period_start", sa.Date(), nullable=True))
    op.add_column("invoices", sa.Column("period_end", sa.Date(), nullable=True))

    op.add_column("invoice_items", sa.Column("dispatch_date", sa.Date(), nullable=True))
    op.add_column(
        "invoice_items", sa.Column("receipt_number", sa.String(length=80), nullable=True)
    )
    op.add_column("invoice_items", sa.Column("hsn_code", sa.String(length=20), nullable=True))
    op.add_column(
        "invoice_items", sa.Column("vehicle_number", sa.String(length=40), nullable=True)
    )

    op.execute(
        sa.text(
            """
            UPDATE materials
            SET hsn_code = :hsn_code
            WHERE hsn_code IS NULL
              AND name IN (
                'Stone Dust',
                'M-Sand',
                '40mm Aggregate',
                '20mm Aggregate',
                '10mm Aggregate',
                'Gitti',
                'Crusher Sand',
                'Metal'
              )
            """
        ).bindparams(hsn_code="25171090")
    )


def downgrade() -> None:
    op.drop_column("invoice_items", "vehicle_number")
    op.drop_column("invoice_items", "hsn_code")
    op.drop_column("invoice_items", "receipt_number")
    op.drop_column("invoice_items", "dispatch_date")

    op.drop_column("invoices", "period_end")
    op.drop_column("invoices", "period_start")
    op.drop_column("invoices", "buyer_order_number")
    op.drop_column("invoices", "other_reference")
    op.drop_column("invoices", "delivery_note")

    op.drop_column("materials", "hsn_code")
