from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel
from app.utils.phone import normalize_mobile_number


class CustomerBase(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    mobile_number: str | None = None
    gst_number: str | None = None
    billing_address: str | None = None
    delivery_address: str | None = None
    city: str | None = None
    state: str | None = None
    opening_balance: Decimal = Decimal("0")
    credit_limit: Decimal = Decimal("0")
    credit_period_days: int = Field(default=0, ge=0)
    is_active: bool = True


class CustomerCreate(CustomerBase):
    mobile_number: str = Field(min_length=10, max_length=30)

    @field_validator("mobile_number", mode="before")
    @classmethod
    def normalize_required_mobile(cls, value):
        return normalize_mobile_number(value)


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    mobile_number: str | None = Field(default=None, min_length=10, max_length=30)
    gst_number: str | None = None
    billing_address: str | None = None
    delivery_address: str | None = None
    city: str | None = None
    state: str | None = None
    opening_balance: Decimal | None = None
    credit_limit: Decimal | None = None
    credit_period_days: int | None = Field(default=None, ge=0)
    is_active: bool | None = None

    @field_validator("mobile_number", mode="before")
    @classmethod
    def normalize_updated_mobile(cls, value):
        if value is None:
            raise ValueError("Mobile number cannot be removed")
        return normalize_mobile_number(value)


class CustomerOut(CustomerBase, ORMModel):
    id: int
    current_outstanding_balance: Decimal
    advance_balance: Decimal


class CustomerOutstanding(BaseModel):
    customer_id: int
    outstanding_amount: Decimal
    advance_balance: Decimal
    net_outstanding: Decimal
