from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.company_settings import get_company_settings, update_company_settings
from app.models import Base
from app.models.user import AuditLog
from app.schemas.company_settings import CompanySettingsUpdate
from app.services.invoice_service import is_intra_state_sale
from app.utils.gst import is_valid_indian_gstin, valid_indian_gstin


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False, future=True) as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_settings_are_seeded_from_environment_defaults_and_can_be_updated(db: Session):
    profile = get_company_settings(db=db, _=None)
    assert profile.id == 1
    assert profile.company_name

    updated = update_company_settings(
        CompanySettingsUpdate(
            company_name="New Crusher Company",
            company_address="New market address",
            company_gstin="27bebpp1879j1z2",
            company_state="Maharashtra",
            company_gst_state_code="27",
            company_bank_ifsc="exam0000123",
        ),
        db=db,
        user=None,
    )

    assert updated.company_name == "New Crusher Company"
    assert updated.company_gstin == "27BEBPP1879J1Z2"
    assert updated.company_bank_ifsc == "EXAM0000123"
    assert db.scalar(select(AuditLog).where(AuditLog.module == "company_settings"))

    reloaded = get_company_settings(db=db, _=None)
    assert reloaded.id == 1
    assert reloaded.company_address == "New market address"


def test_settings_reject_null_required_fields_and_invalid_gstin():
    with pytest.raises(ValidationError, match="cannot be null"):
        CompanySettingsUpdate(company_name=None)
    with pytest.raises(ValidationError, match="cannot be null"):
        CompanySettingsUpdate(company_address=None)
    with pytest.raises(ValidationError, match="valid 15-character"):
        CompanySettingsUpdate(company_gstin="29ABCDE1234F1Z5")


def test_indian_gstin_format_and_checksum_validation():
    assert is_valid_indian_gstin("27AAGCN6325G1ZF")
    assert valid_indian_gstin(" 27aagcn6325g1zf ") == "27AAGCN6325G1ZF"
    assert not is_valid_indian_gstin("27AAGCN6325G1ZA")
    assert not is_valid_indian_gstin("not-a-gstin")
    assert valid_indian_gstin("") is None


def test_tax_location_uses_persisted_company_profile_values():
    company = SimpleNamespace(
        company_gst_state_code="29",
        company_state="Karnataka",
    )
    customer_by_gstin = SimpleNamespace(
        gst_number="29ABCDE1234F1ZW",
        state="Maharashtra",
    )
    customer_by_state = SimpleNamespace(gst_number=None, state="Karnataka")

    assert is_intra_state_sale(customer_by_gstin, company) is True
    assert is_intra_state_sale(customer_by_state, company) is True

    invalid_gstin_uses_state = SimpleNamespace(
        gst_number="27ABCDE1234F1Z5",
        state="Karnataka",
    )
    assert is_intra_state_sale(invalid_gstin_uses_state, company) is True
