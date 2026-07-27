from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models.enums import ChequeStatus, PaymentMethod, PaymentRecordStatus
from app.models.enums import LedgerTransactionType
from app.schemas.common import ORMModel


class PaymentAllocationCreate(BaseModel):
    invoice_id: int
    allocated_amount: Decimal = Field(gt=0)


class PaymentCreate(BaseModel):
    customer_id: int
    payment_date: date
    total_amount: Decimal = Field(gt=0)
    payment_method: PaymentMethod
    transaction_reference: str | None = None
    bank_name: str | None = None
    cheque_number: str | None = None
    cheque_date: date | None = None
    cheque_status: ChequeStatus | None = None
    notes: str | None = None
    allocation_method: Literal["manual", "oldest-invoice-first"] = "manual"
    allocations: list[PaymentAllocationCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_payment(self):
        if self.payment_method == PaymentMethod.CHEQUE and not self.cheque_number:
            raise ValueError("Cheque number is required for cheque payments")
        if self.payment_method == PaymentMethod.CHEQUE and self.cheque_status in {
            ChequeStatus.BOUNCED,
            ChequeStatus.CANCELLED,
        }:
            raise ValueError("A new cheque cannot start as bounced or cancelled")
        invoice_ids = [allocation.invoice_id for allocation in self.allocations]
        if len(invoice_ids) != len(set(invoice_ids)):
            raise ValueError("Each invoice can be allocated only once per payment")
        return self


class PaymentAllocationOut(ORMModel):
    id: int
    payment_id: int
    invoice_id: int
    allocated_amount: Decimal
    allocation_date: date


class PaymentOut(ORMModel):
    id: int
    receipt_number: str
    customer_id: int
    payment_date: date
    total_amount: Decimal
    payment_method: PaymentMethod
    transaction_reference: str | None
    bank_name: str | None
    cheque_number: str | None
    cheque_date: date | None
    cheque_status: ChequeStatus | None
    notes: str | None
    payment_status: PaymentRecordStatus
    unallocated_amount: Decimal
    allocations: list[PaymentAllocationOut] = Field(default_factory=list)


class PaymentAllocate(BaseModel):
    allocation_method: Literal["manual", "oldest-invoice-first"] = "manual"
    allocations: list[PaymentAllocationCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def require_unique_invoices(self):
        invoice_ids = [allocation.invoice_id for allocation in self.allocations]
        if len(invoice_ids) != len(set(invoice_ids)):
            raise ValueError("Each invoice can be allocated only once per payment")
        return self


class PaymentReverse(BaseModel):
    reversal_date: date
    reason: str = Field(min_length=3, max_length=255)


class AdvanceCreate(BaseModel):
    customer_id: int
    advance_date: date
    amount: Decimal = Field(gt=0)
    payment_method: PaymentMethod = PaymentMethod.CASH
    notes: str | None = None


class AdvanceAdjust(BaseModel):
    invoice_id: int
    adjustment_date: date
    amount: Decimal = Field(gt=0)


class AdvanceOut(ORMModel):
    id: int
    customer_id: int
    payment_id: int | None
    advance_date: date
    total_received: Decimal
    total_adjusted: Decimal
    remaining_balance: Decimal
    notes: str | None


class CustomerLedgerOut(ORMModel):
    id: int
    customer_id: int
    transaction_date: date
    transaction_type: LedgerTransactionType
    reference_number: str
    description: str | None
    debit: Decimal
    credit: Decimal
    running_balance: Decimal
    payment_status: str | None
