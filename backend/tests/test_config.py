import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_runtime_database_configuration_accepts_mysql_pymysql():
    configured = Settings(
        DATABASE_URL=(
            "mysql+pymysql://stone_app:password@127.0.0.1:3306/"
            "stone_creysher?charset=utf8mb4"
        ),
        _env_file=None,
    )

    assert configured.DATABASE_URL.startswith("mysql+pymysql://")


def test_runtime_database_configuration_rejects_sqlite():
    with pytest.raises(ValidationError, match="runtime requires MySQL"):
        Settings(
            DATABASE_URL="sqlite+pysqlite:///stone_dev.db",
            _env_file=None,
        )
