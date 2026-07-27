from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import get_current_user, require_roles
from app.models.company_settings import CompanySettings
from app.models.user import User
from app.schemas.company_settings import CompanySettingsOut, CompanySettingsUpdate
from app.services.audit import write_audit
from app.services.company_settings import ensure_company_settings

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("/company", response_model=CompanySettingsOut)
def get_company_settings(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> CompanySettings:
    profile, created = ensure_company_settings(db)
    if created:
        db.commit()
        db.refresh(profile)
    return profile


@router.put("/company", response_model=CompanySettingsOut)
def update_company_settings(
    payload: CompanySettingsUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("Admin", "Manager")),
) -> CompanySettings:
    profile, _ = ensure_company_settings(db)
    previous_value = CompanySettingsOut.model_validate(profile).model_dump(mode="json")
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(profile, key, value)

    write_audit(
        db,
        user=user,
        action="update",
        module="company_settings",
        record_id=profile.id,
        previous_value=previous_value,
        new_value=payload.model_dump(exclude_unset=True, mode="json"),
    )
    db.commit()
    db.refresh(profile)
    return profile
