import csv
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO, StringIO
from typing import Literal

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

ExportFormat = Literal["excel", "csv"]

REPORT_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "sales": [
        ("invoice_number", "Invoice Number"),
        ("invoice_date", "Invoice Date"),
        ("customer", "Customer"),
        ("vehicle_number", "Vehicle Number"),
        ("grand_total", "Grand Total"),
        ("payment_status", "Payment Status"),
    ],
    "payments": [
        ("receipt_number", "Receipt Number"),
        ("payment_date", "Payment Date"),
        ("customer", "Customer"),
        ("amount", "Amount"),
        ("method", "Method"),
        ("status", "Status"),
    ],
    "partial-payments": [
        ("invoice_number", "Invoice Number"),
        ("customer", "Customer"),
        ("grand_total", "Grand Total"),
        ("total_paid", "Total Paid"),
        ("remaining_amount", "Remaining Amount"),
    ],
    "outstanding": [
        ("customer", "Customer"),
        ("mobile", "Mobile"),
        ("outstanding", "Outstanding"),
        ("advance", "Advance"),
        ("credit_limit", "Credit Limit"),
    ],
    "ageing": [
        ("customer_name", "Customer"),
        ("bucket_0_30", "0-30"),
        ("bucket_31_60", "31-60"),
        ("bucket_61_90", "61-90"),
        ("bucket_91_180", "91-180"),
        ("bucket_over_180", ">180"),
        ("total", "Total"),
    ],
    "advances": [
        ("customer", "Customer"),
        ("advance_balance", "Advance Balance"),
        ("mobile", "Mobile"),
    ],
    "gst": [
        ("taxable_amount", "Taxable Amount"),
        ("cgst", "CGST"),
        ("sgst", "SGST"),
        ("igst", "IGST"),
    ],
    "material-sales": [
        ("material", "Material"),
        ("quantity", "Quantity"),
        ("total", "Total"),
    ],
    "cheques": [
        ("receipt_number", "Receipt Number"),
        ("customer", "Customer"),
        ("cheque_number", "Cheque Number"),
        ("bank_name", "Bank Name"),
        ("cheque_status", "Cheque Status"),
        ("amount", "Amount"),
    ],
    "reversed-payments": [
        ("receipt_number", "Receipt Number"),
        ("customer", "Customer"),
        ("amount", "Amount"),
        ("status", "Status"),
    ],
}


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


@router.get("/reports/sales", response_model=None)
def sales_report(
    start_date: date | None = None,
    end_date: date | None = None,
    customer_id: int | None = None,
    export: ExportFormat | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict] | Response:
    stmt = select(Invoice)
    if start_date:
        stmt = stmt.where(Invoice.invoice_date >= start_date)
    if end_date:
        stmt = stmt.where(Invoice.invoice_date <= end_date)
    if customer_id:
        stmt = stmt.where(Invoice.customer_id == customer_id)
    invoices = db.scalars(stmt.order_by(Invoice.invoice_date.desc())).all()
    rows = [
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
    if export:
        return _report_export_response(export, "sales", REPORT_COLUMNS["sales"], rows)
    return rows


@router.get("/reports/payments", response_model=None)
def payments_report(
    start_date: date | None = None,
    end_date: date | None = None,
    payment_method: PaymentMethod | None = None,
    export: ExportFormat | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict] | Response:
    stmt = select(Payment)
    if start_date:
        stmt = stmt.where(Payment.payment_date >= start_date)
    if end_date:
        stmt = stmt.where(Payment.payment_date <= end_date)
    if payment_method:
        stmt = stmt.where(Payment.payment_method == payment_method)
    payments = db.scalars(stmt.order_by(Payment.payment_date.desc())).all()
    rows = [
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
    if export:
        return _report_export_response(export, "collections", REPORT_COLUMNS["payments"], rows)
    return rows


@router.get("/reports/partial-payments", response_model=None)
def partial_payment_report(
    export: ExportFormat | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict] | Response:
    invoices = db.scalars(
        select(Invoice).where(Invoice.payment_status == InvoicePaymentStatus.PARTIALLY_PAID)
    ).all()
    rows = [
        {
            "invoice_number": invoice.invoice_number,
            "customer": invoice.customer.name,
            "grand_total": invoice.grand_total,
            "total_paid": invoice.total_paid,
            "remaining_amount": invoice.remaining_amount,
        }
        for invoice in invoices
    ]
    if export:
        return _report_export_response(
            export,
            "partial-payments",
            REPORT_COLUMNS["partial-payments"],
            rows,
        )
    return rows


@router.get("/reports/outstanding", response_model=None)
def outstanding_report(
    export: ExportFormat | None = None,
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
    if export:
        return _report_export_response(
            export,
            "outstanding",
            REPORT_COLUMNS["outstanding"],
            rows,
        )
    return rows


@router.get("/reports/ageing", response_model=None)
def get_ageing_report(
    as_of: date = Query(default_factory=date.today),
    export: ExportFormat | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict] | Response:
    rows = ageing_report(db, as_of)
    if export:
        return _report_export_response(export, "ageing", REPORT_COLUMNS["ageing"], rows)
    return rows


@router.get("/reports/advances", response_model=None)
def advance_report(
    export: ExportFormat | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict] | Response:
    customers = db.scalars(select(Customer).where(Customer.advance_balance > 0)).all()
    rows = [
        {
            "customer": customer.name,
            "advance_balance": customer.advance_balance,
            "mobile": customer.mobile_number,
        }
        for customer in customers
    ]
    if export:
        return _report_export_response(export, "advances", REPORT_COLUMNS["advances"], rows)
    return rows


@router.get("/reports/gst", response_model=None)
def gst_report(
    start_date: date | None = None,
    end_date: date | None = None,
    export: ExportFormat | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict | Response:
    stmt = select(Invoice)
    if start_date:
        stmt = stmt.where(Invoice.invoice_date >= start_date)
    if end_date:
        stmt = stmt.where(Invoice.invoice_date <= end_date)
    invoices = db.scalars(stmt).all()
    row = {
        "taxable_amount": money(sum((invoice.taxable_amount for invoice in invoices), Decimal("0"))),
        "cgst": money(sum((invoice.cgst_amount for invoice in invoices), Decimal("0"))),
        "sgst": money(sum((invoice.sgst_amount for invoice in invoices), Decimal("0"))),
        "igst": money(sum((invoice.igst_amount for invoice in invoices), Decimal("0"))),
    }
    if export:
        return _report_export_response(export, "gst", REPORT_COLUMNS["gst"], [row])
    return row


@router.get("/reports/material-sales", response_model=None)
def material_sales_report(
    export: ExportFormat | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict] | Response:
    rows = db.execute(
        select(
            InvoiceItem.material_name,
            func.sum(InvoiceItem.quantity).label("quantity"),
            func.sum(InvoiceItem.line_total).label("total"),
        ).group_by(InvoiceItem.material_name)
    ).all()
    report_rows = [
        {"material": row.material_name, "quantity": row.quantity, "total": row.total}
        for row in rows
    ]
    if export:
        return _report_export_response(
            export,
            "material-sales",
            REPORT_COLUMNS["material-sales"],
            report_rows,
        )
    return report_rows


@router.get("/reports/cheques", response_model=None)
def cheque_report(
    export: ExportFormat | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict] | Response:
    payments = db.scalars(select(Payment).where(Payment.payment_method == PaymentMethod.CHEQUE)).all()
    rows = [
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
    if export:
        return _report_export_response(export, "cheques", REPORT_COLUMNS["cheques"], rows)
    return rows


@router.get("/reports/reversed-payments", response_model=None)
def reversed_payment_report(
    export: ExportFormat | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict] | Response:
    payments = db.scalars(
        select(Payment).where(Payment.payment_status.in_([PaymentRecordStatus.REVERSED, PaymentRecordStatus.BOUNCED]))
    ).all()
    rows = [
        {
            "receipt_number": payment.receipt_number,
            "customer": payment.customer.name,
            "amount": payment.total_amount,
            "status": payment.payment_status.value,
        }
        for payment in payments
    ]
    if export:
        return _report_export_response(
            export,
            "reversed-payments",
            REPORT_COLUMNS["reversed-payments"],
            rows,
        )
    return rows


def _report_export_response(
    export_format: ExportFormat,
    filename_stem: str,
    columns: list[tuple[str, str]],
    rows: list[dict],
) -> Response:
    if export_format == "csv":
        return _csv_response(f"{filename_stem}.csv", columns, rows)
    return _excel_response(f"{filename_stem}.xlsx", columns, rows)


def _spreadsheet_value(value):
    if value is None:
        return ""
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


def _excel_response(
    filename: str,
    columns: list[tuple[str, str]],
    rows: list[dict],
) -> Response:
    wb = Workbook()
    ws = wb.active
    ws.title = "Report"
    ws.append([label for _, label in columns])
    for row in rows:
        ws.append([_spreadsheet_value(row.get(key)) for key, _ in columns])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    output = BytesIO()
    wb.save(output)
    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _csv_response(
    filename: str,
    columns: list[tuple[str, str]],
    rows: list[dict],
) -> Response:
    output = StringIO(newline="")
    csv_writer = csv.writer(output)
    csv_writer.writerow([label for _, label in columns])
    for row in rows:
        csv_writer.writerow([_spreadsheet_value(row.get(key)) for key, _ in columns])
    return Response(
        content=f"\ufeff{output.getvalue()}".encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
