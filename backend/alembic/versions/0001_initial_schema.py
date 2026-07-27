"""Initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-07-13
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False, unique=True, index=True),
        sa.Column("description", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(80), nullable=False, unique=True, index=True),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(180), nullable=False, index=True),
        sa.Column("mobile_number", sa.String(30), index=True),
        sa.Column("gst_number", sa.String(30), index=True),
        sa.Column("billing_address", sa.Text()),
        sa.Column("delivery_address", sa.Text()),
        sa.Column("city", sa.String(100)),
        sa.Column("state", sa.String(100)),
        sa.Column("opening_balance", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("credit_limit", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("credit_period_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_outstanding_balance", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("advance_balance", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "materials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False, unique=True, index=True),
        sa.Column("unit", sa.String(30), nullable=False, server_default="TON"),
        sa.Column("selling_rate", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("purchase_rate", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("gst_percentage", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("stock_quantity", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("minimum_stock", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "stock_movements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("movement_type", sa.Enum("IN", "OUT", "ADJUSTMENT", name="stockmovementtype"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("reference_number", sa.String(80)),
        sa.Column("movement_date", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("invoice_number", sa.String(40), nullable=False, unique=True, index=True),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date()),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("vehicle_number", sa.String(40)),
        sa.Column("driver_name", sa.String(120)),
        sa.Column("transporter", sa.String(160)),
        sa.Column("delivery_location", sa.String(255)),
        sa.Column("payment_type", sa.String(40)),
        sa.Column("credit_period_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text()),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("discount_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("taxable_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("cgst_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("sgst_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("igst_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("transport_charges", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("loading_charges", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("other_charges", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("round_off", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("grand_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_paid", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("advance_adjusted", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("remaining_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column(
            "payment_status",
            sa.Enum("UNPAID", "PARTIALLY_PAID", "FULLY_PAID", "OVERPAID", "CANCELLED", name="invoicepaymentstatus"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "invoice_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id")),
        sa.Column("material_name", sa.String(160), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit", sa.String(30), nullable=False),
        sa.Column("rate", sa.Numeric(14, 2), nullable=False),
        sa.Column("gst_percentage", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("discount_percentage", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("line_subtotal", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("discount_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("taxable_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("gst_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "payments",
        sa.Column("payment_id", sa.Integer(), primary_key=True),
        sa.Column("receipt_number", sa.String(40), nullable=False, unique=True, index=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "payment_method",
            sa.Enum("CASH", "UPI", "CARD", "BANK_TRANSFER", "CHEQUE", "RTGS", "NEFT", "CUSTOMER_ADVANCE", "ADJUSTMENT", "OTHER", name="paymentmethod"),
            nullable=False,
        ),
        sa.Column("transaction_reference", sa.String(120), index=True),
        sa.Column("bank_name", sa.String(120)),
        sa.Column("cheque_number", sa.String(80), index=True),
        sa.Column("cheque_date", sa.Date()),
        sa.Column(
            "cheque_status",
            sa.Enum("RECEIVED", "DEPOSITED", "CLEARED", "BOUNCED", "CANCELLED", name="chequestatus"),
        ),
        sa.Column("notes", sa.Text()),
        sa.Column(
            "payment_status",
            sa.Enum("SUCCESSFUL", "PENDING", "REVERSED", "CANCELLED", "BOUNCED", name="paymentrecordstatus"),
            nullable=False,
        ),
        sa.Column("unallocated_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "payment_allocations",
        sa.Column("allocation_id", sa.Integer(), primary_key=True),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.payment_id"), nullable=False),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("allocated_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("allocation_date", sa.Date(), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "customer_advances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.payment_id")),
        sa.Column("advance_date", sa.Date(), nullable=False),
        sa.Column("total_received", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_adjusted", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("remaining_balance", sa.Numeric(14, 2), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "advance_adjustments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("advance_id", sa.Integer(), sa.ForeignKey("customer_advances.id"), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("adjustment_date", sa.Date(), nullable=False),
        sa.Column("adjusted_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "customer_ledger",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False, index=True),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column(
            "transaction_type",
            sa.Enum("INVOICE", "PAYMENT", "ADVANCE_PAYMENT", "ADVANCE_ADJUSTMENT", "PAYMENT_REVERSAL", "OPENING_BALANCE", "DEBIT_NOTE", "CREDIT_NOTE", "DISCOUNT_ADJUSTMENT", "ADDITIONAL_CHARGE", name="ledgertransactiontype"),
            nullable=False,
        ),
        sa.Column("reference_number", sa.String(80), nullable=False),
        sa.Column("description", sa.String(255)),
        sa.Column("debit", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("credit", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("running_balance", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("payment_status", sa.String(40)),
        sa.Column("due_date", sa.Date()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "cheque_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.payment_id"), nullable=False, unique=True),
        sa.Column("cheque_number", sa.String(80), nullable=False, index=True),
        sa.Column("cheque_date", sa.Date()),
        sa.Column("bank_name", sa.String(120)),
        sa.Column("cheque_status", sa.Enum("RECEIVED", "DEPOSITED", "CLEARED", "BOUNCED", "CANCELLED", name="chequestatus"), nullable=False),
        sa.Column("bounce_charges", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "payment_reversals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.payment_id"), nullable=False),
        sa.Column("reversal_date", sa.Date(), nullable=False),
        sa.Column("reversal_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "receipts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("receipt_number", sa.String(40), nullable=False, unique=True, index=True),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.payment_id"), nullable=False, unique=True),
        sa.Column("receipt_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("amount_in_words", sa.String(255)),
        sa.Column("received_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("module", sa.String(80), nullable=False),
        sa.Column("record_id", sa.String(80), nullable=False),
        sa.Column("previous_value", sa.JSON()),
        sa.Column("new_value", sa.JSON()),
        sa.Column("ip_address", sa.String(64)),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "user_activity",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("ip_address", sa.String(64)),
        sa.Column("user_agent", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("user_activity")
    op.drop_table("audit_logs")
    op.drop_table("receipts")
    op.drop_table("payment_reversals")
    op.drop_table("cheque_payments")
    op.drop_table("customer_ledger")
    op.drop_table("advance_adjustments")
    op.drop_table("customer_advances")
    op.drop_table("payment_allocations")
    op.drop_table("payments")
    op.drop_table("invoice_items")
    op.drop_table("invoices")
    op.drop_table("stock_movements")
    op.drop_table("materials")
    op.drop_table("customers")
    op.drop_table("user_roles")
    op.drop_table("users")
    op.drop_table("roles")
