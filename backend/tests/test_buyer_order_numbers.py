from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.api.invoices import next_buyer_order_number
from app.models import Base
from app.models.customer import Customer
from app.models.invoice import BuyerOrderSequence
from app.schemas.invoice import InvoiceCreate, InvoiceItemCreate
from app.services.invoice_service import (
    create_invoice,
    preview_buyer_order_number,
    reserve_buyer_order_number,
)


INVOICE_DATE = date(2026, 6, 27)


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False, future=True) as session:
        yield session
    engine.dispose()


def _invoice_payload(
    customer_id: int,
    *,
    invoice_date: date = INVOICE_DATE,
    buyer_order_number: str | None = None,
) -> InvoiceCreate:
    return InvoiceCreate(
        invoice_date=invoice_date,
        customer_id=customer_id,
        buyer_order_number=buyer_order_number,
        items=[
            InvoiceItemCreate(
                material_name="Crusher Sand",
                quantity=Decimal("1.000"),
                rate=Decimal("100.00"),
            )
        ],
    )


def test_preview_is_read_only_and_endpoint_shape_is_stable(db: Session):
    assert preview_buyer_order_number(db, INVOICE_DATE) == "1-27062026"
    assert db.scalar(select(func.count(BuyerOrderSequence.sequence_date))) == 0

    response = next_buyer_order_number(
        invoice_date=INVOICE_DATE,
        db=db,
        _=None,
    )
    assert response.model_dump() == {
        "buyer_order_number": "1-27062026",
    }
    assert db.scalar(select(func.count(BuyerOrderSequence.sequence_date))) == 0


def test_invoice_creation_generates_daily_sequence_and_respects_manual_values(
    db: Session,
):
    customer = Customer(
        name="Buyer Order Customer",
        mobile_number="9876543210",
    )
    db.add(customer)
    db.commit()

    first = create_invoice(
        db,
        _invoice_payload(customer.id),
        user=None,
    )
    second = create_invoice(
        db,
        _invoice_payload(customer.id, buyer_order_number="   "),
        user=None,
    )
    manual = create_invoice(
        db,
        _invoice_payload(
            customer.id,
            buyer_order_number="  10-27062026  ",
        ),
        user=None,
    )
    after_manual = create_invoice(
        db,
        _invoice_payload(customer.id),
        user=None,
    )
    next_day = create_invoice(
        db,
        _invoice_payload(
            customer.id,
            invoice_date=date(2026, 6, 28),
        ),
        user=None,
    )

    assert first.buyer_order_number == "1-27062026"
    assert second.buyer_order_number == "2-27062026"
    assert manual.buyer_order_number == "10-27062026"
    assert after_manual.buyer_order_number == "11-27062026"
    assert next_day.buyer_order_number == "1-28062026"


def test_daily_sequence_reservation_is_atomic_across_sessions(tmp_path):
    database_path = tmp_path / "buyer-order-sequence.db"
    engine = create_engine(
        f"sqlite+pysqlite:///{database_path}",
        connect_args={"check_same_thread": False, "timeout": 30},
        future=True,
    )
    BuyerOrderSequence.__table__.create(engine)

    def reserve() -> str:
        with Session(engine, future=True) as session:
            buyer_order_number = reserve_buyer_order_number(
                session,
                INVOICE_DATE,
            )
            session.commit()
            return buyer_order_number

    with ThreadPoolExecutor(max_workers=8) as executor:
        numbers = list(executor.map(lambda _: reserve(), range(12)))

    sequence_numbers = sorted(
        int(buyer_order_number.split("-", 1)[0])
        for buyer_order_number in numbers
    )
    assert sequence_numbers == list(range(1, 13))
    assert len(set(numbers)) == 12
    engine.dispose()
