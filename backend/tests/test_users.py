import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api.users import create_user, list_roles, list_users
from app.core.security import verify_password
from app.models import Base
from app.models.user import AuditLog, Role
from app.schemas.auth import UserCreate


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False, future=True) as session:
        session.add_all(
            [
                Role(name="Admin", description="Administrator"),
                Role(name="Manager", description="Manager"),
                Role(name="Operator", description="Operator"),
                Role(name="Accountant", description="Accountant"),
            ]
        )
        session.commit()
        yield session
    engine.dispose()


def test_admin_can_create_and_list_user(db: Session):
    created = create_user(
        UserCreate(
            username="  Counter.Operator ",
            full_name="  Counter   Operator ",
            password="secure-pass-123",
            role_names=["Operator"],
        ),
        db=db,
        current_user=None,
    )

    assert created.username == "counter.operator"
    assert created.full_name == "Counter Operator"
    assert verify_password("secure-pass-123", created.password_hash)
    assert [role.name for role in created.roles] == ["Operator"]
    assert [user.id for user in list_users(db=db, _=None)] == [created.id]
    assert {role.name for role in list_roles(db=db, _=None)} == {
        "Admin",
        "Manager",
        "Operator",
        "Accountant",
    }
    assert db.scalar(select(AuditLog).where(AuditLog.module == "user"))


def test_user_creation_rejects_duplicate_username_and_unknown_role(db: Session):
    payload = UserCreate(
        username="operator",
        full_name="First Operator",
        password="secure-pass-123",
        role_names=["Operator"],
    )
    create_user(payload, db=db, current_user=None)

    with pytest.raises(HTTPException, match="already in use") as duplicate:
        create_user(payload, db=db, current_user=None)
    assert duplicate.value.status_code == 409

    with pytest.raises(HTTPException, match="Unknown role") as unknown_role:
        create_user(
            UserCreate(
                username="unknown-role",
                full_name="Unknown Role",
                password="secure-pass-123",
                role_names=["Supervisor"],
            ),
            db=db,
            current_user=None,
        )
    assert unknown_role.value.status_code == 400


def test_user_schema_requires_safe_username_and_password():
    with pytest.raises(ValidationError):
        UserCreate(
            username="not allowed!",
            full_name="Invalid User",
            password="secure-pass-123",
            role_names=["Operator"],
        )
    with pytest.raises(ValidationError):
        UserCreate(
            username="valid-user",
            full_name="Invalid User",
            password="short",
            role_names=["Operator"],
        )
