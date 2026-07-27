from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import get_current_user
from app.core.security import create_access_token, verify_password
from app.models.user import User, UserActivity
from app.schemas.auth import Token, UserOut

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=Token)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    user = db.scalar(select(User).where(User.username == form_data.username))
    if user is None or not verify_password(form_data.password, user.password_hash):
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    db.add(
        UserActivity(
            user_id=user.id,
            action="login",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    )
    db.commit()
    return Token(access_token=create_access_token(str(user.id)))


@router.post("/logout")
def logout(current_user: User = Depends(get_current_user)) -> dict[str, str]:
    return {"message": f"{current_user.username} logged out"}


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
