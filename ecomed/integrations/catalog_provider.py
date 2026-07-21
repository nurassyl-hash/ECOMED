"""Адаптер справочника лекарств (ТЗ раздел 8).

Приоритетный источник для РК — гос. реестр НЦЭЛС/NDDA. В MVP используется
подготовленный локальный набор (data/demo_catalog.csv) со ссылкой и датой
выгрузки. Интерфейс адаптера: search / get_by_id / healthcheck.
"""
from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

from ecomed.domain import normalize_inn

DATA = Path(__file__).resolve().parent.parent / "data" / "demo_catalog.csv"


@lru_cache(maxsize=1)
def _rows() -> list[dict]:
    if not DATA.exists():
        return []
    with DATA.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def healthcheck() -> dict:
    return {"provider": "demo_catalog_csv", "available": DATA.exists(), "rows": len(_rows())}


def search(query: str) -> list[dict]:
    """Кандидаты по торговому названию или МНН (нестрого)."""
    q = normalize_inn(query)
    out = []
    for r in _rows():
        hay = normalize_inn(f"{r.get('trade_name','')} {r.get('inn','')}")
        if q and q in hay:
            out.append(r)
    return out


def get_by_id(source_id: str) -> dict | None:
    for r in _rows():
        if str(r.get("id")) == str(source_id):
            return r
    return None
