from types import SimpleNamespace
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.invoice import InvoiceCreate, InvoiceItemCreate
from app.services.invoice_service import generate_invoice_number, is_intra_state_sale


def test_tax_location_uses_gst_state_code_before_state_name():
    same_state = SimpleNamespace(gst_number="27AAGCN6325G1ZF", state="Karnataka")
    other_state = SimpleNamespace(gst_number="29ABCDE1234F1ZW", state="Maharashtra")

    assert is_intra_state_sale(same_state) is True
    assert is_intra_state_sale(other_state) is False


def test_tax_location_falls_back_to_customer_state():
    same_state = SimpleNamespace(gst_number=None, state=" Maharashtra ")
    other_state = SimpleNamespace(gst_number=None, state="Karnataka")

    assert is_intra_state_sale(same_state) is True
    assert is_intra_state_sale(other_state) is False


def test_invoice_number_uses_the_unique_database_id():
    assert generate_invoice_number(date(2025, 12, 22), 42) == "INV-20251222-000042"


def test_invoice_schema_rejects_excessive_rounding_and_gst():
    with pytest.raises(ValidationError):
        InvoiceCreate(
            invoice_date=date.today(),
            customer_id=1,
            round_off=Decimal("-1.01"),
            items=[
                InvoiceItemCreate(
                    material_name="Stone",
                    quantity=Decimal("1"),
                    rate=Decimal("100"),
                    gst_percentage=Decimal("5"),
                )
            ],
        )

    with pytest.raises(ValidationError):
        InvoiceItemCreate(
            material_name="Stone",
            quantity=Decimal("1"),
            rate=Decimal("100"),
            gst_percentage=Decimal("100.01"),
        )
