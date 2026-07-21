"""Утилизация: проверенные пункты и подтверждённая передача (ТЗ FR-13, 4.4)."""
from __future__ import annotations

from datetime import date
from typing import Optional

from ecomed.db.database import get_session
from ecomed.db.models import DisposalEvent, DisposalPoint, InventoryItem

# Честные тексты из Приложения A ТЗ
NO_POINT_TEXT = (
    "Для выбранного города нет подтверждённого пункта в нашей базе. Не используйте "
    "непроверенный адрес; уточните порядок у аптеки или местного компетентного органа."
)
DISCLAIMER_TEXT = (
    "Показаны только правила из одобренной базы источников. Если правила для "
    "домохозяйств не определены однозначно, приложение не додумывает процедуру."
)


def list_points(city: Optional[str] = None) -> list[dict]:
    """Пункты приёма. Каждый содержит verified_at, source_url и статус demo/verified."""
    with get_session() as s:
        q = s.query(DisposalPoint)
        if city:
            q = q.filter(DisposalPoint.city == city)
        points = q.all()
        return [{
            "id": p.id, "name": p.name, "city": p.city, "address": p.address,
            "lat": p.lat, "lon": p.lon, "accepted_types": p.accepted_types,
            "verified_at": p.verified_at.isoformat() if p.verified_at else None,
            "source_url": p.source_url, "status": p.status,
        } for p in points]


def record_disposal(
    household_id: int,
    point_id: int,
    packages_count: int,
    item_id: Optional[int] = None,
) -> int:
    """Отметка передачи → подтверждённое экологическое действие (ТЗ 4.4)."""
    if packages_count < 0:
        raise ValueError("Количество упаковок не может быть отрицательным.")
    with get_session() as s:
        if item_id is not None:
            item = s.get(InventoryItem, item_id)
            if item is None or item.household_id != household_id:
                raise PermissionError("Нет доступа к записи другой семьи.")
        ev = DisposalEvent(
            household_id=household_id, item_id=item_id,
            point_id=point_id, packages_count=packages_count,
        )
        s.add(ev)
        s.flush()
        return ev.id
