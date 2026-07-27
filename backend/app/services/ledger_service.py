from datetime import date
from decimal import Decimal

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.enums import LedgerTransactionType
from app.models.payment import CustomerLedger
from app.services.calculations import money


def append_ledger_entry(
    db: Session,
    *,
    customer_id: int,
    transaction_date: date,
    transaction_type: LedgerTransactionType,
    reference_number: str,
    description: str | None,
    debit: Decimal = Decimal("0"),
    credit: Decimal = Decimal("0"),
    payment_status: str | None = None,
    due_date: date | None = None,
) -> CustomerLedger:
    previous = db.scalar(
        select(CustomerLedger)
        .where(CustomerLedger.customer_id == customer_id)
        .order_by(desc(CustomerLedger.transaction_date), desc(CustomerLedger.id))
        .limit(1)
    )
    previous_balance = previous.running_balance if previous else Decimal("0")
    entry = CustomerLedger(
        customer_id=customer_id,
        transaction_date=transaction_date,
        transaction_type=transaction_type,
        reference_number=reference_number,
        description=description,
        debit=money(debit),
        credit=money(credit),
        running_balance=money(previous_balance + debit - credit),
        payment_status=payment_status,
        due_date=due_date,
    )
    db.add(entry)
    return entry
