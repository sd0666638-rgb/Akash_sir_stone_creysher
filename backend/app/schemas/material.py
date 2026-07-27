from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.models.enums import StockMovementType
from app.schemas.common import ORMModel


MaterialName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=2, max_length=160),
]
MaterialUnit = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=30),
]


class MaterialBase(BaseModel):
    name: MaterialName
    hsn_code: str | None = Field(default=None, max_length=20)
    unit: MaterialUnit = "TON"
    selling_rate: Decimal = Field(default=Decimal("0"), ge=0)
    purchase_rate: Decimal = Field(default=Decimal("0"), ge=0)
    gst_percentage: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    stock_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    minimum_stock: Decimal = Field(default=Decimal("0"), ge=0)
    is_active: bool = True


class MaterialCreate(MaterialBase):
    pass


class MaterialUpdate(BaseModel):
    name: MaterialName | None = None
    hsn_code: str | None = Field(default=None, max_length=20)
    unit: MaterialUnit | None = None
    selling_rate: Decimal | None = Field(default=None, ge=0)
    purchase_rate: Decimal | None = Field(default=None, ge=0)
    gst_percentage: Decimal | None = Field(default=None, ge=0, le=100)
    stock_quantity: Decimal | None = Field(default=None, ge=0)
    minimum_stock: Decimal | None = Field(default=None, ge=0)
    is_active: bool | None = None

    @field_validator(
        "name",
        "unit",
        "selling_rate",
        "purchase_rate",
        "gst_percentage",
        "stock_quantity",
        "minimum_stock",
        "is_active",
    )
    @classmethod
    def reject_null_for_required_columns(cls, value):
        if value is None:
            raise ValueError("Field cannot be null")
        return value


class MaterialOut(MaterialBase, ORMModel):
    id: int


class StockUpdate(BaseModel):
    movement_type: Literal[StockMovementType.IN, StockMovementType.OUT]
    quantity: Decimal = Field(gt=0)
    reference_number: str | None = None
