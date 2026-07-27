from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Enum as SAEnum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import ChequeStatus, LedgerTransactionType, PaymentMethod, PaymentRecordStatus


class Payment(TimestampMixin, Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column("payment_id", Integer, primary_key=True)
    receipt_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    payment_method: Mapped[PaymentMethod] = mapped_column(SAEnum(PaymentMethod), nullable=False)
    transaction_reference: Mapped[str | None] = mapped_column(String(120), index=True)
    bank_name: Mapped[str | None] = mapped_column(String(120))
    cheque_number: Mapped[str | None] = mapped_column(String(80), index=True)
    cheque_date: Mapped[date | None] = mapped_column(Date)
    cheque_status: Mapped[ChequeStatus | None] = mapped_column(SAEnum(ChequeStatus))
    notes: Mapped[str | None] = mapped_column(Text)
    payment_status: Mapped[PaymentRecordStatus] = mapped_column(
        SAEnum(PaymentRecordStatus), default=PaymentRecordStatus.SUCCESSFUL, nullable=False
    )
    unallocated_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    customer: Mapped["Customer"] = relationship(back_populates="payments", lazy="selectin")
    allocations: Mapped[list["PaymentAllocation"]] = relationship(
        back_populates="payment", cascade="all, delete-orphan", lazy="selectin"
    )
    receipt: Mapped["Receipt | None"] = relationship(
        back_populates="payment", uselist=False, lazy="selectin"
    )
    cheque_payment: Mapped["ChequePayment | None"] = relationship(
        back_populates="payment", uselist=False, lazy="selectin"
    )


class PaymentAllocation(TimestampMixin, Base):
    __tablename__ = "payment_allocations"

    id: Mapped[int] = mapped_column("allocation_id", Integer, primary_key=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.payment_id"), nullable=False)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False)
    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    allocation_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    payment: Mapped[Payment] = relationship(back_populates="allocations", lazy="selectin")
    invoice: Mapped["Invoice"] = relationship(back_populates="allocations", lazy="selectin")


class CustomerAdvance(TimestampMixin, Base):
    __tablename__ = "customer_advances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    payment_id: Mapped[int | None] = mapped_column(ForeignKey("payments.payment_id"), nullable=True)
    advance_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_received: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total_adjusted: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    remaining_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    customer: Mapped["Customer"] = relationship(lazy="selectin")
    payment: Mapped[Payment | None] = relationship(lazy="selectin")
    adjustments: Mapped[list["AdvanceAdjustment"]] = relationship(
        back_populates="advance", lazy="selectin"
    )


class AdvanceAdjustment(TimestampMixin, Base):
    __tablename__ = "advance_adjustments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    advance_id: Mapped[int] = mapped_column(ForeignKey("customer_advances.id"), nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False)
    adjustment_date: Mapped[date] = mapped_column(Date, nullable=False)
    adjusted_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    advance: Mapped[CustomerAdvance] = relationship(back_populates="adjustments", lazy="selectin")
    invoice: Mapped["Invoice"] = relationship(back_populates="advance_adjustments", lazy="selectin")


class CustomerLedger(TimestampMixin, Base):
    __tablename__ = "customer_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    transaction_type: Mapped[LedgerTransactionType] = mapped_column(
        SAEnum(LedgerTransactionType), nullable=False
    )
    reference_number: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    debit: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    credit: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    running_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    payment_status: Mapped[str | None] = mapped_column(String(40))
    due_date: Mapped[date | None] = mapped_column(Date)

    customer: Mapped["Customer"] = relationship(lazy="selectin")


class ChequePayment(TimestampMixin, Base):
    __tablename__ = "cheque_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payments.payment_id"), nullable=False, unique=True
    )
    cheque_number: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    cheque_date: Mapped[date | None] = mapped_column(Date)
    bank_name: Mapped[str | None] = mapped_column(String(120))
    cheque_status: Mapped[ChequeStatus] = mapped_column(
        SAEnum(ChequeStatus), default=ChequeStatus.RECEIVED, nullable=False
    )
    bounce_charges: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    payment: Mapped[Payment] = relationship(back_populates="cheque_payment", lazy="selectin")


class PaymentReversal(TimestampMixin, Base):
    __tablename__ = "payment_reversals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.payment_id"), nullable=False)
    reversal_date: Mapped[date] = mapped_column(Date, nullable=False)
    reversal_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    payment: Mapped[Payment] = relationship(lazy="selectin")


class Receipt(TimestampMixin, Base):
    __tablename__ = "receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    receipt_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payments.payment_id"), nullable=False, unique=True
    )
    receipt_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    amount_in_words: Mapped[str | None] = mapped_column(String(255))
    received_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    payment: Mapped[Payment] = relationship(back_populates="receipt", lazy="selectin")
