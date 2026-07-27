from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import get_current_user, require_roles
from app.models.enums import StockMovementType
from app.models.material import Material, StockMovement
from app.models.user import User
from app.schemas.material import MaterialCreate, MaterialOut, MaterialUpdate, StockUpdate
from app.services.audit import write_audit

router = APIRouter(prefix="/materials", tags=["Materials"])


def _duplicate_name_conflict() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="A material with this name already exists",
    )


def _material_name_exists(
    db: Session,
    name: str,
    *,
    exclude_material_id: int | None = None,
) -> bool:
    stmt = select(Material.id).where(func.lower(Material.name) == name.casefold())
    if exclude_material_id is not None:
        stmt = stmt.where(Material.id != exclude_material_id)
    return db.scalar(stmt) is not None


@router.get("", response_model=list[MaterialOut])
def list_materials(
    q: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[Material]:
    stmt = select(Material).order_by(Material.name)
    if not include_inactive:
        stmt = stmt.where(Material.is_active.is_(True))
    if q:
        stmt = stmt.where(Material.name.like(f"%{q}%"))
    return list(db.scalars(stmt).all())


@router.post("", response_model=MaterialOut)
def create_material(
    payload: MaterialCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("Admin", "Manager")),
) -> Material:
    if _material_name_exists(db, payload.name):
        raise _duplicate_name_conflict()

    material = Material(**payload.model_dump())
    try:
        db.add(material)
        db.flush()
        write_audit(db, user=user, action="create", module="material", record_id=material.id)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _duplicate_name_conflict() from exc

    db.refresh(material)
    return material


@router.put("/{material_id}", response_model=MaterialOut)
def update_material(
    material_id: int,
    payload: MaterialUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("Admin", "Manager")),
) -> Material:
    material = db.get(Material, material_id)
    if material is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")

    updates = payload.model_dump(exclude_unset=True)
    new_name = updates.get("name")
    if new_name is not None and _material_name_exists(
        db,
        new_name,
        exclude_material_id=material.id,
    ):
        raise _duplicate_name_conflict()

    for key, value in updates.items():
        setattr(material, key, value)
    write_audit(
        db,
        user=user,
        action="update",
        module="material",
        record_id=material.id,
        new_value=payload.model_dump(exclude_unset=True, mode="json"),
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _duplicate_name_conflict() from exc

    db.refresh(material)
    return material


@router.delete("/{material_id}", response_model=MaterialOut)
def deactivate_material(
    material_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("Admin", "Manager")),
) -> Material:
    material = db.get(Material, material_id)
    if material is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")
    material.is_active = False
    write_audit(db, user=user, action="deactivate", module="material", record_id=material.id)
    db.commit()
    db.refresh(material)
    return material


@router.post("/{material_id}/stock", response_model=MaterialOut)
def update_stock(
    material_id: int,
    payload: StockUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("Admin", "Manager", "Operator")),
) -> Material:
    material = db.get(Material, material_id)
    if material is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")

    current_quantity = Decimal(material.stock_quantity)
    if payload.movement_type == StockMovementType.OUT:
        if payload.quantity > current_quantity:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Cannot remove {payload.quantity} {material.unit}; "
                    f"only {current_quantity} {material.unit} is available"
                ),
            )
        material.stock_quantity = current_quantity - payload.quantity
    elif payload.movement_type == StockMovementType.IN:
        material.stock_quantity = current_quantity + payload.quantity
    else:  # StockUpdate rejects unsupported movement types; this is defensive.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Stock movement must be IN or OUT",
        )

    db.add(
        StockMovement(
            material_id=material.id,
            movement_type=payload.movement_type,
            quantity=payload.quantity,
            reference_number=payload.reference_number,
            movement_date=datetime.now(timezone.utc),
            created_by=user.id,
        )
    )
    write_audit(db, user=user, action="stock_update", module="material", record_id=material.id)
    db.commit()
    db.refresh(material)
    return material
