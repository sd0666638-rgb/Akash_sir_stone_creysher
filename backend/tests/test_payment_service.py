from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.api.customers import customer_outstanding
from app.models import Base
from app.models.customer import Customer
from app.models.enums import (
    ChequeStatus,
    InvoicePaymentStatus,
    PaymentMethod,
    PaymentRecordStatus,
)
from app.models.invoice import Invoice
from app.models.payment import (
    CustomerAdvance,
    CustomerLedger,
    Payment,
    PaymentAllocation,
)
from app.schemas.payment import (
    PaymentAllocate,
    PaymentAllocationCreate,
    PaymentCreate,
)
from app.services.payment_service import (
    adjust_customer_advance,
    allocate_payment,
    receive_payment,
    reverse_payment,
    update_cheque_status,
)


TODAY = date(2026, 7, 25)


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False, future=True) as session:
        yield session
    engine.dispose()


def _customer_and_invoice(
    db: Session, *, total: Decimal = Decimal("100.00")
) -> tuple[Customer, Invoice]:
    customer = Customer(name="Partial Payment Customer")
    db.add(customer)
    db.flush()
    invoice = Invoice(
        invoice_number="INV-PARTIAL-001",
        invoice_date=TODAY,
        customer_id=customer.id,
        grand_total=total,
        remaining_amount=total,
        payment_status=InvoicePaymentStatus.UNPAID,
    )
    db.add(invoice)
    db.commit()
    return customer, invoice


def _payment_payload(
    customer_id: int,
    amount: Decimal,
    *,
    invoice_id: int | None = None,
    method: PaymentMethod = PaymentMethod.CASH,
) -> PaymentCreate:
    allocations = (
        [PaymentAllocationCreate(invoice_id=invoice_id, allocated_amount=amount)]
        if invoice_id is not None
        else []
    )
    return PaymentCreate(
        customer_id=customer_id,
        payment_date=TODAY,
        total_amount=amount,
        payment_method=method,
        cheque_number="CHQ-001" if method == PaymentMethod.CHEQUE else None,
        allocations=allocations,
    )


def test_payment_schemas_restrict_allocation_modes_and_duplicate_invoices():
    common = {
        "customer_id": 1,
        "payment_date": TODAY,
        "total_amount": Decimal("100.00"),
        "payment_method": PaymentMethod.CASH,
    }
    with pytest.raises(ValidationError):
        PaymentCreate(**common, allocation_method="due-date-priority")
    with pytest.raises(ValidationError, match="cannot start"):
        PaymentCreate(
            **{
                **common,
                "payment_method": PaymentMethod.CHEQUE,
                "cheque_number": "CHQ-INVALID",
                "cheque_status": ChequeStatus.BOUNCED,
            }
        )

    duplicate_allocations = [
        PaymentAllocationCreate(invoice_id=7, allocated_amount=Decimal("40.00")),
        PaymentAllocationCreate(invoice_id=7, allocated_amount=Decimal("60.00")),
    ]
    with pytest.raises(ValidationError, match="only once"):
        PaymentCreate(**common, allocations=duplicate_allocations)
    with pytest.raises(ValidationError, match="only once"):
        PaymentAllocate(allocations=duplicate_allocations)


def test_two_partial_payments_move_invoice_from_partial_to_fully_paid(db: Session):
    customer, invoice = _customer_and_invoice(db)

    receive_payment(
        db,
        _payment_payload(customer.id, Decimal("40.00"), invoice_id=invoice.id),
        user=None,
    )
    assert invoice.total_paid == Decimal("40.00")
    assert invoice.remaining_amount == Decimal("60.00")
    assert invoice.payment_status == InvoicePaymentStatus.PARTIALLY_PAID

    receive_payment(
        db,
        _payment_payload(customer.id, Decimal("60.00"), invoice_id=invoice.id),
        user=None,
    )
    assert invoice.total_paid == Decimal("100.00")
    assert invoice.remaining_amount == Decimal("0.00")
    assert invoice.payment_status == InvoicePaymentStatus.FULLY_PAID


def test_pending_cheque_reserves_invoice_until_it_bounces(db: Session):
    customer, invoice = _customer_and_invoice(db)
    cheque = receive_payment(
        db,
        _payment_payload(
            customer.id,
            Decimal("100.00"),
            invoice_id=invoice.id,
            method=PaymentMethod.CHEQUE,
        ),
        user=None,
    )

    assert cheque.payment_status == PaymentRecordStatus.PENDING
    assert invoice.payment_status == InvoicePaymentStatus.UNPAID
    assert invoice.pending_payment_amount == Decimal("100.00")
    assert invoice.available_payment_amount == Decimal("0.00")

    with pytest.raises(HTTPException, match="remaining amount"):
        receive_payment(
            db,
            _payment_payload(
                customer.id,
                Decimal("1.00"),
                invoice_id=invoice.id,
            ),
            user=None,
        )
    db.rollback()

    update_cheque_status(
        db,
        payment_id=cheque.id,
        cheque_status=ChequeStatus.BOUNCED,
        user=None,
    )
    receive_payment(
        db,
        _payment_payload(customer.id, Decimal("100.00"), invoice_id=invoice.id),
        user=None,
    )
    assert invoice.payment_status == InvoicePaymentStatus.FULLY_PAID


def test_late_allocation_requires_success_and_cannot_reuse_an_advance(db: Session):
    customer, invoice = _customer_and_invoice(db)
    advance_payment = receive_payment(
        db,
        _payment_payload(customer.id, Decimal("100.00")),
        user=None,
    )
    allocation = PaymentAllocate(
        allocations=[
            PaymentAllocationCreate(
                invoice_id=invoice.id,
                allocated_amount=Decimal("50.00"),
            )
        ]
    )

    with pytest.raises(HTTPException, match="adjust the advance instead") as conflict:
        allocate_payment(db, advance_payment.id, allocation, user=None)
    assert conflict.value.status_code == 409
    db.rollback()
    assert db.scalar(select(func.count(PaymentAllocation.id))) == 0

    pending_cheque = receive_payment(
        db,
        _payment_payload(
            customer.id,
            Decimal("10.00"),
            method=PaymentMethod.CHEQUE,
        ),
        user=None,
    )
    with pytest.raises(HTTPException, match="Only successful"):
        allocate_payment(db, pending_cheque.id, allocation, user=None)


def test_late_allocation_of_legacy_successful_unallocated_payment_is_counted_once(
    db: Session,
):
    customer, invoice = _customer_and_invoice(db)
    payment = Payment(
        receipt_number="RCT-LEGACY-001",
        customer_id=customer.id,
        payment_date=TODAY,
        total_amount=Decimal("100.00"),
        payment_method=PaymentMethod.CASH,
        payment_status=PaymentRecordStatus.SUCCESSFUL,
        unallocated_amount=Decimal("100.00"),
    )
    db.add(payment)
    db.commit()

    allocate_payment(
        db,
        payment.id,
        PaymentAllocate(
            allocations=[
                PaymentAllocationCreate(
                    invoice_id=invoice.id,
                    allocated_amount=Decimal("40.00"),
                )
            ]
        ),
        user=None,
    )

    assert payment.unallocated_amount == Decimal("60.00")
    assert invoice.total_paid == Decimal("40.00")
    assert invoice.remaining_amount == Decimal("60.00")
    ledger_credit = db.scalar(
        select(func.coalesce(func.sum(CustomerLedger.credit), 0))
    )
    assert ledger_credit == Decimal("40.00")


def test_reversal_unwinds_unused_advance_and_blocks_used_advance(db: Session):
    customer, invoice = _customer_and_invoice(db)
    unused_payment = receive_payment(
        db,
        _payment_payload(customer.id, Decimal("30.00")),
        user=None,
    )
    unused_advance = db.scalar(
        select(CustomerAdvance).where(
            CustomerAdvance.payment_id == unused_payment.id
        )
    )
    assert unused_advance is not None
    assert customer.advance_balance == Decimal("30.00")

    reverse_payment(
        db,
        payment_id=unused_payment.id,
        reversal_date=TODAY,
        reason="Incorrect receipt",
        user=None,
    )
    assert unused_payment.payment_status == PaymentRecordStatus.REVERSED
    assert unused_advance.remaining_balance == Decimal("0.00")
    assert customer.advance_balance == Decimal("0.00")

    used_payment = receive_payment(
        db,
        _payment_payload(customer.id, Decimal("100.00")),
        user=None,
    )
    adjust_customer_advance(
        db,
        customer_id=customer.id,
        invoice_id=invoice.id,
        adjustment_date=TODAY,
        amount=Decimal("40.00"),
        user=None,
    )
    with pytest.raises(HTTPException, match="already been adjusted") as conflict:
        reverse_payment(
            db,
            payment_id=used_payment.id,
            reversal_date=TODAY,
            reason="Cannot reverse applied funds",
            user=None,
        )
    assert conflict.value.status_code == 409
    db.rollback()
    assert db.get(Payment, used_payment.id).payment_status == PaymentRecordStatus.SUCCESSFUL


def test_cheque_status_is_idempotent_and_bounce_unwinds_unused_advance(db: Session):
    customer, _ = _customer_and_invoice(db)
    payment = receive_payment(
        db,
        _payment_payload(
            customer.id,
            Decimal("75.00"),
            method=PaymentMethod.CHEQUE,
        ),
        user=None,
    )

    update_cheque_status(
        db,
        payment_id=payment.id,
        cheque_status=ChequeStatus.CLEARED,
        user=None,
    )
    first_ledger_count = db.scalar(select(func.count(CustomerLedger.id)))
    first_advance_count = db.scalar(select(func.count(CustomerAdvance.id)))
    assert customer.advance_balance == Decimal("75.00")

    update_cheque_status(
        db,
        payment_id=payment.id,
        cheque_status=ChequeStatus.CLEARED,
        user=None,
    )
    assert db.scalar(select(func.count(CustomerLedger.id))) == first_ledger_count
    assert db.scalar(select(func.count(CustomerAdvance.id))) == first_advance_count

    update_cheque_status(
        db,
        payment_id=payment.id,
        cheque_status=ChequeStatus.BOUNCED,
        user=None,
    )
    advance = db.scalar(
        select(CustomerAdvance).where(CustomerAdvance.payment_id == payment.id)
    )
    bounced_ledger_count = db.scalar(select(func.count(CustomerLedger.id)))
    assert payment.payment_status == PaymentRecordStatus.BOUNCED
    assert advance is not None
    assert advance.remaining_balance == Decimal("0.00")
    assert customer.advance_balance == Decimal("0.00")

    update_cheque_status(
        db,
        payment_id=payment.id,
        cheque_status=ChequeStatus.BOUNCED,
        user=None,
    )
    assert db.scalar(select(func.count(CustomerLedger.id))) == bounced_ledger_count


def test_customer_outstanding_does_not_subtract_advance_twice(db: Session):
    customer, _ = _customer_and_invoice(db)
    receive_payment(
        db,
        _payment_payload(customer.id, Decimal("30.00")),
        user=None,
    )

    result = customer_outstanding(customer.id, db=db, _=None)

    assert result.outstanding_amount == Decimal("70.00")
    assert result.advance_balance == Decimal("30.00")
    assert result.net_outstanding == Decimal("70.00")
