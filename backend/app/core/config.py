from functools import lru_cache
from typing import List

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Stone Crusher ERP"
    ENVIRONMENT: str = "development"
    SECRET_KEY: str = "change-this-secret-before-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    DATABASE_URL: str = (
        "mysql+pymysql://stone:stone_password@db:3306/stone_creysher?charset=utf8mb4"
    )
    BACKEND_CORS_ORIGINS: List[str | AnyHttpUrl] = ["http://localhost:5173"]
    COMPANY_NAME: str = "Radhya Construction"
    COMPANY_ADDRESS: str = "Crusher and construction material supplier"
    COMPANY_PHONE: str = ""
    COMPANY_GSTIN: str = ""
    COMPANY_STATE: str = ""
    COMPANY_GST_STATE_CODE: str = ""
    COMPANY_JURISDICTION: str = ""
    COMPANY_BANK_NAME: str = ""
    COMPANY_BANK_ACCOUNT: str = ""
    COMPANY_BANK_IFSC: str = ""
    COMPANY_BANK_BRANCH: str = ""
    COMPANY_PAYMENT_TERMS_DAYS: int = 5
    COMPANY_LATE_INTEREST_PERCENT: int = 18
    COMPANY_LOGO_PATH: str = ""
    DOCUMENT_FILE_PREFIX: str = "Radhya Construction"
    DOCUMENT_FILENAME_DOUBLE_DOT: bool = True
    FIRST_ADMIN_USERNAME: str = "admin"
    FIRST_ADMIN_PASSWORD: str = "admin123"
    FIRST_ADMIN_FULL_NAME: str = "System Administrator"
    CHEQUE_COLLECTION_REQUIRES_CLEARANCE: bool = True

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        case_sensitive=True,
        enable_decoding=False,
        extra="ignore",
    )

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("DATABASE_URL")
    @classmethod
    def require_mysql_runtime_database(cls, value: str) -> str:
        database_url = value.strip()
        if not database_url.casefold().startswith("mysql+pymysql://"):
            raise ValueError(
                "The application runtime requires MySQL through the PyMySQL driver "
                "(DATABASE_URL must start with mysql+pymysql://)"
            )
        return database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
