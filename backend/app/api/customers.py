from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import get_current_user, require_roles
from app.models.customer import Customer
from app.models.payment import CustomerAdvance, CustomerLedger
from app.models.user import User
from app.schemas.customer import CustomerCreate, CustomerOut, CustomerOutstanding, CustomerUpdate
from app.schemas.payment import AdvanceOut, CustomerLedgerOut
from app.services.accounting import refresh_customer_balances
from app.services.audit import write_audit
from app.utils.phone import mobile_search_digits

router = APIRouter(prefix="/customers", tags=["Customers"])


def _duplicate_mobile_conflict(mobile_number: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"A customer with mobile number {mobile_number} already exists",
    )


def _mobile_is_registered(
    db: Session,
    mobile_number: str,
    *,
    exclude_customer_id: int | None = None,
) -> bool:
    stmt = select(Customer.id).where(Customer.mobile_number == mobile_number)
    if exclude_customer_id is not None:
        stmt = stmt.where(Customer.id != exclude_customer_id)
    return db.scalar(stmt.limit(1)) is not None


@router.get("", response_model=list[CustomerOut])
def list_customers(
    q: str | None = Query(default=None, max_length=180),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[Customer]:
    stmt = select(Customer)
    query = (q or "").strip()
    if query:
        mobile_query = mobile_search_digits(query)
        conditions = [Customer.name.like(f"%{query}%")]
        if mobile_query:
            conditions.append(Customer.mobile_number.like(f"%{mobile_query}%"))
            if mobile_query != query:
                conditions.append(Customer.name.like(f"%{mobile_query}%"))
        stmt = stmt.where(or_(*conditions))
        if mobile_query:
            stmt = stmt.order_by(
                case(
                    (Customer.mobile_number == mobile_query, 0),
                    else_=1,
                ),
                Customer.name,
                Customer.id,
            )
        else:
            stmt = stmt.order_by(Customer.name, Customer.id)
    else:
        stmt = stmt.order_by(Customer.name, Customer.id)
    return list(db.scalars(stmt.limit(limit)).all())


@router.post("", response_model=CustomerOut)
def create_customer(
    payload: CustomerCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("Admin", "Manager", "Operator")),
) -> Customer:
    if _mobile_is_registered(db, payload.mobile_number):
        raise _duplicate_mobile_conflict(payload.mobile_number)

    customer = Customer(**payload.model_dump())
    customer.current_outstanding_balance = max(payload.opening_balance, Decimal("0"))
    try:
        db.add(customer)
        db.flush()
        write_audit(
            db,
            user=user,
            action="create",
            module="customer",
            record_id=customer.id,
            new_value=payload.model_dump(mode="json"),
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _duplicate_mobile_conflict(payload.mobile_number) from exc
    db.refresh(customer)
    return customer


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> Customer:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return customer


@router.put("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: int,
    payload: CustomerUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("Admin", "Manager")),
) -> Customer:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    previous = CustomerOut.model_validate(customer).model_dump(mode="json")
    changes = payload.model_dump(exclude_unset=True)
    mobile_number = changes.get("mobile_number")
    if mobile_number and _mobile_is_registered(
        db,
        mobile_number,
        exclude_customer_id=customer.id,
    ):
        raise _duplicate_mobile_conflict(mobile_number)

    for key, value in changes.items():
        setattr(customer, key, value)
    try:
        db.flush()
        refresh_customer_balances(db, customer.id)
        write_audit(
            db,
            user=user,
            action="update",
            module="customer",
            record_id=customer.id,
            previous_value=previous,
            new_value=payload.model_dump(exclude_unset=True, mode="json"),
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if mobile_number:
            raise _duplicate_mobile_conflict(mobile_number) from exc
        raise
    db.refresh(customer)
    return customer


@router.delete("/{customer_id}", response_model=CustomerOut)
def deactivate_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("Admin", "Manager")),
) -> Customer:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    customer.is_active = False
    write_audit(db, user=user, action="deactivate", module="customer", record_id=customer.id)
    db.commit()
    db.refresh(customer)
    return customer


@router.get("/{customer_id}/ledger", response_model=list[CustomerLedgerOut])
def customer_ledger(
    customer_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> list[CustomerLedger]:
    return list(
        db.scalars(
            select(CustomerLedger)
            .where(CustomerLedger.customer_id == customer_id)
            .order_by(CustomerLedger.transaction_date, CustomerLedger.id)
        ).all()
    )


@router.get("/{customer_id}/outstanding", response_model=CustomerOutstanding)
def customer_outstanding(
    customer_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> CustomerOutstanding:
    customer = refresh_customer_balances(db, customer_id)
    return CustomerOutstanding(
        customer_id=customer.id,
        outstanding_amount=customer.current_outstanding_balance,
        advance_balance=customer.advance_balance,
        # current_outstanding_balance is already net of customer advances.
        net_outstanding=customer.current_outstanding_balance,
    )


@router.get("/{customer_id}/advances", response_model=list[AdvanceOut])
def customer_advances(
    customer_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> list[CustomerAdvance]:
    return list(
        db.scalars(
            select(CustomerAdvance)
            .where(CustomerAdvance.customer_id == customer_id)
            .order_by(CustomerAdvance.advance_date.desc())
        ).all()
    )


@router.post("/{customer_id}/payment-reminder")
def send_payment_reminder(
    customer_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles("Admin", "Manager", "Accountant"))
) -> dict[str, str]:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    write_audit(db, user=user, action="payment_reminder", module="customer", record_id=customer.id)
    db.commit()
    return {"message": "Payment reminder logged for follow-up"}
