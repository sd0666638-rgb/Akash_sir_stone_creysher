from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.reports import visual_analytics
from app.models import Base
from app.models.customer import Customer
from app.models.enums import (
    InvoicePaymentStatus,
    LedgerTransactionType,
    PaymentMethod,
    PaymentRecordStatus,
)
from app.models.invoice import Invoice, InvoiceItem
from app.models.payment import CustomerLedger, Payment
from app.services.reports_service import analytics_report


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False, future=True) as session:
        yield session
    engine.dispose()


def test_analytics_report_builds_continuous_business_trends(db: Session):
    established_customer = Customer(
        name="Established Customer",
        mobile_number="9000000001",
        opening_balance=Decimal("100"),
        created_at=datetime(2025, 12, 31, tzinfo=timezone.utc),
    )
    new_customer = Customer(
        name="New Customer",
        mobile_number="9000000002",
        opening_balance=Decimal("0"),
        created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    db.add_all([established_customer, new_customer])
    db.flush()

    first_invoice = Invoice(
        invoice_number="INV-1",
        invoice_date=date(2026, 1, 1),
        customer_id=established_customer.id,
        grand_total=Decimal("1000"),
        remaining_amount=Decimal("700"),
        payment_status=InvoicePaymentStatus.PARTIALLY_PAID,
    )
    second_invoice = Invoice(
        invoice_number="INV-2",
        invoice_date=date(2026, 1, 3),
        customer_id=new_customer.id,
        grand_total=Decimal("500"),
        advance_adjusted=Decimal("50"),
        remaining_amount=Decimal("450"),
        payment_status=InvoicePaymentStatus.PARTIALLY_PAID,
    )
    cancelled_invoice = Invoice(
        invoice_number="INV-CANCELLED",
        invoice_date=date(2026, 1, 1),
        customer_id=established_customer.id,
        grand_total=Decimal("900"),
        remaining_amount=Decimal("0"),
        payment_status=InvoicePaymentStatus.CANCELLED,
    )
    db.add_all([first_invoice, second_invoice, cancelled_invoice])
    db.flush()
    db.add_all(
        [
            InvoiceItem(
                invoice_id=first_invoice.id,
                material_name="Stone",
                quantity=Decimal("2"),
                unit="TON",
                rate=Decimal("500"),
                line_total=Decimal("1000"),
            ),
            InvoiceItem(
                invoice_id=second_invoice.id,
                material_name="Gravel",
                quantity=Decimal("1"),
                unit="TON",
                rate=Decimal("500"),
                line_total=Decimal("500"),
            ),
            InvoiceItem(
                invoice_id=cancelled_invoice.id,
                material_name="Cancelled material",
                quantity=Decimal("1"),
                unit="TON",
                rate=Decimal("900"),
                line_total=Decimal("900"),
            ),
        ]
    )
    db.add_all(
        [
            Payment(
                receipt_number="RCT-1",
                customer_id=established_customer.id,
                payment_date=date(2026, 1, 2),
                total_amount=Decimal("300"),
                payment_method=PaymentMethod.CASH,
                payment_status=PaymentRecordStatus.SUCCESSFUL,
            ),
            Payment(
                receipt_number="RCT-ADVANCE",
                customer_id=new_customer.id,
                payment_date=date(2026, 1, 2),
                total_amount=Decimal("50"),
                payment_method=PaymentMethod.CASH,
                payment_status=PaymentRecordStatus.SUCCESSFUL,
            ),
        ]
    )
    db.add_all(
        [
            CustomerLedger(
                customer_id=established_customer.id,
                transaction_date=date(2026, 1, 1),
                transaction_type=LedgerTransactionType.INVOICE,
                reference_number="INV-1",
                debit=Decimal("1000"),
                credit=Decimal("0"),
                running_balance=Decimal("1100"),
            ),
            CustomerLedger(
                customer_id=established_customer.id,
                transaction_date=date(2026, 1, 2),
                transaction_type=LedgerTransactionType.PAYMENT,
                reference_number="RCT-1",
                debit=Decimal("0"),
                credit=Decimal("300"),
                running_balance=Decimal("800"),
            ),
            CustomerLedger(
                customer_id=new_customer.id,
                transaction_date=date(2026, 1, 2),
                transaction_type=LedgerTransactionType.ADVANCE_PAYMENT,
                reference_number="RCT-ADVANCE",
                debit=Decimal("0"),
                credit=Decimal("50"),
                running_balance=Decimal("-50"),
            ),
            CustomerLedger(
                customer_id=new_customer.id,
                transaction_date=date(2026, 1, 3),
                transaction_type=LedgerTransactionType.INVOICE,
                reference_number="INV-2",
                debit=Decimal("500"),
                credit=Decimal("0"),
                running_balance=Decimal("550"),
            ),
            CustomerLedger(
                customer_id=new_customer.id,
                transaction_date=date(2026, 1, 3),
                transaction_type=LedgerTransactionType.ADVANCE_ADJUSTMENT,
                reference_number="INV-2",
                debit=Decimal("0"),
                credit=Decimal("50"),
                running_balance=Decimal("500"),
            ),
        ]
    )
    db.commit()

    report = analytics_report(db, date(2026, 1, 1), date(2026, 1, 3))

    assert report["summary"] == {
        "total_sales": Decimal("1500.00"),
        "total_collections": Decimal("350.00"),
        "invoice_count": 2,
        "new_customers": 1,
        "customers_served": 2,
        "current_outstanding": Decimal("1250.00"),
    }
    assert [point["date"] for point in report["daily"]] == [
        date(2026, 1, 1),
        date(2026, 1, 2),
        date(2026, 1, 3),
    ]
    assert [point["outstanding"] for point in report["daily"]] == [
        Decimal("1100.00"),
        Decimal("800.00"),
        Decimal("1250.00"),
    ]
    assert [point["new_customers"] for point in report["daily"]] == [0, 1, 0]
    assert [row["material"] for row in report["top_materials"]] == ["Stone", "Gravel"]


def test_visual_analytics_endpoint_uses_requested_period(db: Session):
    response = visual_analytics(
        days=7,
        as_of=date(2026, 2, 10),
        db=db,
        _=None,
    )

    assert response["start_date"] == date(2026, 2, 4)
    assert response["end_date"] == date(2026, 2, 10)
    assert len(response["daily"]) == 7
    assert response["summary"]["total_sales"] == Decimal("0.00")
