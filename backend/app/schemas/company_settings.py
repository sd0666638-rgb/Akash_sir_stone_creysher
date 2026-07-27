from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel
from app.utils.gst import normalize_gstin, is_valid_indian_gstin


class CompanySettingsUpdate(BaseModel):
    company_name: str | None = Field(default=None, min_length=2, max_length=180)
    company_address: str | None = Field(default=None, min_length=1, max_length=2000)
    company_phone: str | None = Field(default=None, max_length=30)
    company_gstin: str | None = Field(default=None, max_length=15)
    company_state: str | None = Field(default=None, max_length=100)
    company_gst_state_code: str | None = Field(default=None, max_length=2)
    company_jurisdiction: str | None = Field(default=None, max_length=100)
    company_bank_name: str | None = Field(default=None, max_length=160)
    company_bank_account: str | None = Field(default=None, max_length=80)
    company_bank_ifsc: str | None = Field(default=None, max_length=20)
    company_bank_branch: str | None = Field(default=None, max_length=160)

    @field_validator("company_name", "company_address", mode="before")
    @classmethod
    def strip_required_text(cls, value):
        if value is None:
            raise ValueError("Value cannot be null")
        text = str(value).strip()
        if not text:
            raise ValueError("Value cannot be blank")
        return text

    @field_validator(
        "company_phone",
        "company_state",
        "company_jurisdiction",
        "company_bank_name",
        "company_bank_account",
        "company_bank_branch",
        mode="before",
    )
    @classmethod
    def strip_optional_text(cls, value):
        if value is None:
            return None
        return str(value).strip() or None

    @field_validator("company_gstin", mode="before")
    @classmethod
    def validate_company_gstin(cls, value):
        if value is None or not str(value).strip():
            return None
        gstin = normalize_gstin(str(value))
        if not is_valid_indian_gstin(gstin):
            raise ValueError("Enter a valid 15-character Indian GSTIN")
        return gstin

    @field_validator("company_gst_state_code", mode="before")
    @classmethod
    def validate_state_code(cls, value):
        if value is None or not str(value).strip():
            return None
        code = str(value).strip()
        if len(code) == 1:
            code = code.zfill(2)
        if len(code) != 2 or not code.isdigit() or code == "00":
            raise ValueError("GST state code must be two digits")
        return code

    @field_validator("company_bank_ifsc", mode="before")
    @classmethod
    def normalize_ifsc(cls, value):
        if value is None or not str(value).strip():
            return None
        return str(value).strip().upper()


class CompanySettingsOut(ORMModel):
    id: int
    company_name: str
    company_address: str
    company_phone: str | None
    company_gstin: str | None
    company_state: str | None
    company_gst_state_code: str | None
    company_jurisdiction: str | None
    company_bank_name: str | None
    company_bank_account: str | None
    company_bank_ifsc: str | None
    company_bank_branch: str | None
    created_at: datetime
    updated_at: datetime
