from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.company_settings import CompanySettings


def default_company_settings() -> dict[str, object]:
    return {
        "id": 1,
        "company_name": settings.COMPANY_NAME,
        "company_address": settings.COMPANY_ADDRESS,
        "company_phone": settings.COMPANY_PHONE.strip() or None,
        "company_gstin": settings.COMPANY_GSTIN.strip().upper() or None,
        "company_state": settings.COMPANY_STATE.strip() or None,
        "company_gst_state_code": settings.COMPANY_GST_STATE_CODE.strip() or None,
        "company_jurisdiction": settings.COMPANY_JURISDICTION.strip() or None,
        "company_bank_name": settings.COMPANY_BANK_NAME.strip() or None,
        "company_bank_account": settings.COMPANY_BANK_ACCOUNT.strip() or None,
        "company_bank_ifsc": settings.COMPANY_BANK_IFSC.strip().upper() or None,
        "company_bank_branch": settings.COMPANY_BANK_BRANCH.strip() or None,
    }


def load_company_settings(db: Session) -> CompanySettings:
    """Load persisted settings, falling back to an unpersisted default profile."""

    profile = db.get(CompanySettings, 1)
    return profile if profile is not None else CompanySettings(**default_company_settings())


def ensure_company_settings(db: Session) -> tuple[CompanySettings, bool]:
    profile = db.get(CompanySettings, 1)
    if profile is not None:
        return profile, False

    profile = CompanySettings(**default_company_settings())
    db.add(profile)
    db.flush()
    return profile, True
