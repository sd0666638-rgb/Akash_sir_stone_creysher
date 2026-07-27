from decimal import Decimal, ROUND_HALF_UP

from app.models.enums import InvoicePaymentStatus

PAISE = Decimal("0.01")


def money(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value or 0)).quantize(PAISE, rounding=ROUND_HALF_UP)


def calculate_line(
    quantity: Decimal,
    rate: Decimal,
    gst_percentage: Decimal,
    discount_percentage: Decimal = Decimal("0"),
) -> dict[str, Decimal]:
    line_subtotal = money(quantity * rate)
    discount_amount = money(line_subtotal * discount_percentage / Decimal("100"))
    taxable_amount = money(line_subtotal - discount_amount)
    gst_amount = money(taxable_amount * gst_percentage / Decimal("100"))
    line_total = money(taxable_amount + gst_amount)
    return {
        "line_subtotal": line_subtotal,
        "discount_amount": discount_amount,
        "taxable_amount": taxable_amount,
        "gst_amount": gst_amount,
        "line_total": line_total,
    }


def calculate_invoice_totals(
    line_totals: list[dict[str, Decimal]],
    transport_charges: Decimal = Decimal("0"),
    loading_charges: Decimal = Decimal("0"),
    other_charges: Decimal = Decimal("0"),
    round_off: Decimal = Decimal("0"),
    intra_state: bool = True,
) -> dict[str, Decimal]:
    subtotal = money(sum(row["line_subtotal"] for row in line_totals))
    discount_amount = money(sum(row["discount_amount"] for row in line_totals))
    taxable_amount = money(sum(row["taxable_amount"] for row in line_totals))
    gst_total = money(sum(row["gst_amount"] for row in line_totals))
    if intra_state:
        cgst_amount = money(gst_total / Decimal("2"))
        # Assign the residual paise to SGST so the split always reconciles
        # exactly to the GST already included in grand_total.
        sgst_amount = money(gst_total - cgst_amount)
        igst_amount = Decimal("0.00")
    else:
        cgst_amount = Decimal("0.00")
        sgst_amount = Decimal("0.00")
        igst_amount = gst_total

    grand_total = money(
        taxable_amount
        + gst_total
        + transport_charges
        + loading_charges
        + other_charges
        + round_off
    )
    return {
        "subtotal": subtotal,
        "discount_amount": discount_amount,
        "taxable_amount": taxable_amount,
        "cgst_amount": cgst_amount,
        "sgst_amount": sgst_amount,
        "igst_amount": igst_amount,
        "grand_total": grand_total,
    }


def remaining_amount(
    grand_total: Decimal, total_paid: Decimal, advance_adjusted: Decimal = Decimal("0")
) -> Decimal:
    return money(grand_total - total_paid - advance_adjusted)


def derive_invoice_status(
    grand_total: Decimal,
    total_paid: Decimal,
    advance_adjusted: Decimal = Decimal("0"),
    cancelled: bool = False,
) -> InvoicePaymentStatus:
    if cancelled:
        return InvoicePaymentStatus.CANCELLED
    remaining = remaining_amount(grand_total, total_paid, advance_adjusted)
    applied = money(total_paid + advance_adjusted)
    if applied == Decimal("0.00"):
        return InvoicePaymentStatus.UNPAID
    if remaining > Decimal("0.00"):
        return InvoicePaymentStatus.PARTIALLY_PAID
    if remaining == Decimal("0.00"):
        return InvoicePaymentStatus.FULLY_PAID
    return InvoicePaymentStatus.OVERPAID
