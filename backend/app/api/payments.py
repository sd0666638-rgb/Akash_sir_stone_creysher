from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import get_current_user, require_roles
from app.models.enums import ChequeStatus, PaymentRecordStatus
from app.models.payment import Payment
from app.models.user import User
from app.schemas.payment import PaymentAllocate, PaymentCreate, PaymentOut, PaymentReverse
from app.services.company_settings import load_company_settings
from app.services.documents import document_filename, receipt_pdf
from app.services.payment_service import (
    allocate_payment,
    receive_payment,
    reverse_payment,
    update_cheque_status,
)

router = APIRouter(prefix="/payments", tags=["Payments"])


class ChequeStatusUpdate(BaseModel):
    cheque_status: ChequeStatus
    bounce_charges: Decimal = Field(default=Decimal("0"), ge=0)
    notes: str | None = None


@router.post("", response_model=PaymentOut)
def post_payment(
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("Admin", "Manager", "Accountant", "Operator")),
) -> Payment:
    return receive_payment(db, payload, user)


@router.get("", response_model=list[PaymentOut])
def list_payments(
    customer_id: int | None = None,
    receipt_number: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[Payment]:
    stmt = select(Payment).order_by(desc(Payment.payment_date), desc(Payment.id))
    if customer_id:
        stmt = stmt.where(Payment.customer_id == customer_id)
    if receipt_number:
        stmt = stmt.where(Payment.receipt_number.like(f"%{receipt_number}%"))
    return list(db.scalars(stmt).all())


@router.get("/unallocated", response_model=list[PaymentOut])
def unallocated_payments(
    customer_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[Payment]:
    stmt = select(Payment).where(
        Payment.unallocated_amount > 0,
        Payment.payment_status.in_(
            [PaymentRecordStatus.SUCCESSFUL, PaymentRecordStatus.PENDING]
        ),
    )
    if customer_id:
        stmt = stmt.where(Payment.customer_id == customer_id)
    return list(db.scalars(stmt.order_by(desc(Payment.payment_date))).all())


@router.get("/{payment_id}", response_model=PaymentOut)
def get_payment(payment_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> Payment:
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    return payment


@router.post("/{payment_id}/allocate", response_model=PaymentOut)
def allocate(
    payment_id: int,
    payload: PaymentAllocate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("Admin", "Manager", "Accountant")),
) -> Payment:
    return allocate_payment(db, payment_id, payload, user)


@router.post("/{payment_id}/reverse", response_model=PaymentOut)
def reverse(
    payment_id: int,
    payload: PaymentReverse,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("Admin", "Accountant")),
) -> Payment:
    return reverse_payment(
        db, payment_id=payment_id, reversal_date=payload.reversal_date, reason=payload.reason, user=user
    )


@router.post("/{payment_id}/cheque-status", response_model=PaymentOut)
def cheque_status(
    payment_id: int,
    payload: ChequeStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("Admin", "Accountant")),
) -> Payment:
    return update_cheque_status(
        db,
        payment_id=payment_id,
        cheque_status=payload.cheque_status,
        bounce_charges=payload.bounce_charges,
        notes=payload.notes,
        user=user,
    )


@router.get("/{payment_id}/receipt")
def receipt(payment_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> Response:
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    company = load_company_settings(db)
    content = receipt_pdf(payment, company)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{document_filename(payment.payment_date, company=company)}"'
            )
        },
    )
