from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import asc, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.customer import Customer
from app.models.enums import (
    ChequeStatus,
    InvoicePaymentStatus,
    LedgerTransactionType,
    PaymentMethod,
    PaymentRecordStatus,
)
from app.models.invoice import Invoice
from app.models.payment import (
    AdvanceAdjustment,
    ChequePayment,
    CustomerAdvance,
    Payment,
    PaymentAllocation,
    PaymentReversal,
    Receipt,
)
from app.models.user import User
from app.schemas.payment import PaymentAllocate, PaymentAllocationCreate, PaymentCreate
from app.services.accounting import (
    is_collectable_payment,
    invoice_remaining_for_allocation,
    payment_allocated_total,
    refresh_customer_balances,
    refresh_invoice_payment_state,
)
from app.services.audit import write_audit
from app.services.calculations import money
from app.services.ledger_service import append_ledger_entry
from app.utils.numbers import amount_to_indian_words


def generate_receipt_number(db: Session, payment_date: date) -> str:
    prefix = payment_date.strftime("RCT-%Y%m%d")
    count = db.scalar(select(func.count(Payment.id)).where(Payment.receipt_number.like(f"{prefix}%")))
    return f"{prefix}-{(count or 0) + 1:04d}"


def _initial_payment_status(payload: PaymentCreate) -> PaymentRecordStatus:
    if (
        settings.CHEQUE_COLLECTION_REQUIRES_CLEARANCE
        and payload.payment_method == PaymentMethod.CHEQUE
        and payload.cheque_status != ChequeStatus.CLEARED
    ):
        return PaymentRecordStatus.PENDING
    return PaymentRecordStatus.SUCCESSFUL


def _lock_customer(db: Session, customer_id: int) -> Customer | None:
    return db.scalar(
        select(Customer)
        .where(Customer.id == customer_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def _lock_payment(db: Session, payment_id: int) -> Payment | None:
    return db.scalar(
        select(Payment)
        .where(Payment.id == payment_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def _pending_invoices(db: Session, customer_id: int) -> list[Invoice]:
    invoices = db.scalars(
        select(Invoice)
        .where(
            Invoice.customer_id == customer_id,
            Invoice.payment_status.notin_(
                [InvoicePaymentStatus.FULLY_PAID, InvoicePaymentStatus.CANCELLED]
            ),
        )
        .order_by(asc(Invoice.invoice_date), asc(Invoice.id))
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    pending = []
    for invoice in invoices:
        refresh_invoice_payment_state(db, invoice)
        if invoice_remaining_for_allocation(invoice) > 0:
            pending.append(invoice)
    return pending


def _auto_allocations(db: Session, payload: PaymentCreate) -> list[PaymentAllocationCreate]:
    if payload.allocations or payload.allocation_method != "oldest-invoice-first":
        return payload.allocations

    remaining = money(payload.total_amount)
    allocations: list[PaymentAllocationCreate] = []
    for invoice in _pending_invoices(db, payload.customer_id):
        if remaining <= 0:
            break
        amount = min(remaining, invoice_remaining_for_allocation(invoice))
        allocations.append(PaymentAllocationCreate(invoice_id=invoice.id, allocated_amount=amount))
        remaining = money(remaining - amount)
    return allocations


def _validate_allocations(
    db: Session,
    *,
    customer_id: int,
    allocations: list[PaymentAllocationCreate],
) -> list[Invoice]:
    invoice_ids = [allocation.invoice_id for allocation in allocations]
    if len(invoice_ids) != len(set(invoice_ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Each invoice can be allocated only once per payment",
        )
    if not invoice_ids:
        return []

    invoices = db.scalars(
        select(Invoice)
        .where(Invoice.id.in_(sorted(invoice_ids)))
        .order_by(Invoice.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    invoices_by_id = {invoice.id: invoice for invoice in invoices}

    validated = []
    for allocation in allocations:
        invoice = invoices_by_id.get(allocation.invoice_id)
        if invoice is None or invoice.customer_id != customer_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
        if invoice.payment_status == InvoicePaymentStatus.CANCELLED:
            raise HTTPException(status_code=400, detail="Cancelled invoices cannot receive payments")
        refresh_invoice_payment_state(db, invoice)
        if money(allocation.allocated_amount) > invoice_remaining_for_allocation(invoice):
            raise HTTPException(status_code=400, detail="Allocation exceeds invoice remaining amount")
        validated.append(invoice)
    return validated


def _linked_advances(
    db: Session, payment_id: int, *, lock: bool = False
) -> list[CustomerAdvance]:
    stmt = (
        select(CustomerAdvance)
        .where(CustomerAdvance.payment_id == payment_id)
        .order_by(CustomerAdvance.id)
        .execution_options(populate_existing=True)
    )
    if lock:
        stmt = stmt.with_for_update()
    return list(db.scalars(stmt).all())


def _ensure_advances_are_unused(advances: list[CustomerAdvance]) -> None:
    if any(advance.total_adjusted > 0 or advance.adjustments for advance in advances):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This payment advance has already been adjusted against an invoice",
        )


def _unwind_linked_advances(
    db: Session,
    payment: Payment,
    advances: list[CustomerAdvance],
) -> None:
    _ensure_advances_are_unused(advances)
    unused_total = money(
        sum((advance.remaining_balance for advance in advances), Decimal("0"))
    )
    customer = db.get(Customer, payment.customer_id)
    if customer is not None and unused_total > 0:
        customer.advance_balance = max(
            money(customer.advance_balance - unused_total),
            Decimal("0.00"),
        )
    for advance in advances:
        advance.remaining_balance = Decimal("0.00")


def _recorded_collection_total(
    payment: Payment, advances: list[CustomerAdvance]
) -> Decimal:
    return money(
        payment_allocated_total(payment)
        + sum((advance.total_received for advance in advances), Decimal("0"))
    )


def _create_receipt(db: Session, payment: Payment, user: User | None) -> Receipt:
    receipt = Receipt(
        receipt_number=payment.receipt_number,
        payment_id=payment.id,
        receipt_date=payment.payment_date,
        amount=payment.total_amount,
        amount_in_words=amount_to_indian_words(payment.total_amount),
        received_by=user.id if user else None,
    )
    db.add(receipt)
    return receipt


def receive_payment(
    db: Session, payload: PaymentCreate, user: User | None, *, commit: bool = True
) -> Payment:
    # These services can be composed in one transaction (for example while
    # creating an invoice), so persist pending ORM changes before reloading
    # rows with locks for validation.
    db.flush()
    customer = _lock_customer(db, payload.customer_id)
    if customer is None or not customer.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    allocations = _auto_allocations(db, payload)
    allocated_total = money(sum((item.allocated_amount for item in allocations), Decimal("0")))
    if allocated_total > money(payload.total_amount):
        raise HTTPException(status_code=400, detail="Total allocations cannot exceed payment amount")

    allocation_invoices = _validate_allocations(
        db,
        customer_id=payload.customer_id,
        allocations=allocations,
    )

    payment = Payment(
        receipt_number=generate_receipt_number(db, payload.payment_date),
        customer_id=payload.customer_id,
        payment_date=payload.payment_date,
        total_amount=money(payload.total_amount),
        payment_method=payload.payment_method,
        transaction_reference=payload.transaction_reference,
        bank_name=payload.bank_name,
        cheque_number=payload.cheque_number,
        cheque_date=payload.cheque_date,
        cheque_status=payload.cheque_status,
        notes=payload.notes,
        payment_status=_initial_payment_status(payload),
        unallocated_amount=money(payload.total_amount - allocated_total),
        created_by=user.id if user else None,
    )
    db.add(payment)
    db.flush()

    for allocation, invoice in zip(allocations, allocation_invoices):
        db.add(
            PaymentAllocation(
                payment=payment,
                invoice=invoice,
                allocated_amount=money(allocation.allocated_amount),
                allocation_date=payload.payment_date,
                created_by=user.id if user else None,
            )
        )

    if payload.payment_method == PaymentMethod.CHEQUE:
        payment.cheque_status = payload.cheque_status or ChequeStatus.RECEIVED
        db.add(
            ChequePayment(
                payment_id=payment.id,
                cheque_number=payload.cheque_number or "",
                cheque_date=payload.cheque_date,
                bank_name=payload.bank_name,
                cheque_status=payment.cheque_status,
            )
        )

    if payment.unallocated_amount > Decimal("0") and payment.payment_status == PaymentRecordStatus.SUCCESSFUL:
        _create_advance_from_payment(db, payment, user)

    _create_receipt(db, payment, user)
    if allocated_total > Decimal("0") and payment.payment_status == PaymentRecordStatus.SUCCESSFUL:
        append_ledger_entry(
            db,
            customer_id=payment.customer_id,
            transaction_date=payment.payment_date,
            transaction_type=LedgerTransactionType.PAYMENT,
            reference_number=payment.receipt_number,
            description="Payment received",
            credit=allocated_total,
        )

    for invoice in allocation_invoices:
        refresh_invoice_payment_state(db, invoice)
    refresh_customer_balances(db, payment.customer_id)
    write_audit(
        db,
        user=user,
        action="create",
        module="payment",
        record_id=payment.id,
        new_value={"receipt_number": payment.receipt_number, "amount": str(payment.total_amount)},
    )
    if commit:
        db.commit()
        db.refresh(payment)
    return payment


def allocate_payment(
    db: Session, payment_id: int, payload: PaymentAllocate, user: User | None
) -> Payment:
    db.flush()
    payment_reference = db.get(Payment, payment_id)
    if payment_reference is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    _lock_customer(db, payment_reference.customer_id)
    payment = _lock_payment(db, payment_id)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    if (
        payment.payment_status != PaymentRecordStatus.SUCCESSFUL
        or not is_collectable_payment(payment)
    ):
        raise HTTPException(
            status_code=400,
            detail="Only successful payments can be allocated",
        )

    linked_advances = _linked_advances(db, payment.id, lock=True)
    if linked_advances:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Unallocated funds from this payment are recorded as customer advance; "
                "adjust the advance instead"
            ),
        )

    allocated_total = money(sum((item.allocated_amount for item in payload.allocations), Decimal("0")))
    available = min(
        money(payment.total_amount - payment_allocated_total(payment)),
        money(payment.unallocated_amount),
    )
    if allocated_total > available:
        raise HTTPException(status_code=400, detail="Total allocations exceed available payment amount")

    invoices = _validate_allocations(
        db,
        customer_id=payment.customer_id,
        allocations=payload.allocations,
    )
    for allocation, invoice in zip(payload.allocations, invoices):
        db.add(
            PaymentAllocation(
                payment=payment,
                invoice=invoice,
                allocated_amount=money(allocation.allocated_amount),
                allocation_date=date.today(),
                created_by=user.id if user else None,
            )
        )

    payment.unallocated_amount = money(payment.unallocated_amount - allocated_total)
    append_ledger_entry(
        db,
        customer_id=payment.customer_id,
        transaction_date=date.today(),
        transaction_type=LedgerTransactionType.PAYMENT,
        reference_number=payment.receipt_number,
        description="Payment allocated to invoice",
        credit=allocated_total,
    )
    for invoice in invoices:
        refresh_invoice_payment_state(db, invoice)
    refresh_customer_balances(db, payment.customer_id)
    write_audit(
        db,
        user=user,
        action="allocate",
        module="payment",
        record_id=payment.id,
        new_value={"allocated_total": str(allocated_total)},
    )
    db.commit()
    db.refresh(payment)
    return payment


def _create_advance_from_payment(db: Session, payment: Payment, user: User | None) -> CustomerAdvance:
    advance = CustomerAdvance(
        customer_id=payment.customer_id,
        payment_id=payment.id,
        advance_date=payment.payment_date,
        total_received=payment.unallocated_amount,
        total_adjusted=Decimal("0"),
        remaining_balance=payment.unallocated_amount,
        notes="Unallocated customer payment",
        created_by=user.id if user else None,
    )
    db.add(advance)
    customer = db.get(Customer, payment.customer_id)
    if customer:
        customer.advance_balance = money(customer.advance_balance + payment.unallocated_amount)
    append_ledger_entry(
        db,
        customer_id=payment.customer_id,
        transaction_date=payment.payment_date,
        transaction_type=LedgerTransactionType.ADVANCE_PAYMENT,
        reference_number=payment.receipt_number,
        description="Customer advance received",
        credit=payment.unallocated_amount,
    )
    return advance


def create_customer_advance(
    db: Session,
    *,
    customer_id: int,
    advance_date: date,
    amount: Decimal,
    payment_method: PaymentMethod,
    notes: str | None,
    user: User | None,
) -> CustomerAdvance:
    payment = receive_payment(
        db,
        PaymentCreate(
            customer_id=customer_id,
            payment_date=advance_date,
            total_amount=amount,
            payment_method=payment_method,
            notes=notes or "Customer advance",
            allocations=[],
        ),
        user,
        commit=False,
    )
    advance = db.scalar(select(CustomerAdvance).where(CustomerAdvance.payment_id == payment.id))
    write_audit(
        db,
        user=user,
        action="create",
        module="advance",
        record_id=advance.id if advance else payment.id,
        new_value={"amount": str(amount)},
    )
    db.commit()
    if advance:
        db.refresh(advance)
        return advance
    raise HTTPException(status_code=500, detail="Advance could not be created")


def adjust_customer_advance(
    db: Session,
    *,
    customer_id: int,
    invoice_id: int,
    adjustment_date: date,
    amount: Decimal,
    user: User | None,
    commit: bool = True,
) -> list[AdvanceAdjustment]:
    db.flush()
    customer = _lock_customer(db, customer_id)
    invoice = db.scalar(
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if customer is None or invoice is None or invoice.customer_id != customer_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer or invoice not found")
    refresh_invoice_payment_state(db, invoice)
    if invoice.payment_status == InvoicePaymentStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="Cancelled invoices cannot receive advances")
    if amount > customer.advance_balance:
        raise HTTPException(status_code=400, detail="Advance adjustment exceeds available advance balance")
    if amount > invoice_remaining_for_allocation(invoice):
        raise HTTPException(status_code=400, detail="Advance adjustment exceeds invoice remaining amount")

    remaining = money(amount)
    adjustments: list[AdvanceAdjustment] = []
    advances = db.scalars(
        select(CustomerAdvance)
        .where(CustomerAdvance.customer_id == customer_id, CustomerAdvance.remaining_balance > 0)
        .order_by(CustomerAdvance.advance_date, CustomerAdvance.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    for advance in advances:
        if remaining <= 0:
            break
        applied = min(remaining, advance.remaining_balance)
        advance.total_adjusted = money(advance.total_adjusted + applied)
        advance.remaining_balance = money(advance.remaining_balance - applied)
        adjustment = AdvanceAdjustment(
            advance=advance,
            customer_id=customer_id,
            invoice=invoice,
            adjustment_date=adjustment_date,
            adjusted_amount=applied,
            created_by=user.id if user else None,
        )
        db.add(adjustment)
        adjustments.append(adjustment)
        remaining = money(remaining - applied)

    if remaining > 0:
        raise HTTPException(status_code=400, detail="Insufficient advance balance")

    customer.advance_balance = money(customer.advance_balance - amount)
    append_ledger_entry(
        db,
        customer_id=customer_id,
        transaction_date=adjustment_date,
        transaction_type=LedgerTransactionType.ADVANCE_ADJUSTMENT,
        reference_number=invoice.invoice_number,
        description="Advance adjusted against invoice",
        credit=amount,
        payment_status=invoice.payment_status.value,
    )
    refresh_invoice_payment_state(db, invoice)
    refresh_customer_balances(db, customer_id)
    write_audit(
        db,
        user=user,
        action="adjust",
        module="advance",
        record_id=invoice_id,
        new_value={"amount": str(amount)},
    )
    if commit:
        db.commit()
    return adjustments


def reverse_payment(
    db: Session,
    *,
    payment_id: int,
    reversal_date: date,
    reason: str,
    user: User | None,
) -> Payment:
    db.flush()
    payment_reference = db.get(Payment, payment_id)
    if payment_reference is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    _lock_customer(db, payment_reference.customer_id)
    payment = _lock_payment(db, payment_id)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    if payment.payment_status == PaymentRecordStatus.REVERSED:
        raise HTTPException(status_code=400, detail="Payment is already reversed")
    if payment.payment_status in {
        PaymentRecordStatus.BOUNCED,
        PaymentRecordStatus.CANCELLED,
    }:
        raise HTTPException(
            status_code=400,
            detail="Bounced or cancelled payments cannot be reversed again",
        )

    previous_status = payment.payment_status.value
    was_collectable = is_collectable_payment(payment)
    linked_advances = _linked_advances(db, payment.id, lock=True)
    recorded_collection = (
        _recorded_collection_total(payment, linked_advances)
        if was_collectable
        else Decimal("0.00")
    )
    _unwind_linked_advances(db, payment, linked_advances)
    payment.payment_status = PaymentRecordStatus.REVERSED
    db.add(
        PaymentReversal(
            payment_id=payment.id,
            reversal_date=reversal_date,
            reversal_amount=payment.total_amount,
            reason=reason,
            created_by=user.id if user else None,
        )
    )
    if recorded_collection > 0:
        append_ledger_entry(
            db,
            customer_id=payment.customer_id,
            transaction_date=reversal_date,
            transaction_type=LedgerTransactionType.PAYMENT_REVERSAL,
            reference_number=payment.receipt_number,
            description=reason,
            debit=recorded_collection,
        )

    for allocation in payment.allocations:
        refresh_invoice_payment_state(db, allocation.invoice)
    refresh_customer_balances(db, payment.customer_id)
    write_audit(
        db,
        user=user,
        action="reverse",
        module="payment",
        record_id=payment.id,
        previous_value={"payment_status": previous_status},
        new_value={"payment_status": payment.payment_status.value, "reason": reason},
    )
    db.commit()
    db.refresh(payment)
    return payment


def update_cheque_status(
    db: Session,
    *,
    payment_id: int,
    cheque_status: ChequeStatus,
    user: User | None,
    bounce_charges: Decimal = Decimal("0"),
    notes: str | None = None,
) -> Payment:
    if money(bounce_charges) < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bounce charges cannot be negative",
        )
    db.flush()
    payment_reference = db.get(Payment, payment_id)
    if payment_reference is None or payment_reference.payment_method != PaymentMethod.CHEQUE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cheque payment not found")

    _lock_customer(db, payment_reference.customer_id)
    payment = _lock_payment(db, payment_id)
    if payment is None or payment.payment_method != PaymentMethod.CHEQUE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cheque payment not found")

    previous_status = payment.cheque_status
    if previous_status == cheque_status:
        return payment
    if previous_status in {ChequeStatus.BOUNCED, ChequeStatus.CANCELLED}:
        raise HTTPException(
            status_code=400,
            detail="Bounced or cancelled cheques cannot change status",
        )
    if previous_status == ChequeStatus.CLEARED and cheque_status in {
        ChequeStatus.RECEIVED,
        ChequeStatus.DEPOSITED,
    }:
        raise HTTPException(
            status_code=400,
            detail="A cleared cheque cannot return to a pending status",
        )

    previous = previous_status.value if previous_status else None
    was_collectable = is_collectable_payment(payment)
    linked_advances = _linked_advances(db, payment.id, lock=True)
    recorded_collection = (
        _recorded_collection_total(payment, linked_advances)
        if was_collectable
        else Decimal("0.00")
    )

    if cheque_status in {ChequeStatus.BOUNCED, ChequeStatus.CANCELLED}:
        _unwind_linked_advances(db, payment, linked_advances)

    payment.cheque_status = cheque_status
    if payment.cheque_payment:
        payment.cheque_payment.cheque_status = cheque_status
        payment.cheque_payment.bounce_charges = money(bounce_charges)
        payment.cheque_payment.notes = notes

    if cheque_status == ChequeStatus.CLEARED:
        payment.payment_status = PaymentRecordStatus.SUCCESSFUL
        allocated_total = payment_allocated_total(payment)
        if allocated_total > Decimal("0"):
            append_ledger_entry(
                db,
                customer_id=payment.customer_id,
                transaction_date=date.today(),
                transaction_type=LedgerTransactionType.PAYMENT,
                reference_number=payment.receipt_number,
                description="Cheque cleared",
                credit=allocated_total,
            )
        if payment.unallocated_amount > Decimal("0"):
            if not linked_advances:
                _create_advance_from_payment(db, payment, user)
    elif cheque_status == ChequeStatus.BOUNCED:
        payment.payment_status = PaymentRecordStatus.BOUNCED
        reversal_total = money(recorded_collection + money(bounce_charges))
        if reversal_total > 0:
            append_ledger_entry(
                db,
                customer_id=payment.customer_id,
                transaction_date=date.today(),
                transaction_type=LedgerTransactionType.PAYMENT_REVERSAL,
                reference_number=payment.receipt_number,
                description=notes or "Cheque bounced",
                debit=reversal_total,
            )
    elif cheque_status == ChequeStatus.CANCELLED:
        payment.payment_status = PaymentRecordStatus.CANCELLED
        if recorded_collection > 0:
            append_ledger_entry(
                db,
                customer_id=payment.customer_id,
                transaction_date=date.today(),
                transaction_type=LedgerTransactionType.PAYMENT_REVERSAL,
                reference_number=payment.receipt_number,
                description=notes or "Cheque cancelled",
                debit=recorded_collection,
            )
    else:
        payment.payment_status = PaymentRecordStatus.PENDING

    for allocation in payment.allocations:
        refresh_invoice_payment_state(db, allocation.invoice)
    refresh_customer_balances(db, payment.customer_id)
    write_audit(
        db,
        user=user,
        action="cheque_status_change",
        module="payment",
        record_id=payment.id,
        previous_value={"cheque_status": previous},
        new_value={"cheque_status": cheque_status.value},
    )
    db.commit()
    db.refresh(payment)
    return payment
