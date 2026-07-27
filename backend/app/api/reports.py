from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

from fastapi import APIRouter, Depends, Query, Response
from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import get_current_user
from app.models.customer import Customer
from app.models.enums import InvoicePaymentStatus, PaymentMethod, PaymentRecordStatus
from app.models.invoice import Invoice, InvoiceItem
from app.models.payment import Payment
from app.models.user import User
from app.schemas.report import AnalyticsReport, DashboardSummary
from app.services.calculations import money
from app.services.reports_service import ageing_report, analytics_report, dashboard_summary

router = APIRouter(tags=["Reports"])


@router.get("/dashboard", response_model=DashboardSummary)
def dashboard(
    as_of: date = Query(default_factory=date.today),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return dashboard_summary(db, as_of)


@router.get("/reports/analytics", response_model=AnalyticsReport)
def visual_analytics(
    days: int = Query(default=30, ge=7, le=365),
    as_of: date = Query(default_factory=date.today),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    start_date = as_of - timedelta(days=days - 1)
    return analytics_report(db, start_date, as_of)


@router.get("/reports/sales")
def sales_report(
    start_date: date | None = None,
    end_date: date | None = None,
    customer_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict]:
    stmt = select(Invoice)
    if start_date:
        stmt = stmt.where(Invoice.invoice_date >= start_date)
    if end_date:
        stmt = stmt.where(Invoice.invoice_date <= end_date)
    if customer_id:
        stmt = stmt.where(Invoice.customer_id == customer_id)
    invoices = db.scalars(stmt.order_by(Invoice.invoice_date.desc())).all()
    return [
        {
            "invoice_number": invoice.invoice_number,
            "invoice_date": invoice.invoice_date,
            "customer": invoice.customer.name,
            "vehicle_number": invoice.vehicle_number,
            "grand_total": invoice.grand_total,
            "payment_status": invoice.payment_status.value,
        }
        for invoice in invoices
    ]


@router.get("/reports/payments")
def payments_report(
    start_date: date | None = None,
    end_date: date | None = None,
    payment_method: PaymentMethod | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict]:
    stmt = select(Payment)
    if start_date:
        stmt = stmt.where(Payment.payment_date >= start_date)
    if end_date:
        stmt = stmt.where(Payment.payment_date <= end_date)
    if payment_method:
        stmt = stmt.where(Payment.payment_method == payment_method)
    payments = db.scalars(stmt.order_by(Payment.payment_date.desc())).all()
    return [
        {
            "receipt_number": payment.receipt_number,
            "payment_date": payment.payment_date,
            "customer": payment.customer.name,
            "amount": payment.total_amount,
            "method": payment.payment_method.value,
            "status": payment.payment_status.value,
        }
        for payment in payments
    ]


@router.get("/reports/partial-payments")
def partial_payment_report(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[dict]:
    invoices = db.scalars(
        select(Invoice).where(Invoice.payment_status == InvoicePaymentStatus.PARTIALLY_PAID)
    ).all()
    return [
        {
            "invoice_number": invoice.invoice_number,
            "customer": invoice.customer.name,
            "grand_total": invoice.grand_total,
            "total_paid": invoice.total_paid,
            "remaining_amount": invoice.remaining_amount,
        }
        for invoice in invoices
    ]


@router.get("/reports/outstanding", response_model=None)
def outstanding_report(
    export: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict] | Response:
    customers = db.scalars(select(Customer).order_by(Customer.name)).all()
    rows = [
        {
            "customer": customer.name,
            "mobile": customer.mobile_number,
            "outstanding": customer.current_outstanding_balance,
            "advance": customer.advance_balance,
            "credit_limit": customer.credit_limit,
        }
        for customer in customers
        if customer.current_outstanding_balance > 0 or customer.advance_balance > 0
    ]
    if export == "excel":
        return _excel_response("outstanding.xlsx", ["Customer", "Mobile", "Outstanding", "Advance"], rows)
    return rows


@router.get("/reports/ageing", response_model=None)
def get_ageing_report(
    as_of: date = Query(default_factory=date.today),
    export: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict] | Response:
    rows = ageing_report(db, as_of)
    if export == "excel":
        excel_rows = [
            {
                "customer": row["customer_name"],
                "bucket_0_30": row["bucket_0_30"],
                "bucket_31_60": row["bucket_31_60"],
                "bucket_61_90": row["bucket_61_90"],
                "bucket_91_180": row["bucket_91_180"],
                "bucket_over_180": row["bucket_over_180"],
                "total": row["total"],
            }
            for row in rows
        ]
        return _excel_response(
            "ageing.xlsx",
            ["Customer", "0-30", "31-60", "61-90", "91-180", ">180", "Total"],
            excel_rows,
        )
    return rows


@router.get("/reports/advances")
def advance_report(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[dict]:
    customers = db.scalars(select(Customer).where(Customer.advance_balance > 0)).all()
    return [
        {
            "customer": customer.name,
            "advance_balance": customer.advance_balance,
            "mobile": customer.mobile_number,
        }
        for customer in customers
    ]


@router.get("/reports/gst")
def gst_report(
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    stmt = select(Invoice)
    if start_date:
        stmt = stmt.where(Invoice.invoice_date >= start_date)
    if end_date:
        stmt = stmt.where(Invoice.invoice_date <= end_date)
    invoices = db.scalars(stmt).all()
    return {
        "taxable_amount": money(sum((invoice.taxable_amount for invoice in invoices), Decimal("0"))),
        "cgst": money(sum((invoice.cgst_amount for invoice in invoices), Decimal("0"))),
        "sgst": money(sum((invoice.sgst_amount for invoice in invoices), Decimal("0"))),
        "igst": money(sum((invoice.igst_amount for invoice in invoices), Decimal("0"))),
    }


@router.get("/reports/material-sales")
def material_sales_report(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[dict]:
    rows = db.execute(
        select(
            InvoiceItem.material_name,
            func.sum(InvoiceItem.quantity).label("quantity"),
            func.sum(InvoiceItem.line_total).label("total"),
        ).group_by(InvoiceItem.material_name)
    ).all()
    return [{"material": row.material_name, "quantity": row.quantity, "total": row.total} for row in rows]


@router.get("/reports/cheques")
def cheque_report(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[dict]:
    payments = db.scalars(select(Payment).where(Payment.payment_method == PaymentMethod.CHEQUE)).all()
    return [
        {
            "receipt_number": payment.receipt_number,
            "customer": payment.customer.name,
            "cheque_number": payment.cheque_number,
            "bank_name": payment.bank_name,
            "cheque_status": payment.cheque_status.value if payment.cheque_status else None,
            "amount": payment.total_amount,
        }
        for payment in payments
    ]


@router.get("/reports/reversed-payments")
def reversed_payment_report(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[dict]:
    payments = db.scalars(
        select(Payment).where(Payment.payment_status.in_([PaymentRecordStatus.REVERSED, PaymentRecordStatus.BOUNCED]))
    ).all()
    return [
        {
            "receipt_number": payment.receipt_number,
            "customer": payment.customer.name,
            "amount": payment.total_amount,
            "status": payment.payment_status.value,
        }
        for payment in payments
    ]


def _excel_response(filename: str, headers: list[str], rows: list[dict]) -> Response:
    wb = Workbook()
    ws = wb.active
    ws.title = "Report"
    ws.append(headers)
    for row in rows:
        ws.append(list(row.values())[: len(headers)])
    output = BytesIO()
    wb.save(output)
    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
