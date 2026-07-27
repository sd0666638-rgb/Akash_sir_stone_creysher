from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import get_current_user, require_roles
from app.models.payment import CustomerAdvance
from app.models.user import User
from app.schemas.payment import AdvanceAdjust, AdvanceCreate, AdvanceOut
from app.services.payment_service import adjust_customer_advance, create_customer_advance

router = APIRouter(prefix="/advances", tags=["Advances"])


@router.post("", response_model=AdvanceOut)
def create_advance(
    payload: AdvanceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("Admin", "Manager", "Accountant", "Operator")),
) -> CustomerAdvance:
    return create_customer_advance(
        db,
        customer_id=payload.customer_id,
        advance_date=payload.advance_date,
        amount=payload.amount,
        payment_method=payload.payment_method,
        notes=payload.notes,
        user=user,
    )


@router.get("/customer/{customer_id}", response_model=list[AdvanceOut])
def get_advances(
    customer_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[CustomerAdvance]:
    return list(
        db.scalars(
            select(CustomerAdvance)
            .where(CustomerAdvance.customer_id == customer_id)
            .order_by(CustomerAdvance.advance_date.desc())
        ).all()
    )


@router.post("/{advance_id}/adjust")
def adjust_advance(
    advance_id: int,
    payload: AdvanceAdjust,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("Admin", "Manager", "Accountant")),
) -> dict[str, str]:
    advance = db.get(CustomerAdvance, advance_id)
    if advance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Advance not found")
    adjust_customer_advance(
        db,
        customer_id=advance.customer_id,
        invoice_id=payload.invoice_id,
        adjustment_date=payload.adjustment_date,
        amount=payload.amount,
        user=user,
    )
    return {"message": "Advance adjusted"}
