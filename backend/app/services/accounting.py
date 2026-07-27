from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.customer import Customer
from app.models.enums import InvoicePaymentStatus, PaymentMethod, PaymentRecordStatus
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.services.calculations import derive_invoice_status, money, remaining_amount


def is_collectable_payment(payment: Payment) -> bool:
    if payment.payment_status != PaymentRecordStatus.SUCCESSFUL:
        return False
    if (
        settings.CHEQUE_COLLECTION_REQUIRES_CLEARANCE
        and payment.payment_method == PaymentMethod.CHEQUE
    ):
        return bool(payment.cheque_status and payment.cheque_status.value == "Cleared")
    return True


def refresh_invoice_payment_state(db: Session, invoice: Invoice) -> Invoice:
    if invoice.payment_status == InvoicePaymentStatus.CANCELLED:
        invoice.total_paid = Decimal("0.00")
        invoice.remaining_amount = Decimal("0.00")
        return invoice

    total_paid = Decimal("0")
    for allocation in invoice.allocations:
        if is_collectable_payment(allocation.payment):
            total_paid += allocation.allocated_amount

    advance_adjusted = sum(
        (adjustment.adjusted_amount for adjustment in invoice.advance_adjustments),
        Decimal("0"),
    )
    invoice.total_paid = money(total_paid)
    invoice.advance_adjusted = money(advance_adjusted)
    invoice.remaining_amount = remaining_amount(
        invoice.grand_total, invoice.total_paid, invoice.advance_adjusted
    )
    invoice.payment_status = derive_invoice_status(
        invoice.grand_total, invoice.total_paid, invoice.advance_adjusted
    )
    return invoice


def refresh_customer_balances(db: Session, customer_id: int) -> Customer:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise ValueError("Customer not found")

    invoices = db.scalars(
        select(Invoice).where(
            Invoice.customer_id == customer_id,
            Invoice.payment_status != InvoicePaymentStatus.CANCELLED,
        )
    ).all()
    for invoice in invoices:
        refresh_invoice_payment_state(db, invoice)

    outstanding = sum(
        (invoice.remaining_amount for invoice in invoices if invoice.remaining_amount > 0),
        Decimal("0"),
    )
    customer.current_outstanding_balance = money(
        customer.opening_balance + outstanding - customer.advance_balance
    )
    if customer.current_outstanding_balance < 0:
        customer.current_outstanding_balance = Decimal("0.00")
    return customer


def invoice_remaining_for_allocation(invoice: Invoice) -> Decimal:
    return money(invoice.available_payment_amount)


def payment_allocated_total(payment: Payment) -> Decimal:
    return money(sum((allocation.allocated_amount for allocation in payment.allocations), Decimal("0")))
