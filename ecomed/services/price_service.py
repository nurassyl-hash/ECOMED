"""Сравнение цен на лекарства в аптеках города (ТЗ FR-16, 13.3).

Данные приходят из заменяемого провайдера (сейчас — демо-CSV). Каждое
предложение содержит аптеку, цену, город, дату наблюдения и источник; цена
не подменяется средней без явной метки.
"""
from __future__ import annotations

from typing import Optional

from ecomed.integrations.prices_provider import PriceOfferDTO, get_price_provider


def list_cities() -> list[str]:
    return get_price_provider().cities()


def provider_status() -> dict:
    return get_price_provider().healthcheck()


def compare(city: str, query: Optional[str] = None) -> list[dict]:
    """Сравнение по препаратам в городе.

    Возвращает список препаратов; для каждого — предложения аптек, отсортированные
    по цене, и агрегаты (мин/макс/экономия/самая свежая дата).
    """
    offers = get_price_provider().search(city, query)

    grouped: dict[str, list[PriceOfferDTO]] = {}
    for o in offers:
        grouped.setdefault(o.trade_name, []).append(o)

    result = []
    for name, items in sorted(grouped.items()):
        items = sorted(items, key=lambda x: x.price)
        prices = [i.price for i in items]
        low, high = prices[0], prices[-1]
        savings = high - low
        result.append({
            "trade_name": name,
            "package_desc": items[0].package_desc,
            "currency": items[0].currency,
            "min_price": low,
            "max_price": high,
            "min_pharmacy": items[0].pharmacy,
            "savings": savings,
            "savings_pct": round(savings / high * 100, 1) if high else 0.0,
            "latest_observed": max((i.observed_at for i in items), default=""),
            "offers": [i.as_dict() for i in items],
        })
    return result


def cheapest(city: str, name: str) -> Optional[dict]:
    """Самое дешёвое предложение по конкретному препарату в городе."""
    rows = compare(city, name)
    if not rows:
        return None
    top = rows[0]
    return {
        "trade_name": top["trade_name"],
        "price": top["min_price"],
        "currency": top["currency"],
        "pharmacy": top["min_pharmacy"],
        "observed": top["latest_observed"],
        "offers": top["offers"],
    }
