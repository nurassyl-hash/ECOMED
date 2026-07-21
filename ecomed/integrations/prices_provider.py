"""Адаптер цен в аптеках (ТЗ раздел 8: заменяемый провайдер с локальным fallback).

Сейчас данные берутся из локального CSV (демонстрационные, вымышленные аптеки).
В будущем провайдер заменяется на партнёрский API аптечной сети без изменения
UI и сервисного слоя — достаточно реализовать методы контракта в
`PartnerApiPriceProvider` и переключить `ECOMED_PRICES_PROVIDER=api`.

Единый интерфейс адаптера (как в ТЗ 8):
    search(city, query)   -> list[PriceOffer]
    get_by_id(offer_id)   -> PriceOffer | None
    healthcheck()         -> dict(status, latency, last_success)
    refresh(since)        -> dict(upserted, errors)
Каждая запись содержит provider/source_url/observed_at, чтобы доказать
происхождение и обновляемость данных.
"""
from __future__ import annotations

import csv
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

from ecomed.config import settings
from ecomed.domain import normalize_inn

DATA = Path(__file__).resolve().parent.parent / "data" / "demo_prices.csv"


@dataclass
class PriceOfferDTO:
    trade_name: str
    pharmacy: str
    city: str
    price: float
    currency: str
    package_desc: str
    observed_at: str
    source_url: str
    provider: str = "demo"

    def as_dict(self) -> dict:
        return asdict(self)


class PriceProvider(ABC):
    """Контракт провайдера цен."""

    name: str = "base"

    @abstractmethod
    def cities(self) -> list[str]:
        ...

    @abstractmethod
    def search(self, city: str, query: Optional[str] = None) -> list[PriceOfferDTO]:
        ...

    @abstractmethod
    def healthcheck(self) -> dict:
        ...

    def refresh(self, since: Optional[str] = None) -> dict:  # необязателен для demo
        return {"upserted": 0, "errors": []}


class DemoPriceProvider(PriceProvider):
    """Локальный провайдер: демонстрационные цены из CSV."""

    name = "demo"

    @lru_cache(maxsize=1)
    def _rows(self) -> tuple[PriceOfferDTO, ...]:
        if not DATA.exists():
            return tuple()
        out = []
        with DATA.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                out.append(PriceOfferDTO(
                    trade_name=r["trade_name"], pharmacy=r["pharmacy"], city=r["city"],
                    price=float(r["price"]), currency=r.get("currency", "KZT"),
                    package_desc=r.get("package_desc", ""), observed_at=r.get("observed_at", ""),
                    source_url=r.get("source_url", "demo"), provider="demo",
                ))
        return tuple(out)

    def cities(self) -> list[str]:
        return sorted({o.city for o in self._rows()})

    def search(self, city: str, query: Optional[str] = None) -> list[PriceOfferDTO]:
        q = normalize_inn(query or "")
        res = [o for o in self._rows() if o.city == city]
        if q:
            res = [o for o in res if q in normalize_inn(o.trade_name)]
        return res

    def healthcheck(self) -> dict:
        rows = self._rows()
        return {"provider": self.name, "status": "ok" if rows else "empty",
                "rows": len(rows), "source": str(DATA)}


class PartnerApiPriceProvider(PriceProvider):
    """ЗАГОТОВКА под партнёрский API аптечной сети.

    Здесь описан интерфейс будущей интеграции. Реальные вызовы не выполняются,
    пока не заключён договор и не указаны `ECOMED_PRICES_API_URL` / `..._API_KEY`.
    Не выполнять неразрешённый скрейпинг публичных витрин (ТЗ раздел 8).

    Пример будущей реализации (псевдокод):
        import httpx
        def search(self, city, query=None):
            resp = httpx.get(f"{self.base_url}/v1/prices",
                             params={"city": city, "q": query},
                             headers={"Authorization": f"Bearer {self.api_key}"},
                             timeout=10)
            resp.raise_for_status()
            return [PriceOfferDTO(**item, provider="api") for item in resp.json()["items"]]
    """

    name = "api"

    def __init__(self, base_url: str = "", api_key: str = ""):
        self.base_url = base_url or settings.ecomed_prices_api_url
        self.api_key = api_key or settings.ecomed_prices_api_key

    def _configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    def cities(self) -> list[str]:
        # TODO: GET {base_url}/v1/cities
        raise NotImplementedError("Партнёрский API цен ещё не подключён.")

    def search(self, city: str, query: Optional[str] = None) -> list[PriceOfferDTO]:
        # TODO: GET {base_url}/v1/prices?city=...&q=...  (Authorization: Bearer <key>)
        raise NotImplementedError("Партнёрский API цен ещё не подключён.")

    def healthcheck(self) -> dict:
        if not self._configured():
            return {"provider": self.name, "status": "not_configured"}
        # TODO: GET {base_url}/health
        return {"provider": self.name, "status": "unknown"}


@lru_cache(maxsize=1)
def get_price_provider() -> PriceProvider:
    """Фабрика провайдера. Демо по умолчанию; при сбое API — откат на демо."""
    if settings.ecomed_prices_provider == "api":
        api = PartnerApiPriceProvider()
        if api._configured():
            return api
        # API выбран, но не настроен → безопасный откат на локальные данные
    return DemoPriceProvider()
