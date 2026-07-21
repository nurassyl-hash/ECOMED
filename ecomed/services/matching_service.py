"""Сопоставление и дубликаты (ТЗ FR-08, FR-09, 7.2, 13.2)."""
from __future__ import annotations

from datetime import date
from typing import Optional

from ecomed.db.database import get_session
from ecomed.db.models import InventoryEvent, InventoryItem
from ecomed.domain import match_level, normalize_inn, normalize_inn_set
from ecomed.models.schemas import MATCH_TEXT, MatchLevel, PurchaseMatch

try:
    from rapidfuzz.fuzz import token_sort_ratio

    def _similarity(a: str, b: str) -> float:
        return token_sort_ratio(a, b) / 100.0
except ImportError:  # fallback без rapidfuzz
    from difflib import SequenceMatcher

    def _similarity(a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio()


_LEVEL_ORDER = {MatchLevel.A: 0, MatchLevel.B: 1, MatchLevel.C: 2, MatchLevel.D: 3, MatchLevel.NONE: 9}


def check_purchase(
    household_id: int,
    *,
    name: Optional[str] = None,
    inns: Optional[list[str]] = None,
    strength: Optional[str] = None,
    dosage_form: Optional[str] = None,
    package_id: Optional[str] = None,
) -> list[PurchaseMatch]:
    """Проверка перед покупкой: возвращает совпадения уровней A–D по домашним запасам.

    Ни один результат не формулируется как разрешение на замену (ТЗ FR-08).
    """
    q_name = normalize_inn(name or "")
    q_inns = normalize_inn_set(inns or [])
    q_strength = normalize_inn(strength or "")
    q_form = normalize_inn(dosage_form or "")

    matches: list[PurchaseMatch] = []
    with get_session() as s:
        items = s.query(InventoryItem).filter(InventoryItem.household_id == household_id).all()
        for it in items:
            it_inns = normalize_inn_set(it.inn_json or [])
            same_pkg = bool(package_id and it.package_id and package_id == it.package_id)
            sim = _similarity(q_name, normalize_inn(it.custom_name)) if q_name else 0.0
            level = match_level(
                same_package_id=same_pkg,
                query_inns=q_inns,
                item_inns=it_inns,
                same_strength=(bool(q_strength) and q_strength == normalize_inn(it.strength or "")),
                same_form=(bool(q_form) and q_form == normalize_inn(it.dosage_form or "")),
                name_similarity=sim,
            )
            if level == MatchLevel.NONE:
                continue
            matches.append(PurchaseMatch(
                level=level,
                text=MATCH_TEXT[level],
                inventory_item_id=it.id,
                trade_name=it.custom_name,
                quantity_remaining=it.quantity_remaining,
                unit=it.unit,
                expiry_date=it.expiry_date.isoformat() if it.expiry_date else None,
                storage_place=it.storage_place,
                score=round(sim, 3),
                reason=f"inns={sorted(it_inns)} strength={it.strength} form={it.dosage_form}",
            ))

    matches.sort(key=lambda m: (_LEVEL_ORDER[m.level], -m.score))
    return matches


def record_avoided_purchase(
    household_id: int,
    item_id: int,
    price: Optional[float] = None,
    actor_id: Optional[int] = None,
) -> None:
    """Событие «Не купил — уже есть дома» → подтверждённая предотвращённая покупка (ТЗ 4.2)."""
    with get_session() as s:
        item = s.get(InventoryItem, item_id)
        if item is None or item.household_id != household_id:
            raise PermissionError("Нет доступа к записи другой семьи.")
        s.add(InventoryEvent(
            item_id=item_id, household_id=household_id,
            event_type="avoided_purchase", quantity_delta=0, price=price, actor_id=actor_id,
        ))


def record_purchase_check(household_id: int, item_id: Optional[int] = None) -> None:
    """Факт выполненной проверки перед покупкой (эко-показатель, ТЗ FR-15)."""
    with get_session() as s:
        # привязываем к любой позиции семьи, если конкретной нет
        anchor = item_id
        if anchor is None:
            it = s.query(InventoryItem).filter(InventoryItem.household_id == household_id).first()
            anchor = it.id if it else None
        if anchor is None:
            return
        s.add(InventoryEvent(
            item_id=anchor, household_id=household_id,
            event_type="purchase_check", quantity_delta=0,
        ))


def find_duplicates(household_id: int) -> list[dict]:
    """Группы возможных дубликатов по нормализованному набору МНН (ТЗ 13.2).

    Точный дубликат = совпадение набора МНН + дозировки + формы.
    Комбинированные с частичным пересечением показываются отдельно, не как дубликат.
    """
    with get_session() as s:
        items = s.query(InventoryItem).filter(InventoryItem.household_id == household_id).all()
        by_inn: dict[frozenset, list[InventoryItem]] = {}
        for it in items:
            key = normalize_inn_set(it.inn_json or [])
            if not key:
                continue
            by_inn.setdefault(key, []).append(it)

    groups = []
    for key, its in by_inn.items():
        if len(its) < 2:
            continue
        exact = len({(normalize_inn(i.strength or ""), normalize_inn(i.dosage_form or "")) for i in its}) == 1
        groups.append({
            "inns": sorted(key),
            "exact": exact,
            "items": [{"id": i.id, "name": i.custom_name, "strength": i.strength,
                       "form": i.dosage_form, "quantity": i.quantity_remaining} for i in its],
        })
    return groups
