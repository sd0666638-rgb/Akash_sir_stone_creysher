from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import case, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.company_settings import CompanySettings
from app.models.customer import Customer
from app.models.enums import LedgerTransactionType, PaymentMethod, StockMovementType
from app.models.invoice import BuyerOrderSequence, Invoice, InvoiceItem
from app.models.material import Material, StockMovement
from app.models.user import User
from app.schemas.invoice import InvoiceCreate, InvoiceItemCreate
from app.schemas.payment import PaymentAllocationCreate, PaymentCreate
from app.services.accounting import refresh_customer_balances, refresh_invoice_payment_state
from app.services.audit import write_audit
from app.services.calculations import calculate_invoice_totals, calculate_line, money
from app.services.company_settings import load_company_settings
from app.services.ledger_service import append_ledger_entry
from app.utils.gst import valid_indian_gstin


def is_intra_state_sale(
    customer: Customer,
    company: CompanySettings | None = None,
) -> bool:
    company_code = (
        (company.company_gst_state_code or "").strip()
        if company is not None
        else settings.COMPANY_GST_STATE_CODE.strip()
    )
    customer_gstin = valid_indian_gstin(customer.gst_number) or ""
    customer_code = (
        customer_gstin[:2]
        if len(customer_gstin) >= 2 and customer_gstin[:2].isdigit()
        else ""
    )
    if company_code and customer_code:
        return company_code == customer_code

    configured_state = (
        company.company_state or ""
        if company is not None
        else settings.COMPANY_STATE
    )
    company_state = " ".join(configured_state.casefold().split())
    customer_state = " ".join((customer.state or "").casefold().split())
    if company_state and customer_state:
        return company_state == customer_state

    # Preserve the existing intra-state behavior when customer tax location
    # is incomplete, rather than guessing an interstate tax.
    return True


def generate_invoice_number(invoice_date, invoice_id: int) -> str:
    return f"{invoice_date.strftime('INV-%Y%m%d')}-{invoice_id:06d}"


def format_buyer_order_number(sequence_number: int, invoice_date) -> str:
    return f"{sequence_number}-{invoice_date.strftime('%d%m%Y')}"


def preview_buyer_order_number(db: Session, invoice_date) -> str:
    last_number = db.scalar(
        select(BuyerOrderSequence.last_number).where(
            BuyerOrderSequence.sequence_date == invoice_date
        )
    )
    return format_buyer_order_number(int(last_number or 0) + 1, invoice_date)


def reserve_buyer_order_number(db: Session, invoice_date) -> str:
    """Atomically reserve the next daily buyer order number."""

    db.flush()
    dialect_name = db.get_bind().dialect.name
    values = {"sequence_date": invoice_date, "last_number": 1}

    if dialect_name == "mysql":
        statement = mysql_insert(BuyerOrderSequence).values(**values)
        statement = statement.on_duplicate_key_update(
            last_number=BuyerOrderSequence.last_number + 1
        )
        db.execute(statement)
    elif dialect_name == "sqlite":
        statement = sqlite_insert(BuyerOrderSequence).values(**values)
        statement = statement.on_conflict_do_update(
            index_elements=[BuyerOrderSequence.sequence_date],
            set_={"last_number": BuyerOrderSequence.last_number + 1},
        )
        db.execute(statement)
    else:
        sequence = db.scalar(
            select(BuyerOrderSequence)
            .where(BuyerOrderSequence.sequence_date == invoice_date)
            .with_for_update()
        )
        if sequence is None:
            sequence = BuyerOrderSequence(
                sequence_date=invoice_date,
                last_number=1,
            )
            db.add(sequence)
        else:
            sequence.last_number += 1
        db.flush()

    sequence_number = db.scalar(
        select(BuyerOrderSequence.last_number).where(
            BuyerOrderSequence.sequence_date == invoice_date
        )
    )
    return format_buyer_order_number(int(sequence_number), invoice_date)


def _manual_buyer_order_sequence(
    buyer_order_number: str, invoice_date
) -> int | None:
    suffix = f"-{invoice_date.strftime('%d%m%Y')}"
    if not buyer_order_number.endswith(suffix):
        return None
    prefix = buyer_order_number[: -len(suffix)]
    if not prefix.isdigit() or int(prefix) < 1:
        return None
    return int(prefix)


def _advance_buyer_order_sequence(
    db: Session,
    invoice_date,
    sequence_number: int,
) -> None:
    """Keep automatic numbering ahead of matching manually entered values."""

    db.flush()
    dialect_name = db.get_bind().dialect.name
    values = {
        "sequence_date": invoice_date,
        "last_number": sequence_number,
    }
    floor_expression = case(
        (
            BuyerOrderSequence.last_number < sequence_number,
            sequence_number,
        ),
        else_=BuyerOrderSequence.last_number,
    )

    if dialect_name == "mysql":
        statement = mysql_insert(BuyerOrderSequence).values(**values)
        statement = statement.on_duplicate_key_update(
            last_number=floor_expression
        )
        db.execute(statement)
    elif dialect_name == "sqlite":
        statement = sqlite_insert(BuyerOrderSequence).values(**values)
        statement = statement.on_conflict_do_update(
            index_elements=[BuyerOrderSequence.sequence_date],
            set_={"last_number": floor_expression},
        )
        db.execute(statement)
    else:
        sequence = db.scalar(
            select(BuyerOrderSequence)
            .where(BuyerOrderSequence.sequence_date == invoice_date)
            .with_for_update()
        )
        if sequence is None:
            db.add(
                BuyerOrderSequence(
                    sequence_date=invoice_date,
                    last_number=sequence_number,
                )
            )
        elif sequence.last_number < sequence_number:
            sequence.last_number = sequence_number
        db.flush()


def _aggregate_material_quantities(
    items: list[InvoiceItemCreate],
) -> dict[int, Decimal]:
    quantities: dict[int, Decimal] = defaultdict(Decimal)
    for item in items:
        if item.material_id is not None:
            quantities[item.material_id] += item.quantity
    return dict(quantities)


def _lock_invoice_materials(
    db: Session,
    requested_quantities: dict[int, Decimal],
) -> dict[int, Material]:
    if not requested_quantities:
        return {}

    material_ids = sorted(requested_quantities)
    materials = list(
        db.scalars(
            select(Material)
            .where(
                Material.id.in_(material_ids),
                Material.is_active.is_(True),
            )
            .order_by(Material.id)
            .with_for_update()
        ).all()
    )
    materials_by_id = {material.id: material for material in materials}

    for material_id in material_ids:
        if material_id not in materials_by_id:
            material = db.get(Material, material_id)
            if material is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Material {material_id} not found",
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Material {material.name} is inactive",
            )

        material = materials_by_id[material_id]
        requested = requested_quantities[material_id]
        available = Decimal(material.stock_quantity)
        if requested > available:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Insufficient stock for {material.name}: "
                    f"requested {requested} {material.unit}, "
                    f"available {available} {material.unit}"
                ),
            )

    return materials_by_id


def _deduct_invoice_stock(
    db: Session,
    *,
    invoice: Invoice,
    materials_by_id: dict[int, Material],
    requested_quantities: dict[int, Decimal],
    user: User | None,
) -> None:
    movement_date = datetime.now(timezone.utc)
    for material_id in sorted(requested_quantities):
        quantity = requested_quantities[material_id]
        material = materials_by_id[material_id]
        material.stock_quantity = Decimal(material.stock_quantity) - quantity
        db.add(
            StockMovement(
                material_id=material.id,
                movement_type=StockMovementType.OUT,
                quantity=quantity,
                reference_number=invoice.invoice_number,
                movement_date=movement_date,
                created_by=user.id if user else None,
            )
        )


def restore_invoice_stock(
    db: Session,
    *,
    invoice: Invoice,
    user: User | None,
) -> dict[int, Decimal]:
    cancellation_reference = f"{invoice.invoice_number}-CANCEL"
    movements = list(
        db.scalars(
            select(StockMovement)
            .where(
                StockMovement.reference_number.in_(
                    [invoice.invoice_number, cancellation_reference]
                ),
                StockMovement.movement_type.in_(
                    [StockMovementType.OUT, StockMovementType.IN]
                ),
            )
            .order_by(StockMovement.material_id, StockMovement.id)
        ).all()
    )

    deducted: dict[int, Decimal] = defaultdict(Decimal)
    already_restored: dict[int, Decimal] = defaultdict(Decimal)
    for movement in movements:
        if (
            movement.reference_number == invoice.invoice_number
            and movement.movement_type == StockMovementType.OUT
        ):
            deducted[movement.material_id] += movement.quantity
        elif (
            movement.reference_number == cancellation_reference
            and movement.movement_type == StockMovementType.IN
        ):
            already_restored[movement.material_id] += movement.quantity

    quantities_to_restore = {
        material_id: quantity - already_restored[material_id]
        for material_id, quantity in deducted.items()
        if quantity > already_restored[material_id]
    }
    if not quantities_to_restore:
        return {}

    material_ids = sorted(quantities_to_restore)
    materials = list(
        db.scalars(
            select(Material)
            .where(Material.id.in_(material_ids))
            .order_by(Material.id)
            .with_for_update()
        ).all()
    )
    materials_by_id = {material.id: material for material in materials}
    missing_ids = [material_id for material_id in material_ids if material_id not in materials_by_id]
    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot restore stock for missing material {missing_ids[0]}",
        )

    movement_date = datetime.now(timezone.utc)
    for material_id in material_ids:
        quantity = quantities_to_restore[material_id]
        material = materials_by_id[material_id]
        material.stock_quantity = Decimal(material.stock_quantity) + quantity
        db.add(
            StockMovement(
                material_id=material.id,
                movement_type=StockMovementType.IN,
                quantity=quantity,
                reference_number=cancellation_reference,
                movement_date=movement_date,
                created_by=user.id if user else None,
            )
        )

    return quantities_to_restore


def create_invoice(db: Session, payload: InvoiceCreate, user: User | None) -> Invoice:
    customer = db.get(Customer, payload.customer_id)
    if customer is None or not customer.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    requested_quantities = _aggregate_material_quantities(payload.items)
    materials_by_id = _lock_invoice_materials(db, requested_quantities)

    item_rows = []
    for item in payload.items:
        material = materials_by_id.get(item.material_id) if item.material_id is not None else None
        line = calculate_line(
            quantity=item.quantity,
            rate=item.rate,
            gst_percentage=item.gst_percentage,
            discount_percentage=item.discount_percentage,
        )
        snapshot = {
            "material_name": material.name if material else item.material_name,
            "dispatch_date": item.dispatch_date or payload.invoice_date,
            "receipt_number": item.receipt_number or payload.delivery_note,
            "hsn_code": item.hsn_code or (material.hsn_code if material else None),
            "vehicle_number": item.vehicle_number or payload.vehicle_number,
        }
        item_rows.append((item, line, snapshot))

    company = load_company_settings(db)
    totals = calculate_invoice_totals(
        [line for _, line, _ in item_rows],
        transport_charges=payload.transport_charges,
        loading_charges=payload.loading_charges,
        other_charges=payload.other_charges,
        round_off=payload.round_off,
        intra_state=is_intra_state_sale(customer, company),
    )
    if totals["grand_total"] <= Decimal("0"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invoice grand total must be greater than zero",
        )

    buyer_order_number = (payload.buyer_order_number or "").strip()
    if buyer_order_number:
        manual_sequence = _manual_buyer_order_sequence(
            buyer_order_number,
            payload.invoice_date,
        )
        if manual_sequence is not None:
            _advance_buyer_order_sequence(
                db,
                payload.invoice_date,
                manual_sequence,
            )
    else:
        buyer_order_number = reserve_buyer_order_number(
            db,
            payload.invoice_date,
        )

    invoice = Invoice(
        # A unique placeholder allows MySQL to assign the primary key first;
        # the final document number then derives from that collision-free key.
        invoice_number=f"TMP-{uuid4().hex}",
        invoice_date=payload.invoice_date,
        customer_id=payload.customer_id,
        delivery_note=payload.delivery_note,
        other_reference=payload.other_reference,
        buyer_order_number=buyer_order_number,
        vehicle_number=payload.vehicle_number,
        driver_name=payload.driver_name,
        transporter=payload.transporter,
        delivery_location=payload.delivery_location,
        payment_type=payload.payment_type,
        credit_period_days=0,
        notes=payload.notes,
        transport_charges=money(payload.transport_charges),
        loading_charges=money(payload.loading_charges),
        other_charges=money(payload.other_charges),
        round_off=money(payload.round_off),
        created_by=user.id if user else None,
        **totals,
    )
    invoice.remaining_amount = invoice.grand_total
    db.add(invoice)
    db.flush()
    invoice.invoice_number = generate_invoice_number(invoice.invoice_date, invoice.id)
    db.flush()
    _deduct_invoice_stock(
        db,
        invoice=invoice,
        materials_by_id=materials_by_id,
        requested_quantities=requested_quantities,
        user=user,
    )

    for item, line, snapshot in item_rows:
        db.add(
            InvoiceItem(
                invoice_id=invoice.id,
                material_id=item.material_id,
                quantity=item.quantity,
                unit=item.unit,
                rate=item.rate,
                gst_percentage=item.gst_percentage,
                discount_percentage=item.discount_percentage,
                **snapshot,
                **line,
            )
        )

    append_ledger_entry(
        db,
        customer_id=invoice.customer_id,
        transaction_date=invoice.invoice_date,
        transaction_type=LedgerTransactionType.INVOICE,
        reference_number=invoice.invoice_number,
        description="Invoice created",
        debit=invoice.grand_total,
        payment_status=invoice.payment_status.value,
    )

    if payload.advance_to_adjust > Decimal("0"):
        from app.services.payment_service import adjust_customer_advance

        adjust_customer_advance(
            db,
            customer_id=customer.id,
            invoice_id=invoice.id,
            adjustment_date=invoice.invoice_date,
            amount=payload.advance_to_adjust,
            user=user,
            commit=False,
        )

    if payload.amount_paid_now > Decimal("0"):
        from app.services.payment_service import receive_payment

        receive_payment(
            db,
            PaymentCreate(
                customer_id=customer.id,
                payment_date=invoice.invoice_date,
                total_amount=payload.amount_paid_now,
                payment_method=PaymentMethod(payload.payment_method or PaymentMethod.CASH),
                notes=f"Payment received while creating {invoice.invoice_number}",
                allocations=[
                    PaymentAllocationCreate(
                        invoice_id=invoice.id,
                        allocated_amount=payload.amount_paid_now,
                    )
                ],
            ),
            user=user,
            commit=False,
        )

    refresh_invoice_payment_state(db, invoice)
    refresh_customer_balances(db, customer.id)
    write_audit(
        db,
        user=user,
        action="create",
        module="invoice",
        record_id=invoice.id,
        new_value={"invoice_number": invoice.invoice_number, "grand_total": str(invoice.grand_total)},
    )
    db.commit()
    db.refresh(invoice)
    return invoice
