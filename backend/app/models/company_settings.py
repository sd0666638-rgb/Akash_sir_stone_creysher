from sqlalchemy import CheckConstraint, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class CompanySettings(TimestampMixin, Base):
    """Persistent singleton containing the seller details used by the ERP."""

    __tablename__ = "company_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_company_settings_singleton_id"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        default=1,
        autoincrement=False,
    )
    company_name: Mapped[str] = mapped_column(String(180), nullable=False)
    company_address: Mapped[str] = mapped_column(Text, nullable=False)
    company_phone: Mapped[str | None] = mapped_column(String(30))
    company_gstin: Mapped[str | None] = mapped_column(String(15))
    company_state: Mapped[str | None] = mapped_column(String(100))
    company_gst_state_code: Mapped[str | None] = mapped_column(String(2))
    company_jurisdiction: Mapped[str | None] = mapped_column(String(100))
    company_bank_name: Mapped[str | None] = mapped_column(String(160))
    company_bank_account: Mapped[str | None] = mapped_column(String(80))
    company_bank_ifsc: Mapped[str | None] = mapped_column(String(20))
    company_bank_branch: Mapped[str | None] = mapped_column(String(160))
