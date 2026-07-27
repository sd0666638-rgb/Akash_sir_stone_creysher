from datetime import date
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace

from pypdf import PdfReader

from app.models.company_settings import CompanySettings
from app.services.documents import document_filename, invoice_pdf, receipt_pdf


def test_sample_style_invoice_pdf_is_one_page_and_contains_dispatch_details():
    customer = SimpleNamespace(
        name="Nirmal Anand Buildcon Pvt. Ltd.",
        mobile_number="9999999999",
        gst_number="27AAGCN6325G1ZF",
        billing_address="At Post Gulhalli, Tal Tuljapur, Osmanabad - 413601",
        delivery_address=None,
        city="Osmanabad",
        state="Maharashtra",
    )
    items = [
        SimpleNamespace(
            material_name="C Sand",
            dispatch_date=date(2025, 12, 19),
            receipt_number="1405",
            hsn_code="25171090",
            vehicle_number="MH 13 EP 9426",
            quantity=Decimal("6"),
            unit="Brs",
            rate=Decimal("3200"),
            taxable_amount=Decimal("19200"),
        ),
        SimpleNamespace(
            material_name="C Sand",
            dispatch_date=date(2025, 12, 22),
            receipt_number="1569",
            hsn_code="25171090",
            vehicle_number="MH 13 EP 3576",
            quantity=Decimal("6"),
            unit="Brs",
            rate=Decimal("3200"),
            taxable_amount=Decimal("19200"),
        ),
    ]
    invoice = SimpleNamespace(
        invoice_number="INV-20251222-0001",
        invoice_date=date(2025, 12, 22),
        delivery_note="1405/1569",
        buyer_order_number="NABPL/MH/001",
        other_reference="",
        vehicle_number="MH 13 EP 9426",
        customer=customer,
        items=items,
        subtotal=Decimal("38400"),
        discount_amount=Decimal("0"),
        taxable_amount=Decimal("38400"),
        cgst_amount=Decimal("960"),
        sgst_amount=Decimal("960"),
        igst_amount=Decimal("0"),
        transport_charges=Decimal("0"),
        loading_charges=Decimal("0"),
        other_charges=Decimal("0"),
        round_off=Decimal("0"),
        grand_total=Decimal("40320"),
    )

    content = invoice_pdf(invoice)
    reader = PdfReader(BytesIO(content))
    text = reader.pages[0].extract_text()

    assert content.startswith(b"%PDF")
    assert len(reader.pages) == 1
    assert float(reader.pages[0].mediabox.width) == 612
    assert float(reader.pages[0].mediabox.height) == 792
    assert "TAX INVOICE" in text
    assert "1405" in text and "1569" in text
    assert "25171090" in text
    assert "MH 13 EP 9426" in text and "MH 13 EP 3576" in text
    assert "Forty Thousand Three Hundred Twenty Rupees Only" in text
    assert "Grand Total" in text and "40320.00" in text
    assert "Period" not in text
    assert "27AAGCN6325G1ZF" in text

    invoice.items = items * 10
    multipage_reader = PdfReader(BytesIO(invoice_pdf(invoice)))

    assert len(multipage_reader.pages) >= 2
    continuation_text = multipage_reader.pages[1].extract_text()
    assert "Invoice INV-20251222-0001" in continuation_text
    assert "Buyer: Nirmal Anand Buildcon Pvt. Ltd." in continuation_text

    invoice.items = items
    invoice.payment_status = SimpleNamespace(value="Cancelled")
    cancelled_text = PdfReader(BytesIO(invoice_pdf(invoice))).pages[0].extract_text()
    assert "CANCELLED TAX INVOICE" in cancelled_text

    invoice.payment_status = None
    customer.gst_number = "29ABCDE1234F1Z5"
    invalid_gstin_text = PdfReader(BytesIO(invoice_pdf(invoice))).pages[0].extract_text()
    assert "29ABCDE1234F1Z5" not in invalid_gstin_text


def test_invoice_pdf_and_filename_use_persisted_company_profile():
    customer = SimpleNamespace(
        name="Plain Buyer",
        mobile_number="9876543210",
        gst_number=None,
        billing_address=None,
        delivery_address=None,
        city="Pune",
        state="Maharashtra",
    )
    item = SimpleNamespace(
        material_name="Stone",
        dispatch_date=date(2026, 7, 27),
        receipt_number="1",
        hsn_code="25171090",
        vehicle_number="MH12AB1234",
        quantity=Decimal("1"),
        unit="TON",
        rate=Decimal("100"),
        taxable_amount=Decimal("100"),
    )
    invoice = SimpleNamespace(
        invoice_number="INV-1",
        invoice_date=date(2026, 7, 27),
        delivery_note=None,
        buyer_order_number="1-27072026",
        other_reference=None,
        vehicle_number=None,
        customer=customer,
        items=[item],
        subtotal=Decimal("100"),
        discount_amount=Decimal("0"),
        taxable_amount=Decimal("100"),
        cgst_amount=Decimal("2.50"),
        sgst_amount=Decimal("2.50"),
        igst_amount=Decimal("0"),
        transport_charges=Decimal("0"),
        loading_charges=Decimal("0"),
        other_charges=Decimal("0"),
        round_off=Decimal("0"),
        grand_total=Decimal("105"),
    )
    company = CompanySettings(
        id=1,
        company_name="Configured Stone Shop",
        company_address="42 Crusher Road, Pune",
        company_phone="9123456789",
        company_gstin="27BEBPP1879J1Z2",
        company_state="Maharashtra",
        company_gst_state_code="27",
        company_jurisdiction="Pune",
        company_bank_name="Example Bank",
        company_bank_account="123456",
        company_bank_ifsc="EXAM0000123",
        company_bank_branch="Market Yard",
    )

    text = PdfReader(BytesIO(invoice_pdf(invoice, company))).pages[0].extract_text()

    assert "CONFIGURED STONE SHOP" in text
    assert "42 Crusher Road, Pune" in text
    assert "27BEBPP1879J1Z2" in text
    assert "Example Bank" in text
    assert document_filename(date(2026, 7, 27), company=company).startswith(
        "Configured Stone Shop - "
    )


def test_document_filename_matches_requested_double_dot_format():
    assert (
        document_filename(date(2025, 12, 22))
        == "Radhya Construction - 22.12.2025..pdf"
    )


def test_payment_receipt_contains_purchase_and_balance_breakdown():
    customer = SimpleNamespace(
        name="Receipt Buyer",
        mobile_number="9876543210",
    )
    item = SimpleNamespace(
        material_name="20 MM Stone",
        dispatch_date=date(2026, 7, 25),
        receipt_number="CH-104",
        hsn_code="25171090",
        vehicle_number="MH12AB1234",
        quantity=Decimal("5"),
        unit="TON",
        rate=Decimal("100"),
        gst_percentage=Decimal("5"),
        line_total=Decimal("525"),
    )
    prior_payment = SimpleNamespace(
        id=1,
        payment_date=date(2026, 7, 26),
        payment_status=SimpleNamespace(value="Successful"),
    )
    invoice = SimpleNamespace(
        invoice_number="INV-20260725-0001",
        invoice_date=date(2026, 7, 25),
        buyer_order_number="BO-55",
        vehicle_number=None,
        items=[item],
        grand_total=Decimal("1000"),
        advance_adjusted=Decimal("100"),
        advance_adjustments=None,
    )
    previous_allocation = SimpleNamespace(
        payment=prior_payment,
        allocated_amount=Decimal("200"),
    )
    payment = SimpleNamespace(
        id=2,
        receipt_number="RCT-20260727-0001",
        customer=customer,
        payment_date=date(2026, 7, 27),
        total_amount=Decimal("300"),
        payment_method=SimpleNamespace(value="Cash"),
        transaction_reference=None,
        payment_status=SimpleNamespace(value="Successful"),
        unallocated_amount=Decimal("0"),
        notes=None,
    )
    current_allocation = SimpleNamespace(
        payment=payment,
        invoice=invoice,
        allocated_amount=Decimal("300"),
    )
    invoice.allocations = [previous_allocation, current_allocation]
    payment.allocations = [current_allocation]

    content = receipt_pdf(payment)
    reader = PdfReader(BytesIO(content))
    text = "\n".join(page.extract_text() for page in reader.pages)

    assert content.startswith(b"%PDF")
    assert "PAYMENT RECEIPT" in text
    assert "INV-20260725-0001" in text
    assert "20 MM Stone" in text
    assert "CH-104" in text
    assert "Paid before" in text and "300.00" in text
    assert "Paid with this receipt" in text
    assert "Remaining after payment" in text and "400.00" in text
