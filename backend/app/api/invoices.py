from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import get_current_user, require_roles
from app.models.enums import InvoicePaymentStatus, LedgerTransactionType, PaymentRecordStatus
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.user import User
from app.schemas.invoice import (
    BuyerOrderNumberPreview,
    InvoiceCreate,
    InvoiceOut,
    InvoiceOutstanding,
    InvoiceUpdate,
)
from app.schemas.payment import PaymentOut
from app.services.accounting import refresh_customer_balances, refresh_invoice_payment_state
from app.services.audit import write_audit
from app.services.company_settings import load_company_settings
from app.services.documents import document_filename, invoice_pdf
from app.services.invoice_service import (
    create_invoice,
    preview_buyer_order_number,
    restore_invoice_stock,
)
from app.services.ledger_service import append_ledger_entry

router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.post("", response_model=InvoiceOut)
def post_invoice(
    payload: InvoiceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("Admin", "Manager", "Operator")),
) -> Invoice:
    return create_invoice(db, payload, user)


@router.get("", response_model=list[InvoiceOut])
def list_invoices(
    status_filter: InvoicePaymentStatus | None = Query(default=None, alias="status"),
    customer_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[Invoice]:
    stmt = select(Invoice).order_by(desc(Invoice.invoice_date), desc(Invoice.id))
    if status_filter:
        stmt = stmt.where(Invoice.payment_status == status_filter)
    if customer_id:
        stmt = stmt.where(Invoice.customer_id == customer_id)
    invoices = list(db.scalars(stmt).all())
    for invoice in invoices:
        refresh_invoice_payment_state(db, invoice)
    return invoices


@router.get(
    "/next-buyer-order-number",
    response_model=BuyerOrderNumberPreview,
)
def next_buyer_order_number(
    invoice_date: date,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> BuyerOrderNumberPreview:
    return BuyerOrderNumberPreview(
        buyer_order_number=preview_buyer_order_number(db, invoice_date)
    )


@router.get("/{invoice_id}", response_model=InvoiceOut)
def get_invoice(invoice_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> Invoice:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    refresh_invoice_payment_state(db, invoice)
    return invoice


@router.put("/{invoice_id}", response_model=InvoiceOut)
def update_invoice(
    invoice_id: int,
    payload: InvoiceUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("Admin", "Manager")),
) -> Invoice:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    if invoice.payment_status == InvoicePaymentStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="Cancelled invoice cannot be updated")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(invoice, key, value)
    write_audit(
        db,
        user=user,
        action="update",
        module="invoice",
        record_id=invoice.id,
        new_value=payload.model_dump(exclude_unset=True, mode="json"),
    )
    db.commit()
    db.refresh(invoice)
    return invoice


@router.delete("/{invoice_id}", response_model=InvoiceOut)
def delete_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("Admin", "Manager")),
) -> Invoice:
    return cancel_invoice(invoice_id, db, user)


@router.post("/{invoice_id}/cancel", response_model=InvoiceOut)
def cancel_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("Admin", "Manager")),
) -> Invoice:
    invoice = db.scalar(
        select(Invoice).where(Invoice.id == invoice_id).with_for_update()
    )
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    if invoice.payment_status == InvoicePaymentStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="Invoice is already cancelled")

    refresh_invoice_payment_state(db, invoice)
    active_allocations = any(
        allocation.payment.payment_status
        not in {
            PaymentRecordStatus.REVERSED,
            PaymentRecordStatus.CANCELLED,
            PaymentRecordStatus.BOUNCED,
        }
        for allocation in invoice.allocations
    )
    if active_allocations or invoice.advance_adjusted > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Reverse payments and advance adjustments before cancelling this invoice",
        )

    invoice.payment_status = InvoicePaymentStatus.CANCELLED
    invoice.remaining_amount = 0
    restore_invoice_stock(db, invoice=invoice, user=user)
    append_ledger_entry(
        db,
        customer_id=invoice.customer_id,
        transaction_date=date.today(),
        transaction_type=LedgerTransactionType.CREDIT_NOTE,
        reference_number=f"{invoice.invoice_number}-CANCEL",
        description="Invoice cancelled",
        credit=invoice.grand_total,
        payment_status=InvoicePaymentStatus.CANCELLED.value,
    )
    write_audit(db, user=user, action="cancel", module="invoice", record_id=invoice.id)
    refresh_customer_balances(db, invoice.customer_id)
    db.commit()
    db.refresh(invoice)
    return invoice


@router.get("/{invoice_id}/payments", response_model=list[PaymentOut])
def invoice_payments(
    invoice_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> list[Payment]:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return [allocation.payment for allocation in invoice.allocations]


@router.get("/{invoice_id}/outstanding", response_model=InvoiceOutstanding)
def invoice_outstanding(
    invoice_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> InvoiceOutstanding:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    refresh_invoice_payment_state(db, invoice)
    return InvoiceOutstanding(
        invoice_id=invoice.id,
        invoice_number=invoice.invoice_number,
        grand_total=invoice.grand_total,
        total_paid=invoice.total_paid,
        advance_adjusted=invoice.advance_adjusted,
        remaining_amount=invoice.remaining_amount,
        payment_status=invoice.payment_status,
    )


@router.get("/{invoice_id}/pdf")
def download_invoice_pdf(
    invoice_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
) -> Response:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    company = load_company_settings(db)
    content = invoice_pdf(invoice, company)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{document_filename(invoice.invoice_date, company=company)}"'
            )
        },
    )
