"""Add unique normalized customer mobiles and buyer order sequences

Revision ID: 0003_customer_identifiers
Revises: 0002_bill_dispatch_fields
Create Date: 2026-07-27
"""

from datetime import datetime
import re

from alembic import op
import sqlalchemy as sa


revision = "0003_customer_identifiers"
down_revision = "0002_bill_dispatch_fields"
branch_labels = None
depends_on = None


_MOBILE_INPUT = re.compile(r"^[+\d\s()-]+$")
_BUYER_ORDER = re.compile(r"^([1-9]\d*)-(\d{8})$")


def _normalize_legacy_mobile(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    # Preserve malformed legacy values for later user correction rather than
    # discarding data during the uniqueness migration.
    if not _MOBILE_INPUT.fullmatch(text):
        return text
    digits = re.sub(r"\D", "", text)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits if len(digits) == 10 else text


def upgrade() -> None:
    op.create_table(
        "buyer_order_sequences",
        sa.Column("sequence_date", sa.Date(), nullable=False),
        sa.Column(
            "last_number",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.CheckConstraint(
            "last_number >= 0",
            name="ck_buyer_order_sequences_last_number_nonnegative",
        ),
        sa.PrimaryKeyConstraint("sequence_date"),
    )

    bind = op.get_bind()
    customers = sa.table(
        "customers",
        sa.column("id", sa.Integer()),
        sa.column("mobile_number", sa.String(length=30)),
    )
    seen_mobiles: set[str] = set()
    customer_rows = bind.execute(
        sa.select(customers.c.id, customers.c.mobile_number).order_by(customers.c.id)
    ).all()
    for customer_id, current_mobile in customer_rows:
        normalized = _normalize_legacy_mobile(current_mobile)
        if normalized in seen_mobiles:
            normalized = None
        if normalized is not None:
            seen_mobiles.add(normalized)
        if normalized != current_mobile:
            bind.execute(
                customers.update()
                .where(customers.c.id == customer_id)
                .values(mobile_number=normalized)
            )

    op.create_unique_constraint(
        "uq_customers_mobile_number",
        "customers",
        ["mobile_number"],
    )

    invoices = sa.table(
        "invoices",
        sa.column("invoice_date", sa.Date()),
        sa.column("buyer_order_number", sa.String(length=120)),
    )
    daily_maximums: dict[object, int] = {}
    invoice_rows = bind.execute(
        sa.select(invoices.c.invoice_date, invoices.c.buyer_order_number)
        .where(invoices.c.buyer_order_number.is_not(None))
    ).all()
    for invoice_date, buyer_order_number in invoice_rows:
        match = _BUYER_ORDER.fullmatch((buyer_order_number or "").strip())
        if match is None:
            continue
        sequence_number = int(match.group(1))
        try:
            encoded_date = datetime.strptime(match.group(2), "%d%m%Y").date()
        except ValueError:
            continue
        if encoded_date != invoice_date:
            continue
        daily_maximums[invoice_date] = max(
            daily_maximums.get(invoice_date, 0),
            sequence_number,
        )

    sequences = sa.table(
        "buyer_order_sequences",
        sa.column("sequence_date", sa.Date()),
        sa.column("last_number", sa.Integer()),
    )
    if daily_maximums:
        bind.execute(
            sequences.insert(),
            [
                {
                    "sequence_date": sequence_date,
                    "last_number": last_number,
                }
                for sequence_date, last_number in sorted(daily_maximums.items())
            ],
        )


def downgrade() -> None:
    op.drop_constraint(
        "uq_customers_mobile_number",
        "customers",
        type_="unique",
    )
    op.drop_table("buyer_order_sequences")
