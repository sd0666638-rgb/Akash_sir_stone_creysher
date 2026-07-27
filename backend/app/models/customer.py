from decimal import Decimal

from sqlalchemy import Boolean, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("mobile_number", name="uq_customers_mobile_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    mobile_number: Mapped[str | None] = mapped_column(String(30), index=True)
    gst_number: Mapped[str | None] = mapped_column(String(30), index=True)
    billing_address: Mapped[str | None] = mapped_column(Text)
    delivery_address: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(100))
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    credit_limit: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    credit_period_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_outstanding_balance: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=0, nullable=False
    )
    advance_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    invoices: Mapped[list["Invoice"]] = relationship(back_populates="customer", lazy="selectin")
    payments: Mapped[list["Payment"]] = relationship(back_populates="customer", lazy="selectin")
