from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.customers import create_customer, list_customers, update_customer
from app.models import Base
from app.models.customer import Customer
from app.schemas.customer import CustomerCreate, CustomerOut, CustomerUpdate


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False, future=True) as session:
        yield session
    engine.dispose()


def test_customer_create_requires_and_normalizes_mobile_while_legacy_output_allows_null(
    db: Session,
):
    with pytest.raises(ValidationError):
        CustomerCreate(name="Missing Mobile")
    with pytest.raises(ValidationError, match="10-digit"):
        CustomerCreate(name="Invalid Mobile", mobile_number="12345")

    payload = CustomerCreate(
        name="Normalized Mobile",
        mobile_number="+91 (98765) 43210",
    )
    assert payload.mobile_number == "9876543210"

    legacy = Customer(name="Legacy Customer", mobile_number=None)
    db.add(legacy)
    db.commit()
    assert CustomerOut.model_validate(legacy).mobile_number is None

    updated = update_customer(
        legacy.id,
        CustomerUpdate(name="Legacy Customer Updated"),
        db=db,
        user=None,
    )
    assert updated.mobile_number is None


def test_duplicate_normalized_mobile_is_rejected_on_create_and_update(db: Session):
    first = create_customer(
        CustomerCreate(
            name="First Customer",
            mobile_number="+91 98765 43210",
        ),
        db=db,
        user=None,
    )

    with pytest.raises(HTTPException, match="already exists") as duplicate_create:
        create_customer(
            CustomerCreate(
                name="Duplicate Customer",
                mobile_number="98765-43210",
            ),
            db=db,
            user=None,
        )
    assert duplicate_create.value.status_code == 409

    second = create_customer(
        CustomerCreate(
            name="Second Customer",
            mobile_number="9123456780",
        ),
        db=db,
        user=None,
    )
    with pytest.raises(HTTPException, match="already exists") as duplicate_update:
        update_customer(
            second.id,
            CustomerUpdate(mobile_number="09876543210"),
            db=db,
            user=None,
        )
    assert duplicate_update.value.status_code == 409
    assert first.mobile_number == "9876543210"
    assert second.mobile_number == "9123456780"


def test_customer_search_uses_name_or_mobile_exact_mobile_first_and_limit(
    db: Session,
):
    customers = [
        Customer(
            name="9876543210 Supplies",
            mobile_number="9000000001",
            opening_balance=Decimal("0"),
        ),
        Customer(
            name="Zed Exact",
            mobile_number="9876543210",
            opening_balance=Decimal("0"),
        ),
        Customer(
            name="Alpha Stone",
            mobile_number="9000000002",
            city="9876543210",
            opening_balance=Decimal("0"),
        ),
    ]
    db.add_all(customers)
    db.commit()

    results = list_customers(
        q="+91 98765 43210",
        limit=50,
        db=db,
        _=None,
    )
    assert [customer.name for customer in results] == [
        "Zed Exact",
        "9876543210 Supplies",
    ]

    name_results = list_customers(
        q="stone",
        limit=50,
        db=db,
        _=None,
    )
    assert [customer.name for customer in name_results] == ["Alpha Stone"]

    limited = list_customers(q=None, limit=2, db=db, _=None)
    assert len(limited) == 2
