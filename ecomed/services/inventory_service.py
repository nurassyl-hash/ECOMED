"""Учёт упаковок: CRUD, события остатка, статусы срока (ТЗ FR-05, FR-06, FR-10)."""
from __future__ import annotations

from datetime import date
from typing import Optional

from ecomed.db.database import get_session
from ecomed.db.models import InventoryEvent, InventoryItem
from ecomed.domain import (
    effective_expiry,
    expiry_status,
    normalize_inn,
    parse_expiry,
)
from ecomed.models.schemas import ExpiryStatus


class NegativeStock(ValueError):
    """Попытка увести остаток ниже нуля (ТЗ FR-06, TC-10)."""


# --------------------------------------------------------------------------
# Расчёты статуса по ORM-объекту
# --------------------------------------------------------------------------
def item_effective_expiry(item: InventoryItem) -> Optional[date]:
    return effective_expiry(item.expiry_date, item.opened_at, item.after_open_days)


def item_status(item: InventoryItem, today: Optional[date] = None) -> ExpiryStatus:
    return expiry_status(item_effective_expiry(item), today)


def _view(item: InventoryItem, today: Optional[date] = None) -> dict:
    eff = item_effective_expiry(item)
    return {
        "id": item.id,
        "custom_name": item.custom_name,
        "inns": list(item.inn_json or []),
        "dosage_form": item.dosage_form,
        "strength": item.strength,
        "quantity_remaining": item.quantity_remaining,
        "unit": item.unit,
        "package_id": item.package_id,
        "expiry_date": item.expiry_date.isoformat() if item.expiry_date else None,
        "expiry_precision": item.expiry_precision,
        "opened_at": item.opened_at.isoformat() if item.opened_at else None,
        "after_open_days": item.after_open_days,
        "effective_expiry": eff.isoformat() if eff else None,
        "status": item_status(item, today).value,
        "storage_place": item.storage_place,
        "source": item.source,
        "photo_url": item.photo_url,
    }


# --------------------------------------------------------------------------
# Создание
# --------------------------------------------------------------------------
def add_item(
    household_id: int,
    *,
    custom_name: str,
    inns: list[str],
    dosage_form: Optional[str] = None,
    strength: Optional[str] = None,
    quantity: float = 0,
    unit: str = "tablet",
    package_id: Optional[str] = None,
    expiry_raw: Optional[str] = None,
    opened_at: Optional[date] = None,
    after_open_days: Optional[int] = None,
    storage_place: Optional[str] = None,
    source: str = "manual",
    photo_url: Optional[str] = None,
    price: Optional[float] = None,
    actor_id: Optional[int] = None,
) -> int:
    exp = parse_expiry(expiry_raw)
    precision = "month" if (expiry_raw and len(expiry_raw.strip()) == 7) else "day"
    norm_inns = [normalize_inn(x) for x in inns if x and normalize_inn(x)]

    with get_session() as s:
        item = InventoryItem(
            household_id=household_id,
            custom_name=custom_name,
            inn_json=norm_inns,
            dosage_form=dosage_form,
            strength=strength,
            quantity_remaining=max(0.0, float(quantity)),
            unit=unit,
            package_id=package_id,
            expiry_date=exp,
            expiry_precision=precision,
            opened_at=opened_at,
            after_open_days=after_open_days,
            storage_place=storage_place,
            source=source,
            photo_url=photo_url,
        )
        s.add(item)
        s.flush()
        s.add(InventoryEvent(
            item_id=item.id, household_id=household_id, event_type="added",
            quantity_delta=float(quantity), price=price, actor_id=actor_id,
        ))
        return item.id


# --------------------------------------------------------------------------
# Чтение
# --------------------------------------------------------------------------
def list_items(household_id: int, today: Optional[date] = None) -> list[dict]:
    with get_session() as s:
        items = (
            s.query(InventoryItem)
            .filter(InventoryItem.household_id == household_id)
            .order_by(InventoryItem.custom_name)
            .all()
        )
        return [_view(i, today) for i in items]


def get_item(item_id: int, household_id: int, today: Optional[date] = None) -> Optional[dict]:
    with get_session() as s:
        item = s.get(InventoryItem, item_id)
        if item is None or item.household_id != household_id:
            return None  # изоляция семьи (ТЗ FR-02, TC-13)
        return _view(item, today)


# --------------------------------------------------------------------------
# Изменение остатка (ТЗ FR-06)
# --------------------------------------------------------------------------
def update_quantity(
    item_id: int,
    household_id: int,
    delta: float,
    event_type: str,
    price: Optional[float] = None,
    actor_id: Optional[int] = None,
) -> float:
    """Меняет остаток на delta. Отрицательный итог запрещён (NegativeStock)."""
    with get_session() as s:
        item = s.get(InventoryItem, item_id)
        if item is None or item.household_id != household_id:
            raise PermissionError("Нет доступа к записи другой семьи.")
        new_qty = item.quantity_remaining + float(delta)
        if new_qty < 0:
            raise NegativeStock(
                f"Остаток не может быть отрицательным: {item.quantity_remaining} + {delta}"
            )
        item.quantity_remaining = new_qty
        s.add(InventoryEvent(
            item_id=item.id, household_id=household_id, event_type=event_type,
            quantity_delta=float(delta), price=price, actor_id=actor_id,
        ))
        return new_qty


def set_opened(item_id: int, household_id: int, opened_at: date, after_open_days: Optional[int]) -> None:
    with get_session() as s:
        item = s.get(InventoryItem, item_id)
        if item is None or item.household_id != household_id:
            raise PermissionError("Нет доступа к записи другой семьи.")
        item.opened_at = opened_at
        item.after_open_days = after_open_days


def delete_item(item_id: int, household_id: int) -> None:
    with get_session() as s:
        item = s.get(InventoryItem, item_id)
        if item is None or item.household_id != household_id:
            raise PermissionError("Нет доступа к записи другой семьи.")
        s.delete(item)
