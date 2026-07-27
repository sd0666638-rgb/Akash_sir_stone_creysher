from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.materials import (
    create_material,
    deactivate_material,
    update_material,
    update_stock,
)
from app.models.enums import StockMovementType
from app.schemas.material import MaterialCreate, MaterialUpdate, StockUpdate


def test_material_schema_validates_rates_stock_gst_name_and_unit():
    material = MaterialCreate(name="  Crusher Sand  ", unit=" TON ")

    assert material.name == "Crusher Sand"
    assert material.unit == "TON"

    invalid_payloads = [
        {"name": "Stone", "gst_percentage": Decimal("100.01")},
        {"name": "Stone", "stock_quantity": Decimal("-0.001")},
        {"name": "Stone", "minimum_stock": Decimal("-0.001")},
    ]
    for payload in invalid_payloads:
        with pytest.raises(ValidationError):
            MaterialCreate(**payload)

    with pytest.raises(ValidationError):
        MaterialUpdate(name=" ")
    with pytest.raises(ValidationError):
        MaterialUpdate(unit="")
    with pytest.raises(ValidationError):
        MaterialUpdate(name=None)
    with pytest.raises(ValidationError):
        MaterialUpdate(stock_quantity=Decimal("-1"))


def test_stock_schema_accepts_only_positive_in_and_out_movements():
    stock_in = StockUpdate(movement_type="IN", quantity=Decimal("1.250"))
    stock_out = StockUpdate(movement_type="OUT", quantity=Decimal("0.001"))

    assert stock_in.movement_type == StockMovementType.IN
    assert stock_out.movement_type == StockMovementType.OUT

    for movement_type, quantity in [
        ("IN", Decimal("0")),
        ("OUT", Decimal("-1")),
        ("ADJUSTMENT", Decimal("1")),
    ]:
        with pytest.raises(ValidationError):
            StockUpdate(movement_type=movement_type, quantity=quantity)


def test_create_material_returns_clear_conflict_for_duplicate_name():
    db = MagicMock(spec=Session)
    db.scalar.return_value = 42

    with pytest.raises(HTTPException) as error:
        create_material(
            MaterialCreate(name="Stone Dust"),
            db=db,
            user=SimpleNamespace(id=1),
        )

    assert error.value.status_code == 409
    assert error.value.detail == "A material with this name already exists"
    db.add.assert_not_called()


def test_update_material_returns_clear_conflict_for_duplicate_name():
    db = MagicMock(spec=Session)
    db.get.return_value = SimpleNamespace(id=1, name="Stone Dust", is_active=True)
    db.scalar.return_value = 2

    with pytest.raises(HTTPException) as error:
        update_material(
            1,
            MaterialUpdate(name="M-Sand"),
            db=db,
            user=SimpleNamespace(id=1),
        )

    assert error.value.status_code == 409
    assert error.value.detail == "A material with this name already exists"
    db.commit.assert_not_called()


def test_stock_out_rejects_quantity_above_available_stock():
    db = MagicMock(spec=Session)
    material = SimpleNamespace(
        id=1,
        name="M-Sand",
        unit="TON",
        stock_quantity=Decimal("5.000"),
    )
    db.get.return_value = material

    with pytest.raises(HTTPException) as error:
        update_stock(
            1,
            StockUpdate(movement_type="OUT", quantity=Decimal("5.001")),
            db=db,
            user=SimpleNamespace(id=1),
        )

    assert error.value.status_code == 409
    assert "only 5.000 TON is available" in error.value.detail
    assert material.stock_quantity == Decimal("5.000")
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_stock_in_and_out_update_the_available_quantity():
    db = MagicMock(spec=Session)
    material = SimpleNamespace(
        id=1,
        name="M-Sand",
        unit="TON",
        stock_quantity=Decimal("5.000"),
    )
    db.get.return_value = material
    user = SimpleNamespace(id=1)

    update_stock(
        1,
        StockUpdate(movement_type="IN", quantity=Decimal("2.500")),
        db=db,
        user=user,
    )
    assert material.stock_quantity == Decimal("7.500")

    update_stock(
        1,
        StockUpdate(movement_type="OUT", quantity=Decimal("1.250")),
        db=db,
        user=user,
    )
    assert material.stock_quantity == Decimal("6.250")
    assert db.commit.call_count == 2


def test_delete_material_remains_a_soft_delete():
    db = MagicMock(spec=Session)
    material = SimpleNamespace(id=1, name="M-Sand", is_active=True)
    db.get.return_value = material

    result = deactivate_material(
        1,
        db=db,
        user=SimpleNamespace(id=1),
    )

    assert result is material
    assert material.is_active is False
    db.commit.assert_called_once()
