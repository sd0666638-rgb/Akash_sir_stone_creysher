from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, Enum as SAEnum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import InvoicePaymentStatus, PaymentRecordStatus


class BuyerOrderSequence(Base):
    __tablename__ = "buyer_order_sequences"
    __table_args__ = (
        CheckConstraint(
            "last_number >= 0",
            name="ck_buyer_order_sequences_last_number_nonnegative",
        ),
    )

    sequence_date: Mapped[date] = mapped_column(Date, primary_key=True)
    last_number: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )


class Invoice(TimestampMixin, Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date)
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    delivery_note: Mapped[str | None] = mapped_column(String(120))
    other_reference: Mapped[str | None] = mapped_column(String(160))
    buyer_order_number: Mapped[str | None] = mapped_column(String(120))
    vehicle_number: Mapped[str | None] = mapped_column(String(40))
    driver_name: Mapped[str | None] = mapped_column(String(120))
    transporter: Mapped[str | None] = mapped_column(String(160))
    delivery_location: Mapped[str | None] = mapped_column(String(255))
    payment_type: Mapped[str | None] = mapped_column(String(40))
    credit_period_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    taxable_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    cgst_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    sgst_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    igst_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    transport_charges: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    loading_charges: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    other_charges: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    round_off: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    grand_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    total_paid: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    advance_adjusted: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    remaining_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    payment_status: Mapped[InvoicePaymentStatus] = mapped_column(
        SAEnum(InvoicePaymentStatus), default=InvoicePaymentStatus.UNPAID, nullable=False
    )
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    customer: Mapped["Customer"] = relationship(back_populates="invoices", lazy="selectin")
    items: Mapped[list["InvoiceItem"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", lazy="selectin"
    )
    allocations: Mapped[list["PaymentAllocation"]] = relationship(
        back_populates="invoice", lazy="selectin"
    )
    advance_adjustments: Mapped[list["AdvanceAdjustment"]] = relationship(
        back_populates="invoice", lazy="selectin"
    )

    @property
    def pending_payment_amount(self) -> Decimal:
        return sum(
            (
                allocation.allocated_amount
                for allocation in self.allocations
                if allocation.payment.payment_status == PaymentRecordStatus.PENDING
            ),
            Decimal("0"),
        )

    @property
    def available_payment_amount(self) -> Decimal:
        if self.payment_status == InvoicePaymentStatus.CANCELLED:
            return Decimal("0")
        return max(
            Decimal(self.remaining_amount or 0) - self.pending_payment_amount,
            Decimal("0"),
        )


class InvoiceItem(TimestampMixin, Base):
    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False)
    material_id: Mapped[int | None] = mapped_column(ForeignKey("materials.id"), nullable=True)
    material_name: Mapped[str] = mapped_column(String(160), nullable=False)
    dispatch_date: Mapped[date | None] = mapped_column(Date)
    receipt_number: Mapped[str | None] = mapped_column(String(80))
    hsn_code: Mapped[str | None] = mapped_column(String(20))
    vehicle_number: Mapped[str | None] = mapped_column(String(40))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(30), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    gst_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    discount_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    line_subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    taxable_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    gst_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)

    invoice: Mapped[Invoice] = relationship(back_populates="items", lazy="selectin")
    material: Mapped["Material | None"] = relationship(lazy="selectin")
