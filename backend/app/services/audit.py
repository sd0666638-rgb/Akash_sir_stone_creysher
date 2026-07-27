from typing import Any

from sqlalchemy.orm import Session

from app.models.user import AuditLog, User


def write_audit(
    db: Session,
    *,
    user: User | None,
    action: str,
    module: str,
    record_id: str | int,
    previous_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
    ip_address: str | None = None,
    notes: str | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user.id if user else None,
            action=action,
            module=module,
            record_id=str(record_id),
            previous_value=previous_value,
            new_value=new_value,
            ip_address=ip_address,
            notes=notes,
        )
    )
