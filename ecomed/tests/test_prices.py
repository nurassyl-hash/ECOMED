"""Сравнение цен в аптеках (ТЗ FR-16)."""
from ecomed.services import price_service


def test_cities_available():
    cities = price_service.list_cities()
    assert "Алматы" in cities
    assert len(cities) >= 3


def test_compare_sorted_and_aggregated():
    rows = price_service.compare("Алматы")
    assert rows
    for r in rows:
        prices = [o["price"] for o in r["offers"]]
        assert prices == sorted(prices)                 # по возрастанию цены
        assert r["min_price"] == prices[0]
        assert r["max_price"] == prices[-1]
        assert r["savings"] == prices[-1] - prices[0]


def test_cheapest_offer():
    c = price_service.cheapest("Алматы", "Парацетамол")
    assert c is not None
    # среди предложений выбрана минимальная цена
    assert c["price"] == min(o["price"] for o in c["offers"])


def test_search_filters():
    rows = price_service.compare("Алматы", "нурофен")
    assert rows
    assert all("нурофен" in r["trade_name"].lower() for r in rows)
