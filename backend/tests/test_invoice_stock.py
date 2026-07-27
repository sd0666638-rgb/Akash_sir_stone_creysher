from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.invoices import cancel_invoice
from app.models import Base
from app.models.customer import Customer
from app.models.enums import InvoicePaymentStatus, StockMovementType
from app.models.invoice import Invoice, InvoiceItem
from app.models.material import Material, StockMovement
from app.schemas.invoice import InvoiceCreate, InvoiceItemCreate
from app.services.invoice_service import create_invoice


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


def _seed_customer_and_material(
    db: Session,
    *,
    stock_quantity: Decimal,
) -> tuple[Customer, Material]:
    customer = Customer(
        name="Test Customer",
        opening_balance=Decimal("0"),
        credit_limit=Decimal("0"),
        credit_period_days=0,
        current_outstanding_balance=Decimal("0"),
        advance_balance=Decimal("0"),
        is_active=True,
    )
    material = Material(
        name="M-Sand",
        unit="TON",
        selling_rate=Decimal("100"),
        purchase_rate=Decimal("80"),
        gst_percentage=Decimal("5"),
        stock_quantity=stock_quantity,
        minimum_stock=Decimal("0"),
        is_active=True,
    )
    db.add_all([customer, material])
    db.commit()
    return customer, material


def _invoice_payload(
    customer_id: int,
    material_id: int,
    *quantities: Decimal,
) -> InvoiceCreate:
    return InvoiceCreate(
        invoice_date=date(2026, 7, 27),
        customer_id=customer_id,
        items=[
            InvoiceItemCreate(
                material_id=material_id,
                material_name="M-Sand",
                quantity=quantity,
                unit="TON",
                rate=Decimal("100"),
                gst_percentage=Decimal("5"),
            )
            for quantity in quantities
        ],
    )


def test_invoice_creation_decrements_stock_and_records_one_out_movement(db: Session):
    customer, material = _seed_customer_and_material(
        db,
        stock_quantity=Decimal("10.000"),
    )

    invoice = create_invoice(
        db,
        _invoice_payload(customer.id, material.id, Decimal("4.000")),
        user=None,
    )

    db.refresh(material)
    movements = list(
        db.scalars(
            select(StockMovement).where(StockMovement.material_id == material.id)
        ).all()
    )
    assert material.stock_quantity == Decimal("6.000")
    assert len(movements) == 1
    assert movements[0].movement_type == StockMovementType.OUT
    assert movements[0].quantity == Decimal("4.000")
    assert movements[0].reference_number == invoice.invoice_number


def test_duplicate_invoice_lines_are_aggregated_into_one_stock_movement(db: Session):
    customer, material = _seed_customer_and_material(
        db,
        stock_quantity=Decimal("10.000"),
    )

    invoice = create_invoice(
        db,
        _invoice_payload(
            customer.id,
            material.id,
            Decimal("2.000"),
            Decimal("3.000"),
        ),
        user=None,
    )

    db.refresh(material)
    movements = list(
        db.scalars(
            select(StockMovement).where(
                StockMovement.reference_number == invoice.invoice_number
            )
        ).all()
    )
    assert material.stock_quantity == Decimal("5.000")
    assert len(movements) == 1
    assert movements[0].quantity == Decimal("5.000")


def test_duplicate_invoice_lines_use_aggregate_quantity_for_stock_check(db: Session):
    customer, material = _seed_customer_and_material(
        db,
        stock_quantity=Decimal("5.000"),
    )

    with pytest.raises(HTTPException) as error:
        create_invoice(
            db,
            _invoice_payload(
                customer.id,
                material.id,
                Decimal("3.000"),
                Decimal("3.000"),
            ),
            user=None,
        )

    assert error.value.status_code == 409
    assert "requested 6.000 TON, available 5.000 TON" in error.value.detail
    assert material.stock_quantity == Decimal("5.000")
    assert not list(db.scalars(select(StockMovement)).all())


def test_invoice_cancellation_restores_deducted_stock_once(db: Session):
    customer, material = _seed_customer_and_material(
        db,
        stock_quantity=Decimal("10.000"),
    )
    invoice = create_invoice(
        db,
        _invoice_payload(customer.id, material.id, Decimal("4.000")),
        user=None,
    )

    cancelled = cancel_invoice(invoice.id, db=db, user=None)

    db.refresh(material)
    movements = list(
        db.scalars(
            select(StockMovement)
            .where(StockMovement.material_id == material.id)
            .order_by(StockMovement.id)
        ).all()
    )
    assert cancelled.payment_status == InvoicePaymentStatus.CANCELLED
    assert material.stock_quantity == Decimal("10.000")
    assert [movement.movement_type for movement in movements] == [
        StockMovementType.OUT,
        StockMovementType.IN,
    ]
    assert movements[1].quantity == Decimal("4.000")
    assert movements[1].reference_number == f"{invoice.invoice_number}-CANCEL"


def test_legacy_invoice_cancellation_does_not_add_untracked_stock(db: Session):
    customer, material = _seed_customer_and_material(
        db,
        stock_quantity=Decimal("5.000"),
    )
    legacy_invoice = Invoice(
        invoice_number="INV-LEGACY-000001",
        invoice_date=date(2025, 1, 1),
        customer_id=customer.id,
        subtotal=Decimal("400"),
        taxable_amount=Decimal("400"),
        grand_total=Decimal("420"),
        remaining_amount=Decimal("420"),
        payment_status=InvoicePaymentStatus.UNPAID,
    )
    legacy_invoice.items.append(
        InvoiceItem(
            material_id=material.id,
            material_name=material.name,
            quantity=Decimal("4.000"),
            unit=material.unit,
            rate=Decimal("100"),
            gst_percentage=Decimal("5"),
        )
    )
    db.add(legacy_invoice)
    db.commit()

    cancel_invoice(legacy_invoice.id, db=db, user=None)

    db.refresh(material)
    assert material.stock_quantity == Decimal("5.000")
    assert not list(db.scalars(select(StockMovement)).all())
