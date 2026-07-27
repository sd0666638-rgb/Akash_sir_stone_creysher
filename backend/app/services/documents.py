from io import BytesIO
from decimal import Decimal
from pathlib import Path
from re import sub
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.config import settings
from app.models.company_settings import CompanySettings
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.utils.gst import valid_indian_gstin
from app.utils.numbers import amount_to_indian_words


def document_filename(
    document_date,
    suffix: str = "pdf",
    company: CompanySettings | None = None,
) -> str:
    configured_prefix = (
        company.company_name if company is not None else settings.DOCUMENT_FILE_PREFIX
    )
    prefix = sub(r'[<>:"/\\|?*]+', "", configured_prefix).strip()
    date_text = document_date.strftime("%d.%m.%Y")
    ending = f"..{suffix}" if settings.DOCUMENT_FILENAME_DOUBLE_DOT else f".{suffix}"
    return f"{prefix} - {date_text}{ending}"


def _money(value) -> str:
    return f"{Decimal(value or 0):.2f}"


def _p(text: str | None, style) -> Paragraph:
    return Paragraph(str(text or ""), style)


def _styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="CompanyTitle",
            parent=styles["Title"],
            alignment=TA_CENTER,
            fontName="Times-Bold",
            fontSize=23,
            leading=25,
            spaceAfter=2,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CompanyAddress",
            parent=styles["Normal"],
            alignment=TA_CENTER,
            fontName="Times-Bold",
            fontSize=9.5,
            leading=11.5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="LogoMark",
            parent=styles["Title"],
            alignment=TA_CENTER,
            fontName="Times-Bold",
            fontSize=30,
            leading=32,
            textColor=colors.HexColor("#172b4d"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="LogoCaption",
            parent=styles["Normal"],
            alignment=TA_CENTER,
            fontName="Times-Bold",
            fontSize=8,
            leading=9,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CenterSmall",
            parent=styles["Normal"],
            alignment=TA_CENTER,
            fontName="Times-Roman",
            fontSize=8,
            leading=9.5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="RightSmall",
            parent=styles["Normal"],
            alignment=TA_RIGHT,
            fontName="Times-Roman",
            fontSize=8,
            leading=9.5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Cell",
            parent=styles["Normal"],
            fontName="Times-Roman",
            fontSize=8,
            leading=9.5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CellBold",
            parent=styles["Normal"],
            fontName="Times-Bold",
            fontSize=8,
            leading=9.5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CellCenter",
            parent=styles["Normal"],
            alignment=TA_CENTER,
            fontName="Times-Roman",
            fontSize=7.5,
            leading=8.5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CellCenterBold",
            parent=styles["Normal"],
            alignment=TA_CENTER,
            fontName="Times-Bold",
            fontSize=8,
            leading=9,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CellRight",
            parent=styles["Normal"],
            alignment=TA_RIGHT,
            fontName="Times-Roman",
            fontSize=7.5,
            leading=8.5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CellRightBold",
            parent=styles["Normal"],
            alignment=TA_RIGHT,
            fontName="Times-Bold",
            fontSize=8,
            leading=9,
        )
    )
    return styles


def _box_table(data, col_widths=None) -> Table:
    table = Table(data, colWidths=col_widths)
    table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.8, colors.black),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _date_text(value) -> str:
    return value.strftime("%d/%m/%Y") if value else ""


def _quantity(value) -> str:
    text = f"{Decimal(value or 0):f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def _percent(amount, taxable_amount) -> str:
    amount = Decimal(amount or 0)
    taxable_amount = Decimal(taxable_amount or 0)
    if not amount or not taxable_amount:
        return "0.00"
    return f"{(amount * Decimal('100') / taxable_amount):.2f}"


def _state_code(gst_number: str | None) -> str:
    gst_number = (gst_number or "").strip()
    return gst_number[:2] if len(gst_number) >= 2 and gst_number[:2].isdigit() else ""


def _paragraph_lines(lines: list[str], style) -> Paragraph:
    return _p("<br/>".join(line for line in lines if line), style)


def _company_mark(styles, company: CompanySettings | None = None):
    company_name = (
        company.company_name if company is not None else settings.COMPANY_NAME
    )
    configured_path = settings.COMPANY_LOGO_PATH.strip()
    if configured_path:
        logo_path = Path(configured_path).expanduser()
        if logo_path.is_file():
            logo = Image(str(logo_path))
            logo.drawHeight = 22 * mm
            logo.drawWidth = min(50 * mm, logo.drawHeight * logo.imageWidth / logo.imageHeight)
            logo.hAlign = "CENTER"
            return [logo]

    initials = "".join(part[0] for part in company_name.split() if part)[:3].upper()
    return [
        _p(escape(initials or "RC"), styles["LogoMark"]),
        _p(escape(company_name.upper()), styles["LogoCaption"]),
    ]


def invoice_pdf(
    invoice: Invoice,
    company: CompanySettings | None = None,
) -> bytes:
    company_name = company.company_name if company is not None else settings.COMPANY_NAME
    company_address = (
        company.company_address if company is not None else settings.COMPANY_ADDRESS
    )
    company_phone = (
        company.company_phone if company is not None else settings.COMPANY_PHONE
    )
    company_gstin = (
        company.company_gstin if company is not None else settings.COMPANY_GSTIN
    )
    company_state = (
        company.company_state if company is not None else settings.COMPANY_STATE
    )
    company_gst_state_code = (
        company.company_gst_state_code
        if company is not None
        else settings.COMPANY_GST_STATE_CODE
    )
    company_jurisdiction = (
        company.company_jurisdiction
        if company is not None
        else settings.COMPANY_JURISDICTION
    )
    company_bank_name = (
        company.company_bank_name if company is not None else settings.COMPANY_BANK_NAME
    )
    company_bank_account = (
        company.company_bank_account
        if company is not None
        else settings.COMPANY_BANK_ACCOUNT
    )
    company_bank_ifsc = (
        company.company_bank_ifsc if company is not None else settings.COMPANY_BANK_IFSC
    )
    company_bank_branch = (
        company.company_bank_branch
        if company is not None
        else settings.COMPANY_BANK_BRANCH
    )
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=18.5 * mm,
        leftMargin=18.5 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Tax Invoice {invoice.invoice_number}",
        author=company_name,
    )
    styles = _styles()
    customer = invoice.customer
    width = doc.width
    invoice_status = getattr(getattr(invoice, "payment_status", None), "value", "")
    is_cancelled = str(invoice_status).casefold() == "cancelled"

    company_lines = [escape(company_address)]
    if company_phone:
        company_lines.append(f"Mobile: {escape(company_phone)}")
    if company_gstin:
        company_lines.append(f"GSTIN: {escape(company_gstin)}")

    header = Table(
        [
            [
                _company_mark(styles, company),
                [
                    _p(escape(company_name.upper()), styles["CompanyTitle"]),
                    _paragraph_lines(company_lines, styles["CompanyAddress"]),
                ],
            ]
        ],
        colWidths=[width * 0.33, width * 0.67],
        rowHeights=[34 * mm],
    )
    header.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.9, colors.black),
                ("INNERGRID", (0, 0), (-1, -1), 0.75, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    title = Table(
        [
            [
                _p(
                    "<b>CANCELLED TAX INVOICE</b>" if is_cancelled else "<b>TAX INVOICE</b>",
                    styles["CellCenterBold"],
                )
            ]
        ],
        colWidths=[width],
        rowHeights=[7 * mm],
    )
    title.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.9, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )

    customer_address = escape(
        customer.billing_address or customer.delivery_address or ""
    ).replace("\n", "<br/>")
    customer_location = escape(
        ", ".join(part for part in [customer.city, customer.state] if part)
    )
    customer_gstin = valid_indian_gstin(customer.gst_number)
    customer_state_code = _state_code(customer_gstin)
    customer_lines = [
        "To,",
        f"<b>{escape(customer.name.upper())}</b>",
        customer_address,
        customer_location,
    ]
    if customer.mobile_number:
        customer_lines.append(f"Mobile: {escape(customer.mobile_number)}")
    if customer_gstin:
        customer_lines.append(f"GST NO. {escape(customer_gstin)}")
    if customer_state_code:
        customer_lines.append(f"GST State Code : {escape(customer_state_code)}")

    delivery_note = escape(getattr(invoice, "delivery_note", None) or "")
    buyer_order = escape(getattr(invoice, "buyer_order_number", None) or "")
    other_reference = escape(getattr(invoice, "other_reference", None) or "")

    party = Table(
        [
            [
                _paragraph_lines(customer_lines, styles["Cell"]),
                _p(f"Invoice No - <b>{escape(invoice.invoice_number)}</b>", styles["Cell"]),
                _p(f"<b>DATE : {_date_text(invoice.invoice_date)}</b>", styles["CellCenterBold"]),
            ],
            [
                "",
                _p(f"Delivery Note<br/><b>{delivery_note}</b>", styles["Cell"]),
                "",
            ],
            [
                "",
                _p(f"Buyer's Order No.<br/><b>{buyer_order}</b>", styles["Cell"]),
                _p(f"Other Reference(s)<br/><b>{other_reference}</b>", styles["Cell"]),
            ],
        ],
        colWidths=[width * 0.44, width * 0.34, width * 0.22],
        rowHeights=[9 * mm, 11 * mm, 13 * mm],
    )
    party.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.9, colors.black),
                ("INNERGRID", (0, 0), (-1, -1), 0.75, colors.black),
                ("SPAN", (0, 0), (0, 2)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )

    units = {str(item.unit).strip() for item in invoice.items if item.unit}
    unit_label = next(iter(units)) if len(units) == 1 else "Unit"
    item_rows = [
        [
            _p("<b>Date</b>", styles["CellCenterBold"]),
            _p("<b>Receipt No</b>", styles["CellCenterBold"]),
            _p("<b>Material</b>", styles["CellCenterBold"]),
            _p("<b>HSN Code</b>", styles["CellCenterBold"]),
            _p("<b>VEHICLE NO</b>", styles["CellCenterBold"]),
            _p(f"<b>Qty<br/>{escape(unit_label)}</b>", styles["CellCenterBold"]),
            _p("<b>Rate</b>", styles["CellCenterBold"]),
            _p("<b>AMOUNT</b>", styles["CellCenterBold"]),
        ]
    ]
    for item in invoice.items:
        dispatch_date = getattr(item, "dispatch_date", None) or invoice.invoice_date
        receipt_number = getattr(item, "receipt_number", None) or ""
        hsn_code = getattr(item, "hsn_code", None) or ""
        vehicle_number = getattr(item, "vehicle_number", None) or invoice.vehicle_number or ""
        item_rows.append(
            [
                _p(_date_text(dispatch_date), styles["CellCenter"]),
                _p(escape(receipt_number), styles["CellCenter"]),
                _p(escape(item.material_name), styles["CellCenter"]),
                _p(escape(hsn_code), styles["CellCenter"]),
                _p(escape(vehicle_number), styles["CellCenter"]),
                _p(_quantity(item.quantity), styles["CellCenter"]),
                _p(_money(item.rate), styles["CellRight"]),
                _p(_money(item.taxable_amount), styles["CellRightBold"]),
            ]
        )

    anticipated_summary_rows = (
        3
        + (2 if Decimal(invoice.discount_amount or 0) else 0)
        + int(bool(Decimal(invoice.cgst_amount or 0)))
        + int(bool(Decimal(invoice.sgst_amount or 0)))
        + int(bool(Decimal(invoice.igst_amount or 0)))
        + sum(
            int(bool(Decimal(amount or 0)))
            for amount in (
                invoice.transport_charges,
                invoice.loading_charges,
                invoice.other_charges,
            )
        )
    )
    target_item_rows = max(3, 8 - max(0, anticipated_summary_rows - 5))
    display_item_rows = max(target_item_rows, len(invoice.items))
    for _ in range(display_item_rows - len(invoice.items)):
        item_rows.append(["", "", "", "", "", "", "", ""])

    total_quantity = sum((Decimal(item.quantity or 0) for item in invoice.items), Decimal("0"))
    item_rows.append(
        [
            _p("<b>Total Quantity</b>", styles["CellRightBold"]),
            "",
            "",
            "",
            "",
            _p(f"<b>{_quantity(total_quantity)}</b>", styles["CellCenterBold"]),
            _p("<b>Sub Total</b>", styles["Cell"]),
            _p(f"<b>{_money(invoice.subtotal)}</b>", styles["CellRightBold"]),
        ]
    )
    item_table = Table(
        item_rows,
        repeatRows=1,
        colWidths=[
            width * 0.108,
            width * 0.110,
            width * 0.110,
            width * 0.110,
            width * 0.167,
            width * 0.067,
            width * 0.205,
            width * 0.123,
        ],
        rowHeights=[10.5 * mm] + [6.5 * mm] * display_item_rows + [7 * mm],
    )
    item_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.9, colors.black),
                ("INNERGRID", (0, 0), (-1, -1), 0.65, colors.black),
                ("SPAN", (0, -1), (4, -1)),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )

    subtotal = Decimal(invoice.subtotal or 0)
    discount = Decimal(invoice.discount_amount or 0)
    taxable = Decimal(invoice.taxable_amount or 0)
    cgst = Decimal(invoice.cgst_amount or 0)
    sgst = Decimal(invoice.sgst_amount or 0)
    igst = Decimal(invoice.igst_amount or 0)
    tax_inclusive_total = taxable + cgst + sgst + igst
    summary_entries: list[tuple[str, str]] = []
    if discount:
        summary_entries.extend(
            [
                ("Discount", f"-{_money(discount)}"),
                ("Taxable Amount", _money(taxable)),
            ]
        )
    if cgst:
        summary_entries.append((f"CGST @ {_percent(cgst, taxable)}%", _money(cgst)))
    if sgst:
        summary_entries.append((f"SGST @ {_percent(sgst, taxable)}%", _money(sgst)))
    if igst:
        summary_entries.append((f"IGST @ {_percent(igst, taxable)}%", _money(igst)))
    summary_entries.append(("Total", _money(tax_inclusive_total)))
    for label, amount in [
        ("Transport Charges", invoice.transport_charges),
        ("Loading Charges", invoice.loading_charges),
        ("Other Charges", invoice.other_charges),
    ]:
        if Decimal(amount or 0):
            summary_entries.append((label, _money(amount)))
    summary_entries.extend(
        [
            ("Round Off", _money(invoice.round_off)),
            ("Grand Total", _money(invoice.grand_total)),
        ]
    )

    summary_data = [
        [
            "",
            _p(f"<b>{escape(label)}</b>" if label == "Grand Total" else escape(label), styles["Cell"]),
            _p(
                f"<b>{escape(amount)}</b>" if label == "Grand Total" else escape(amount),
                styles["CellRightBold"] if label == "Grand Total" else styles["CellRight"],
            ),
        ]
        for label, amount in summary_entries
    ]
    summary_data[-1][0] = _p(
        f"<b>{escape(amount_to_indian_words(invoice.grand_total))}</b>", styles["CellBold"]
    )
    summary_table = Table(
        summary_data,
        colWidths=[width * 0.67, width * 0.205, width * 0.125],
        rowHeights=[6.5 * mm] * len(summary_data),
    )
    summary_commands = [
        ("BOX", (0, 0), (-1, -1), 0.9, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 0.65, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]
    if len(summary_data) > 1:
        summary_commands.append(("SPAN", (0, 0), (0, len(summary_data) - 2)))
    summary_table.setStyle(TableStyle(summary_commands))

    jurisdiction = escape(company_jurisdiction or "applicable")
    footer_lines = [
        f"<b>GST No:</b>&nbsp;&nbsp; {escape(company_gstin or '-')}",
        (
            f"<b>State:</b> {escape(company_state or '-')}"
            f"&nbsp;&nbsp; <b>GST State Code:</b> {escape(company_gst_state_code or '-')}"
        ),
        "<b>Terms and Conditions</b>",
        f"(1) Subject to {jurisdiction} jurisdiction.",
        (
            f"(2) Payment should be made within {settings.COMPANY_PAYMENT_TERMS_DAYS} "
            "days from invoice date."
        ),
        (
            f"(3) Interest at {settings.COMPANY_LATE_INTEREST_PERCENT}% may be charged "
            "if payment remains overdue for one month."
        ),
    ]
    bank_parts = []
    for label, value in [
        ("NAME OF BANK", company_bank_name),
        ("ACCOUNT NO.", company_bank_account),
        ("IFSC", company_bank_ifsc),
        ("BRANCH", company_bank_branch),
    ]:
        if value:
            bank_parts.append(f"<b>{label}:</b> {escape(value)}")
    if bank_parts:
        footer_lines.append("<b>BANK DETAILS</b> " + "&nbsp;&nbsp; ".join(bank_parts))

    footer = Table(
        [
            [
                _paragraph_lines(footer_lines, styles["Cell"]),
                [
                    _p(f"For, {escape(company_name.upper())}", styles["CellCenter"]),
                    Spacer(1, 22 * mm),
                    _p("<b>Authorised Signatory</b>", styles["CellCenterBold"]),
                ],
            ]
        ],
        colWidths=[width * 0.68, width * 0.32],
        rowHeights=[40 * mm],
    )
    footer.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.9, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    elements = [header, title, party, item_table, summary_table, footer]

    def decorate_page(canvas, document) -> None:
        canvas.saveState()
        if document.page > 1:
            page_width, page_height = letter
            canvas.setFillColor(colors.black)
            canvas.setFont("Times-Bold", 8)
            canvas.drawString(
                doc.leftMargin,
                page_height - 8 * mm,
                company_name.upper(),
            )
            canvas.drawCentredString(
                page_width / 2,
                page_height - 8 * mm,
                f"Invoice {invoice.invoice_number}",
            )
            canvas.drawRightString(
                page_width - doc.rightMargin,
                page_height - 8 * mm,
                f"Page {document.page}",
            )
            canvas.setFont("Times-Roman", 7)
            canvas.drawString(
                doc.leftMargin,
                page_height - 12 * mm,
                f"Buyer: {customer.name}",
            )
            canvas.setLineWidth(0.5)
            canvas.line(
                doc.leftMargin,
                page_height - 14 * mm,
                page_width - doc.rightMargin,
                page_height - 14 * mm,
            )
        if is_cancelled:
            page_width, page_height = letter
            canvas.setFillColor(colors.HexColor("#dddddd"))
            canvas.setFont("Times-Bold", 48)
            canvas.translate(page_width / 2, page_height / 2)
            canvas.rotate(35)
            canvas.drawCentredString(0, 0, "CANCELLED")
        canvas.restoreState()

    doc.build(elements, onFirstPage=decorate_page, onLaterPages=decorate_page)
    return buffer.getvalue()


def receipt_pdf(
    payment: Payment,
    company: CompanySettings | None = None,
) -> bytes:
    company_name = company.company_name if company is not None else settings.COMPANY_NAME
    company_address = (
        company.company_address if company is not None else settings.COMPANY_ADDRESS
    )
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=f"Payment Receipt {payment.receipt_number}",
        author=company_name,
    )
    styles = _styles()
    width = doc.width
    status_text = str(
        getattr(getattr(payment, "payment_status", None), "value", None)
        or getattr(payment, "payment_status", None)
        or "Successful"
    )

    def paid_before(allocation) -> Decimal:
        invoice = allocation.invoice
        adjustments = getattr(invoice, "advance_adjustments", None)
        if adjustments is None:
            prior = Decimal(invoice.advance_adjusted or 0)
        else:
            prior = sum(
                (
                    Decimal(adjustment.adjusted_amount or 0)
                    for adjustment in adjustments
                    if adjustment.adjustment_date <= payment.payment_date
                ),
                Decimal("0"),
            )
        current_key = (
            payment.payment_date,
            int(getattr(payment, "id", 0) or 0),
        )
        for other in getattr(invoice, "allocations", []):
            other_payment = getattr(other, "payment", None)
            if (
                other_payment is None
                or other_payment is payment
                or (
                    getattr(other_payment, "id", None) is not None
                    and getattr(other_payment, "id", None) == getattr(payment, "id", None)
                )
            ):
                continue
            other_status = str(
                getattr(getattr(other_payment, "payment_status", None), "value", None)
                or getattr(other_payment, "payment_status", None)
                or ""
            )
            other_key = (
                getattr(other_payment, "payment_date", payment.payment_date),
                int(getattr(other_payment, "id", 0) or 0),
            )
            if other_status == "Successful" and other_key < current_key:
                prior += Decimal(other.allocated_amount or 0)
        return max(prior, Decimal("0"))

    def purchased_items_table(invoice: Invoice) -> Table:
        rows = [
            [
                _p("<b>Dispatch</b>", styles["CellCenterBold"]),
                _p("<b>Challan</b>", styles["CellCenterBold"]),
                _p("<b>Material / HSN / GST</b>", styles["CellCenterBold"]),
                _p("<b>Vehicle</b>", styles["CellCenterBold"]),
                _p("<b>Quantity</b>", styles["CellCenterBold"]),
                _p("<b>Rate</b>", styles["CellCenterBold"]),
                _p("<b>Line total</b>", styles["CellCenterBold"]),
            ]
        ]
        for item in invoice.items:
            dispatch_date = getattr(item, "dispatch_date", None) or invoice.invoice_date
            material_lines = [f"<b>{escape(item.material_name)}</b>"]
            if getattr(item, "hsn_code", None):
                material_lines.append(f"HSN: {escape(item.hsn_code)}")
            material_lines.append(f"GST: {_quantity(item.gst_percentage)}%")
            rows.append(
                [
                    _p(_date_text(dispatch_date), styles["CellCenter"]),
                    _p(escape(getattr(item, "receipt_number", None) or "-"), styles["CellCenter"]),
                    _p("<br/>".join(material_lines), styles["Cell"]),
                    _p(
                        escape(
                            getattr(item, "vehicle_number", None)
                            or getattr(invoice, "vehicle_number", None)
                            or "-"
                        ),
                        styles["CellCenter"],
                    ),
                    _p(
                        f"{_quantity(item.quantity)} {escape(item.unit or '')}",
                        styles["CellCenter"],
                    ),
                    _p(_money(item.rate), styles["CellRight"]),
                    _p(_money(item.line_total), styles["CellRightBold"]),
                ]
            )
        table = Table(
            rows,
            repeatRows=1,
            colWidths=[
                width * 0.11,
                width * 0.10,
                width * 0.25,
                width * 0.15,
                width * 0.11,
                width * 0.13,
                width * 0.15,
            ],
        )
        table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.8, colors.black),
                    ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f2ef")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        return table

    def invoice_value_table(invoice: Invoice) -> Table:
        entries: list[tuple[str, str]] = []
        for label, attribute, negative in [
            ("Subtotal", "subtotal", False),
            ("Discount", "discount_amount", True),
            ("Taxable amount", "taxable_amount", False),
            ("CGST", "cgst_amount", False),
            ("SGST", "sgst_amount", False),
            ("IGST", "igst_amount", False),
            ("Transport charges", "transport_charges", False),
            ("Loading charges", "loading_charges", False),
            ("Other charges", "other_charges", False),
            ("Round off", "round_off", False),
        ]:
            amount = Decimal(getattr(invoice, attribute, 0) or 0)
            if amount:
                entries.append((label, f"-{_money(amount)}" if negative else _money(amount)))
        entries.append(("Invoice total", _money(invoice.grand_total)))
        rows = [
            [
                _p(
                    f"<b>{escape(label)}</b>" if label == "Invoice total" else escape(label),
                    styles["Cell"],
                ),
                _p(
                    f"<b>Rs. {escape(amount)}</b>"
                    if label == "Invoice total"
                    else f"Rs. {escape(amount)}",
                    styles["CellRightBold"] if label == "Invoice total" else styles["CellRight"],
                ),
            ]
            for label, amount in entries
        ]
        table = Table(rows, colWidths=[45 * mm, 35 * mm], hAlign="RIGHT")
        table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.8, colors.black),
                    ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.grey),
                    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e8f2ef")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        return table

    elements = [
        _p(escape(company_name.upper()), styles["CompanyTitle"]),
        _p(escape(company_address), styles["CompanyAddress"]),
        Spacer(1, 8),
        _p("<b>PAYMENT RECEIPT</b>", styles["CellCenterBold"]),
        Spacer(1, 6),
        _box_table(
            [
                [_p("<b>Received From</b>", styles["Cell"]), _p("<b>Receipt Details</b>", styles["Cell"])],
                [
                    _p(
                        f"<b>{escape(payment.customer.name)}</b><br/>Mobile: {escape(payment.customer.mobile_number or '-')}",
                        styles["Cell"],
                    ),
                    _p(
                        "<br/>".join(
                            [
                                f"Receipt No: <b>{escape(payment.receipt_number)}</b>",
                                f"Receipt Date: {payment.payment_date.strftime('%d.%m.%Y')}",
                                f"Payment Method: {escape(payment.payment_method.value)}",
                                f"Reference: {escape(payment.transaction_reference or '-')}",
                                f"Status: <b>{escape(status_text)}</b>",
                            ]
                        ),
                        styles["Cell"],
                    ),
                ],
            ],
            [92 * mm, 91 * mm],
        ),
        Spacer(1, 10),
        _p(f"<b>Amount received now:</b> Rs. {_money(payment.total_amount)}", styles["CellBold"]),
        _p(f"<b>Amount in words:</b> {amount_to_indian_words(payment.total_amount)}", styles["Cell"]),
        Spacer(1, 12),
    ]

    for allocation in payment.allocations:
        invoice = allocation.invoice
        order_number = getattr(invoice, "buyer_order_number", None) or "-"
        elements.extend(
            [
                _p(
                    (
                        f"<b>INVOICE {escape(invoice.invoice_number)}</b>"
                        f"&nbsp;&nbsp; Date: {_date_text(invoice.invoice_date)}"
                        f"&nbsp;&nbsp; Buyer order: {escape(order_number)}"
                    ),
                    styles["CellBold"],
                ),
                Spacer(1, 5),
                purchased_items_table(invoice),
                invoice_value_table(invoice),
                Spacer(1, 6),
            ]
        )
        earlier_paid = paid_before(allocation)
        paying_now = Decimal(allocation.allocated_amount or 0)
        balance_after = max(
            Decimal(invoice.grand_total or 0) - earlier_paid - paying_now,
            Decimal("0"),
        )
        balance_table = Table(
            [
                [
                    _p("Invoice total", styles["CellCenter"]),
                    _p("Paid before", styles["CellCenter"]),
                    _p("Paid with this receipt", styles["CellCenter"]),
                    _p("Remaining after payment", styles["CellCenter"]),
                ],
                [
                    _p(f"<b>Rs. {_money(invoice.grand_total)}</b>", styles["CellCenterBold"]),
                    _p(f"<b>Rs. {_money(earlier_paid)}</b>", styles["CellCenterBold"]),
                    _p(f"<b>Rs. {_money(paying_now)}</b>", styles["CellCenterBold"]),
                    _p(f"<b>Rs. {_money(balance_after)}</b>", styles["CellCenterBold"]),
                ],
            ],
            colWidths=[width * 0.25] * 4,
        )
        balance_table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.8, colors.black),
                    ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f2f5f4")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        elements.extend([balance_table, Spacer(1, 12)])

    if not payment.allocations:
        elements.extend(
            [
                _box_table(
                    [
                        [
                            _p("<b>Customer advance</b>", styles["CellBold"]),
                            _p(
                                "This payment is not linked to a specific invoice.",
                                styles["Cell"],
                            ),
                            _p(
                                f"<b>Rs. {_money(payment.unallocated_amount)}</b>",
                                styles["CellRightBold"],
                            ),
                        ]
                    ],
                    [44 * mm, 94 * mm, 45 * mm],
                ),
                Spacer(1, 12),
            ]
        )

    if getattr(payment, "notes", None):
        elements.extend(
            [
                _p(f"<b>Notes:</b> {escape(payment.notes)}", styles["Cell"]),
                Spacer(1, 8),
            ]
        )

    elements.extend(
        [
            Spacer(1, 10),
            _box_table(
                [
                    [
                        _p("Received By<br/><br/>____________________", styles["CenterSmall"]),
                        _p("Customer Signature<br/><br/>____________________", styles["CenterSmall"]),
                        _p(
                            f"Authorized Signature<br/><br/>For {escape(company_name)}",
                            styles["CenterSmall"],
                        ),
                    ]
                ],
                [61 * mm, 61 * mm, 61 * mm],
            ),
        ]
    )
    doc.build(elements)
    return buffer.getvalue()
