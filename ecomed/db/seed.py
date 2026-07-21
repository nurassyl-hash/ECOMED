"""Seed демо-данных (ТЗ раздел 19: подготовка демонстрации).

Идемпотентно: создаёт «Демо-семью» один раз. Для публичного демо используются
вымышленные имена и подготовленные данные (ТЗ 16).
"""
from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

from ecomed.db.database import get_session, init_db
from ecomed.db.models import (
    DisposalPoint,
    Household,
    HouseholdMember,
    InventoryEvent,
    InventoryItem,
    MedicationCatalog,
    PriceOffer,
    User,
)
from ecomed.domain import normalize_inn

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEMO_HOUSEHOLD = "Демо-семья"


def _d(iso: str) -> date:
    return date.fromisoformat(iso)


def _load_catalog(s) -> None:
    with (DATA_DIR / "demo_catalog.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            inns = [normalize_inn(x) for x in r["inn"].split(";") if x.strip()]
            s.add(MedicationCatalog(
                trade_name=r["trade_name"], inn_json=inns, dosage_form=r["dosage_form"],
                strength=r["strength"], atc=r["atc"], registration_no=r["registration_no"],
                provider="demo_catalog", source_url=r["source_url"],
            ))


def _load_prices(s) -> None:
    with (DATA_DIR / "demo_prices.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            s.add(PriceOffer(
                trade_name=r["trade_name"], pharmacy=r["pharmacy"], city=r["city"],
                price=float(r["price"]), currency=r["currency"], package_desc=r["package_desc"],
                observed_at=_d(r["observed_at"]), source_url=r["source_url"],
            ))


def _opt_float(v: str) -> float | None:
    v = (v or "").strip()
    return float(v) if v else None


def _opt_date(v: str):
    v = (v or "").strip()
    return _d(v) if v else None


def _load_disposal(s) -> None:
    with (DATA_DIR / "demo_disposal_points.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            s.add(DisposalPoint(
                name=r["name"], city=r["city"], address=r["address"],
                lat=_opt_float(r["lat"]), lon=_opt_float(r["lon"]),
                accepted_types=r["accepted_types"],
                verified_at=_opt_date(r["verified_at"]), source_url=r["source_url"],
                status=r["status"],
            ))


def _demo_inventory(today: date) -> list[dict]:
    """8 позиций: 2 группы дубликатов (парацетамол, ибупрофен), комбинированный,
    без срока, просроченный (для утилизации)."""
    def off(days: int) -> str:
        return (today + timedelta(days=days)).isoformat()

    return [
        dict(custom_name="Парацетамол 500 мг", inns=["парацетамол"], dosage_form="таблетки",
             strength="500 мг", quantity=10, unit="таблетка", expiry_raw=off(200),
             storage_place="Кухонный шкаф"),
        dict(custom_name="Парацетамол детский сироп", inns=["парацетамол"], dosage_form="сироп",
             strength="120 мг/5 мл", quantity=1, unit="флакон", expiry_raw=off(70),
             storage_place="Холодильник"),
        dict(custom_name="Нурофен 200 мг", inns=["ибупрофен"], dosage_form="таблетки",
             strength="200 мг", quantity=20, unit="таблетка", expiry_raw=off(60),
             storage_place="Аптечка в ванной"),
        dict(custom_name="Ибупрофен 200 мг", inns=["ибупрофен"], dosage_form="таблетки",
             strength="200 мг", quantity=8, unit="таблетка", expiry_raw=off(20),
             storage_place="Аптечка в ванной"),
        dict(custom_name="Аспирин 500 мг", inns=["ацетилсалициловая кислота"], dosage_form="таблетки",
             strength="500 мг", quantity=10, unit="таблетка", expiry_raw=off(-2),
             storage_place="Кухонный шкаф"),
        dict(custom_name="ТераФлю", inns=["парацетамол", "фенирамин", "фенилэфрин"],
             dosage_form="порошок", strength="325 мг", quantity=5, unit="пакетик",
             expiry_raw=off(150), storage_place="Кухонный шкаф"),
        dict(custom_name="Амоксициллин 500 мг", inns=["амоксициллин"], dosage_form="капсулы",
             strength="500 мг", quantity=16, unit="капсула", expiry_raw=None,
             storage_place="Аптечка в спальне"),
        dict(custom_name="Но-шпа 40 мг", inns=["дротаверин"], dosage_form="таблетки",
             strength="40 мг", quantity=24, unit="таблетка", expiry_raw=off(400),
             storage_place="Сумочка"),
    ]


def seed_demo(today: date | None = None) -> int:
    """Создаёт демо-семью и данные (если ещё нет). Возвращает household_id."""
    init_db()
    today = today or date.today()

    with get_session() as s:
        existing = s.query(Household).filter(Household.name == DEMO_HOUSEHOLD).first()
        if existing is not None:
            return existing.id

        user = User(email="demo@ecomed.local", display_name="Демо-пользователь")
        s.add(user)
        s.flush()

        hh = Household(name=DEMO_HOUSEHOLD, owner_id=user.id, city="Алматы")
        s.add(hh)
        s.flush()
        s.add(HouseholdMember(household_id=hh.id, user_id=user.id, role="owner"))

        if s.query(MedicationCatalog).count() == 0:
            _load_catalog(s)
        if s.query(PriceOffer).count() == 0:
            _load_prices(s)
        if s.query(DisposalPoint).count() == 0:
            _load_disposal(s)

        for spec in _demo_inventory(today):
            from ecomed.domain import parse_expiry
            exp = parse_expiry(spec["expiry_raw"]) if spec["expiry_raw"] else None
            item = InventoryItem(
                household_id=hh.id, custom_name=spec["custom_name"],
                inn_json=[normalize_inn(x) for x in spec["inns"]],
                dosage_form=spec["dosage_form"], strength=spec["strength"],
                quantity_remaining=spec["quantity"], unit=spec["unit"],
                expiry_date=exp, storage_place=spec["storage_place"], source="manual",
            )
            s.add(item)
            s.flush()
            s.add(InventoryEvent(item_id=item.id, household_id=hh.id,
                                 event_type="added", quantity_delta=spec["quantity"]))
        return hh.id


if __name__ == "__main__":
    hid = seed_demo()
    print(f"Demo household id = {hid}")
