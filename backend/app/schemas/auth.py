from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import ORMModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RoleOut(ORMModel):
    id: int
    name: str


class UserOut(ORMModel):
    id: int
    username: str
    full_name: str
    is_active: bool
    roles: list[RoleOut] = []


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80, pattern=r"^[a-z0-9._-]+$")
    full_name: str = Field(min_length=2, max_length=150)
    password: str = Field(min_length=8, max_length=128)
    role_names: list[str] = Field(min_length=1, max_length=4)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value):
        return str(value or "").strip().lower()

    @field_validator("full_name", mode="before")
    @classmethod
    def normalize_full_name(cls, value):
        return " ".join(str(value or "").split())

    @model_validator(mode="after")
    def require_unique_roles(self):
        if len(self.role_names) != len(set(self.role_names)):
            raise ValueError("Each role can be assigned only once")
        return self
