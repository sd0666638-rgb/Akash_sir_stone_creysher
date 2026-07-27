from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.enums import (
    InvoicePaymentStatus,
    LedgerTransactionType,
    PaymentRecordStatus,
)
from app.models.invoice import Invoice, InvoiceItem
from app.models.payment import CustomerLedger, Payment
from app.services.calculations import money


def dashboard_summary(db: Session, today: date) -> dict:
    month_start = today.replace(day=1)
    todays_invoices = db.scalars(select(Invoice).where(Invoice.invoice_date == today)).all()
    todays_payments = db.scalars(
        select(Payment).where(
            Payment.payment_date == today,
            Payment.payment_status == PaymentRecordStatus.SUCCESSFUL,
        )
    ).all()
    active_invoices = db.scalars(
        select(Invoice).where(Invoice.payment_status != InvoicePaymentStatus.CANCELLED)
    ).all()

    top_materials = db.execute(
        select(
            InvoiceItem.material_name,
            func.sum(InvoiceItem.quantity).label("quantity"),
            func.sum(InvoiceItem.line_total).label("sales"),
        )
        .join(Invoice, Invoice.id == InvoiceItem.invoice_id)
        .where(Invoice.invoice_date >= month_start)
        .group_by(InvoiceItem.material_name)
        .order_by(desc("sales"))
        .limit(5)
    ).all()
    recent_invoices = db.scalars(select(Invoice).order_by(desc(Invoice.id)).limit(8)).all()
    recent_payments = db.scalars(select(Payment).order_by(desc(Payment.id)).limit(8)).all()

    return {
        "todays_sales": money(sum((invoice.grand_total for invoice in todays_invoices), Decimal("0"))),
        "todays_collections": money(
            sum((payment.total_amount for payment in todays_payments), Decimal("0"))
        ),
        "total_outstanding_amount": money(
            sum(
                (invoice.remaining_amount for invoice in active_invoices if invoice.remaining_amount > 0),
                Decimal("0"),
            )
        ),
        "partially_paid_invoice_amount": money(
            sum(
                (
                    invoice.remaining_amount
                    for invoice in active_invoices
                    if invoice.payment_status == InvoicePaymentStatus.PARTIALLY_PAID
                ),
                Decimal("0"),
            )
        ),
        "fully_unpaid_invoice_amount": money(
            sum(
                (
                    invoice.remaining_amount
                    for invoice in active_invoices
                    if invoice.payment_status == InvoicePaymentStatus.UNPAID
                ),
                Decimal("0"),
            )
        ),
        "customer_advances": money(
            db.scalar(select(func.coalesce(func.sum(Customer.advance_balance), 0))) or Decimal("0")
        ),
        "total_customers": db.scalar(select(func.count(Customer.id))) or 0,
        "todays_orders": len(todays_invoices),
        "monthly_revenue": money(
            db.scalar(
                select(func.coalesce(func.sum(Invoice.grand_total), 0)).where(
                    Invoice.invoice_date >= month_start,
                    Invoice.payment_status != InvoicePaymentStatus.CANCELLED,
                )
            )
            or Decimal("0")
        ),
        "top_selling_materials": [
            {"material": row.material_name, "quantity": row.quantity, "sales": row.sales}
            for row in top_materials
        ],
        "recent_invoices": [
            {
                "id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "customer_id": invoice.customer_id,
                "grand_total": invoice.grand_total,
                "payment_status": invoice.payment_status.value,
            }
            for invoice in recent_invoices
        ],
        "recent_payments": [
            {
                "id": payment.id,
                "receipt_number": payment.receipt_number,
                "customer_id": payment.customer_id,
                "total_amount": payment.total_amount,
                "payment_method": payment.payment_method.value,
            }
            for payment in recent_payments
        ],
    }


def ageing_report(db: Session, as_of: date) -> list[dict]:
    rows: dict[int, dict] = {}
    invoices = db.scalars(
        select(Invoice).where(
            Invoice.payment_status.notin_(
                [InvoicePaymentStatus.FULLY_PAID, InvoicePaymentStatus.CANCELLED]
            )
        )
    ).all()
    for invoice in invoices:
        if invoice.remaining_amount <= 0:
            continue
        customer = invoice.customer
        row = rows.setdefault(
            customer.id,
            {
                "customer_id": customer.id,
                "customer_name": customer.name,
                "bucket_0_30": Decimal("0"),
                "bucket_31_60": Decimal("0"),
                "bucket_61_90": Decimal("0"),
                "bucket_91_180": Decimal("0"),
                "bucket_over_180": Decimal("0"),
                "total": Decimal("0"),
            },
        )
        days = (as_of - invoice.invoice_date).days
        bucket = "bucket_0_30"
        if days > 180:
            bucket = "bucket_over_180"
        elif days > 90:
            bucket = "bucket_91_180"
        elif days > 60:
            bucket = "bucket_61_90"
        elif days > 30:
            bucket = "bucket_31_60"
        row[bucket] = money(row[bucket] + invoice.remaining_amount)
        row["total"] = money(row["total"] + invoice.remaining_amount)
    return list(rows.values())


def analytics_report(db: Session, start_date: date, end_date: date) -> dict:
    """Build a compact, continuous daily trend report.

    Outstanding history is reconstructed from customer opening balances and
    ledger debits/credits. Keeping the calculation in Python makes the result
    consistent on both MySQL and SQLite and includes zero-activity days.
    """
    days = (end_date - start_date).days + 1
    dates = [start_date + timedelta(days=offset) for offset in range(days)]
    daily = {
        day: {
            "date": day,
            "sales": Decimal("0"),
            "collections": Decimal("0"),
            "invoice_count": 0,
            "new_customers": 0,
            "outstanding": Decimal("0"),
        }
        for day in dates
    }

    invoices = db.scalars(
        select(Invoice).where(
            Invoice.invoice_date >= start_date,
            Invoice.invoice_date <= end_date,
            Invoice.payment_status != InvoicePaymentStatus.CANCELLED,
        )
    ).all()
    customers_served: set[int] = set()
    for invoice in invoices:
        point = daily[invoice.invoice_date]
        point["sales"] += invoice.grand_total
        point["invoice_count"] += 1
        customers_served.add(invoice.customer_id)

    payments = db.scalars(
        select(Payment).where(
            Payment.payment_date >= start_date,
            Payment.payment_date <= end_date,
            Payment.payment_status == PaymentRecordStatus.SUCCESSFUL,
        )
    ).all()
    for payment in payments:
        daily[payment.payment_date]["collections"] += payment.total_amount

    customers = db.scalars(select(Customer)).all()
    opening_by_date: dict[date, list[tuple[int, Decimal]]] = {}
    balances: dict[int, Decimal] = {}
    for customer in customers:
        created_date = customer.created_at.date()
        if created_date > end_date:
            continue
        opening = Decimal(customer.opening_balance or 0)
        if created_date < start_date:
            balances[customer.id] = opening
        else:
            opening_by_date.setdefault(created_date, []).append((customer.id, opening))
            daily[created_date]["new_customers"] += 1

    ledger_by_date: dict[date, list[CustomerLedger]] = {}
    ledger_entries = db.scalars(
        select(CustomerLedger)
        .where(
            CustomerLedger.transaction_date <= end_date,
            # Applying an advance moves the same money from advance balance to
            # an invoice; it does not change the customer's net outstanding.
            CustomerLedger.transaction_type
            != LedgerTransactionType.ADVANCE_ADJUSTMENT,
        )
        .order_by(CustomerLedger.transaction_date, CustomerLedger.id)
    ).all()
    for entry in ledger_entries:
        if entry.transaction_date < start_date:
            balances[entry.customer_id] = (
                balances.get(entry.customer_id, Decimal("0"))
                + entry.debit
                - entry.credit
            )
        else:
            ledger_by_date.setdefault(entry.transaction_date, []).append(entry)

    for day in dates:
        for customer_id, opening in opening_by_date.get(day, []):
            balances[customer_id] = balances.get(customer_id, Decimal("0")) + opening
        for entry in ledger_by_date.get(day, []):
            balances[entry.customer_id] = (
                balances.get(entry.customer_id, Decimal("0"))
                + entry.debit
                - entry.credit
            )
        daily[day]["outstanding"] = sum(
            (max(balance, Decimal("0")) for balance in balances.values()),
            Decimal("0"),
        )

    material_rows = db.execute(
        select(
            InvoiceItem.material_name,
            InvoiceItem.unit,
            func.sum(InvoiceItem.quantity).label("quantity"),
            func.sum(InvoiceItem.line_total).label("sales"),
        )
        .join(Invoice, Invoice.id == InvoiceItem.invoice_id)
        .where(
            Invoice.invoice_date >= start_date,
            Invoice.invoice_date <= end_date,
            Invoice.payment_status != InvoicePaymentStatus.CANCELLED,
        )
        .group_by(InvoiceItem.material_name, InvoiceItem.unit)
        .order_by(desc("sales"))
        .limit(5)
    ).all()

    points = []
    for point in daily.values():
        points.append(
            {
                **point,
                "sales": money(point["sales"]),
                "collections": money(point["collections"]),
                "outstanding": money(point["outstanding"]),
            }
        )

    return {
        "start_date": start_date,
        "end_date": end_date,
        "summary": {
            "total_sales": money(
                sum((point["sales"] for point in points), Decimal("0"))
            ),
            "total_collections": money(
                sum((point["collections"] for point in points), Decimal("0"))
            ),
            "invoice_count": sum(point["invoice_count"] for point in points),
            "new_customers": sum(point["new_customers"] for point in points),
            "customers_served": len(customers_served),
            "current_outstanding": points[-1]["outstanding"] if points else Decimal("0.00"),
        },
        "daily": points,
        "top_materials": [
            {
                "material": row.material_name,
                "unit": row.unit,
                "quantity": row.quantity,
                "sales": row.sales,
            }
            for row in material_rows
        ],
    }


def invoices_by_status(db: Session, status_value: InvoicePaymentStatus | None = None) -> list[Invoice]:
    stmt = select(Invoice).order_by(desc(Invoice.invoice_date), desc(Invoice.id))
    if status_value:
        stmt = stmt.where(Invoice.payment_status == status_value)
    return db.scalars(stmt).all()
