from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import require_roles
from app.core.security import get_password_hash
from app.models.user import Role, User
from app.schemas.auth import RoleOut, UserCreate, UserOut
from app.services.audit import write_audit

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("Admin")),
) -> list[User]:
    return list(db.scalars(select(User).order_by(User.full_name, User.username)).all())


@router.get("/roles", response_model=list[RoleOut])
def list_roles(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("Admin")),
) -> list[Role]:
    return list(db.scalars(select(Role).order_by(Role.id)).all())


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
) -> User:
    existing = db.scalar(
        select(User).where(func.lower(User.username) == payload.username.lower())
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That username is already in use",
        )

    roles = list(db.scalars(select(Role).where(Role.name.in_(payload.role_names))).all())
    roles_by_name = {role.name: role for role in roles}
    missing_roles = sorted(set(payload.role_names) - set(roles_by_name))
    if missing_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown role: {', '.join(missing_roles)}",
        )

    user = User(
        username=payload.username,
        full_name=payload.full_name,
        password_hash=get_password_hash(payload.password),
        is_active=True,
        roles=[roles_by_name[name] for name in payload.role_names],
    )
    db.add(user)
    db.flush()
    write_audit(
        db,
        user=current_user,
        action="create",
        module="user",
        record_id=user.id,
        new_value={
            "username": user.username,
            "full_name": user.full_name,
            "roles": payload.role_names,
        },
    )
    db.commit()
    db.refresh(user)
    return user
