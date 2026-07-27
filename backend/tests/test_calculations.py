from decimal import Decimal

from app.models.enums import InvoicePaymentStatus
from app.services.calculations import (
    calculate_invoice_totals,
    calculate_line,
    derive_invoice_status,
    remaining_amount,
)
from app.utils.numbers import amount_to_indian_words


def test_calculate_line_with_discount_and_gst():
    result = calculate_line(
        quantity=Decimal("10"),
        rate=Decimal("500"),
        gst_percentage=Decimal("5"),
        discount_percentage=Decimal("10"),
    )

    assert result["line_subtotal"] == Decimal("5000.00")
    assert result["discount_amount"] == Decimal("500.00")
    assert result["taxable_amount"] == Decimal("4500.00")
    assert result["gst_amount"] == Decimal("225.00")
    assert result["line_total"] == Decimal("4725.00")


def test_invoice_totals_split_gst_for_intra_state_sales():
    line = calculate_line(Decimal("20"), Decimal("1000"), Decimal("5"))
    totals = calculate_invoice_totals(
        [line],
        transport_charges=Decimal("500"),
        loading_charges=Decimal("250"),
        other_charges=Decimal("0"),
        round_off=Decimal("0"),
    )

    assert totals["taxable_amount"] == Decimal("20000.00")
    assert totals["cgst_amount"] == Decimal("500.00")
    assert totals["sgst_amount"] == Decimal("500.00")
    assert totals["grand_total"] == Decimal("21750.00")


def test_split_gst_reconciles_when_total_tax_has_an_odd_paise():
    line = calculate_line(Decimal("1"), Decimal("100.10"), Decimal("5"))
    totals = calculate_invoice_totals([line])

    assert totals["cgst_amount"] == Decimal("2.51")
    assert totals["sgst_amount"] == Decimal("2.50")
    assert totals["cgst_amount"] + totals["sgst_amount"] == line["gst_amount"]
    assert totals["grand_total"] == Decimal("105.11")


def test_payment_statuses_follow_remaining_amount_rules():
    total = Decimal("50000")

    assert derive_invoice_status(total, Decimal("0")) == InvoicePaymentStatus.UNPAID
    assert derive_invoice_status(total, Decimal("20000")) == InvoicePaymentStatus.PARTIALLY_PAID
    assert derive_invoice_status(total, Decimal("50000")) == InvoicePaymentStatus.FULLY_PAID
    assert derive_invoice_status(total, Decimal("55000")) == InvoicePaymentStatus.OVERPAID
    assert derive_invoice_status(total, Decimal("0"), cancelled=True) == InvoicePaymentStatus.CANCELLED


def test_remaining_amount_uses_payments_and_advance_adjustment():
    assert remaining_amount(Decimal("40000"), Decimal("15000"), Decimal("25000")) == Decimal("0.00")


def test_amount_to_indian_words():
    assert amount_to_indian_words(Decimal("125000")) == "One Lakh Twenty Five Thousand Rupees Only"
    assert (
        amount_to_indian_words(Decimal("40320.50"))
        == "Forty Thousand Three Hundred Twenty Rupees and Fifty Paise Only"
    )
