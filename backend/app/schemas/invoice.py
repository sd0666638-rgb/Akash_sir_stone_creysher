from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.models.enums import InvoicePaymentStatus
from app.schemas.common import ORMModel


class InvoiceItemBase(BaseModel):
    material_id: int | None = None
    material_name: str
    dispatch_date: date | None = None
    receipt_number: str | None = Field(default=None, max_length=80)
    hsn_code: str | None = Field(default=None, max_length=20)
    vehicle_number: str | None = Field(default=None, max_length=40)
    quantity: Decimal = Field(gt=0)
    unit: str = "TON"
    rate: Decimal = Field(ge=0)
    gst_percentage: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    discount_percentage: Decimal = Field(default=Decimal("0"), ge=0, le=100)


class InvoiceItemCreate(InvoiceItemBase):
    pass


class InvoiceItemOut(InvoiceItemBase, ORMModel):
    id: int
    line_subtotal: Decimal
    discount_amount: Decimal
    taxable_amount: Decimal
    gst_amount: Decimal
    line_total: Decimal


class InvoiceCreate(BaseModel):
    invoice_date: date
    customer_id: int
    delivery_note: str | None = Field(default=None, max_length=120)
    other_reference: str | None = Field(default=None, max_length=160)
    buyer_order_number: str | None = Field(default=None, max_length=120)
    vehicle_number: str | None = None
    driver_name: str | None = None
    transporter: str | None = None
    delivery_location: str | None = None
    payment_type: str | None = None
    notes: str | None = None
    transport_charges: Decimal = Field(default=Decimal("0"), ge=0)
    loading_charges: Decimal = Field(default=Decimal("0"), ge=0)
    other_charges: Decimal = Field(default=Decimal("0"), ge=0)
    round_off: Decimal = Field(default=Decimal("0"), ge=Decimal("-1"), le=Decimal("1"))
    amount_paid_now: Decimal = Field(default=Decimal("0"), ge=0)
    payment_method: str | None = None
    advance_to_adjust: Decimal = Field(default=Decimal("0"), ge=0)
    items: list[InvoiceItemCreate]

    @model_validator(mode="after")
    def require_items(self):
        if not self.items:
            raise ValueError("At least one invoice item is required")
        return self


class InvoiceUpdate(BaseModel):
    delivery_note: str | None = Field(default=None, max_length=120)
    other_reference: str | None = Field(default=None, max_length=160)
    buyer_order_number: str | None = Field(default=None, max_length=120)
    vehicle_number: str | None = None
    driver_name: str | None = None
    transporter: str | None = None
    delivery_location: str | None = None
    notes: str | None = None


class InvoiceOut(ORMModel):
    id: int
    invoice_number: str
    invoice_date: date
    customer_id: int
    delivery_note: str | None
    other_reference: str | None
    buyer_order_number: str | None
    vehicle_number: str | None
    driver_name: str | None
    transporter: str | None
    delivery_location: str | None
    payment_type: str | None
    subtotal: Decimal
    discount_amount: Decimal
    taxable_amount: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    igst_amount: Decimal
    transport_charges: Decimal
    loading_charges: Decimal
    other_charges: Decimal
    round_off: Decimal
    grand_total: Decimal
    total_paid: Decimal
    advance_adjusted: Decimal
    remaining_amount: Decimal
    pending_payment_amount: Decimal
    available_payment_amount: Decimal
    payment_status: InvoicePaymentStatus
    items: list[InvoiceItemOut] = []


class InvoiceOutstanding(BaseModel):
    invoice_id: int
    invoice_number: str
    grand_total: Decimal
    total_paid: Decimal
    advance_adjusted: Decimal
    remaining_amount: Decimal
    payment_status: InvoicePaymentStatus


class BuyerOrderNumberPreview(BaseModel):
    buyer_order_number: str
