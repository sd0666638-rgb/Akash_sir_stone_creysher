from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import StockMovementType


class Material(TimestampMixin, Base):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, nullable=False, index=True)
    hsn_code: Mapped[str | None] = mapped_column(String(20))
    unit: Mapped[str] = mapped_column(String(30), default="TON", nullable=False)
    selling_rate: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    purchase_rate: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    gst_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    stock_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0, nullable=False)
    minimum_stock: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    movements: Mapped[list["StockMovement"]] = relationship(
        back_populates="material", lazy="selectin"
    )


class StockMovement(TimestampMixin, Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), nullable=False)
    movement_type: Mapped[StockMovementType] = mapped_column(
        SAEnum(StockMovementType), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(80))
    movement_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    material: Mapped[Material] = relationship(back_populates="movements", lazy="selectin")
