from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.company_settings import CompanySettings
from app.models.material import Material
from app.models.user import Role, User
from app.services.company_settings import default_company_settings

ROLE_NAMES = ["Admin", "Manager", "Operator", "Accountant"]
DEFAULT_MATERIALS = [
    ("Stone Dust", "25171090", "TON", 650, 500, 5),
    ("M-Sand", "25171090", "TON", 850, 650, 5),
    ("40mm Aggregate", "25171090", "TON", 900, 700, 5),
    ("20mm Aggregate", "25171090", "TON", 950, 750, 5),
    ("10mm Aggregate", "25171090", "TON", 980, 780, 5),
    ("Gitti", "25171090", "TON", 920, 710, 5),
    ("Crusher Sand", "25171090", "TON", 780, 590, 5),
    ("Metal", "25171090", "TON", 1100, 850, 5),
]


def bootstrap_database(db: Session) -> None:
    if db.get(CompanySettings, 1) is None:
        db.add(CompanySettings(**default_company_settings()))

    roles = {}
    for name in ROLE_NAMES:
        role = db.scalar(select(Role).where(Role.name == name))
        if role is None:
            role = Role(name=name, description=f"{name} role")
            db.add(role)
        roles[name] = role

    admin = db.scalar(select(User).where(User.username == settings.FIRST_ADMIN_USERNAME))
    if admin is None:
        admin = User(
            username=settings.FIRST_ADMIN_USERNAME,
            full_name=settings.FIRST_ADMIN_FULL_NAME,
            password_hash=get_password_hash(settings.FIRST_ADMIN_PASSWORD),
            is_active=True,
        )
        admin.roles.append(roles["Admin"])
        db.add(admin)

    for name, hsn_code, unit, selling_rate, purchase_rate, gst_percentage in DEFAULT_MATERIALS:
        exists = db.scalar(select(Material).where(Material.name == name))
        if exists is None:
            db.add(
                Material(
                    name=name,
                    hsn_code=hsn_code,
                    unit=unit,
                    selling_rate=selling_rate,
                    purchase_rate=purchase_rate,
                    gst_percentage=gst_percentage,
                    stock_quantity=0,
                    minimum_stock=0,
                    is_active=True,
                )
            )
        elif not exists.hsn_code:
            exists.hsn_code = hsn_code

    db.commit()
