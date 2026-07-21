"""Сравнение цен на лекарства в аптеках города (ТЗ FR-16, раздел 8)."""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_r = _Path(__file__).resolve()
while _r.parent != _r and not (_r / "ecomed" / "__init__.py").exists():
    _r = _r.parent
if str(_r) not in _sys.path:
    _sys.path.insert(0, str(_r))

import streamlit as st

from ecomed.services import price_service
from ecomed.ui_common import household_id, page_setup

page_setup("Цены в аптеках", "💊")
household_id()

st.title("💊 Цены на лекарства в аптеках")
st.caption("Сравните стоимость препарата в аптеках выбранного города. Данные демонстрационные (вымышленные аптеки); цена не является публичной офертой — уточняйте в аптеке.")

cities = price_service.list_cities()
if not cities:
    st.warning("Данные о ценах недоступны.")
    st.stop()

# Город: по умолчанию — выбранный в боковой панели
pre = st.session_state.get("price_city")
idx = cities.index(pre) if pre in cities else 0
c1, c2 = st.columns([1, 2])
city = c1.selectbox("Город", cities, index=idx)
query = c2.text_input("Поиск препарата", "", placeholder="например: парацетамол")

rows = price_service.compare(city, query or None)
if not rows:
    st.info("По запросу ничего не найдено.")
    st.stop()

# --- Сводная таблица ---
st.subheader(f"Обзор цен — {city}")
st.dataframe(
    [{
        "Препарат": r["trade_name"],
        "Упаковка": r["package_desc"],
        "Дешевле всего": f"{r['min_price']:.0f} ₸",
        "Аптека": r["min_pharmacy"],
        "Дороже всего": f"{r['max_price']:.0f} ₸",
        "Экономия": f"{r['savings']:.0f} ₸ ({r['savings_pct']:.0f}%)",
        "Обновлено": r["latest_observed"],
    } for r in rows],
    width="stretch", hide_index=True,
)

# --- Детализация по аптекам ---
st.subheader("Детально по аптекам")
for r in rows:
    title = f"{r['trade_name']} — от {r['min_price']:.0f} ₸ (экономия до {r['savings']:.0f} ₸)"
    with st.expander(title):
        st.caption(f"Упаковка: {r['package_desc']}")
        for i, o in enumerate(r["offers"]):
            mark = "🟢 дешевле всего" if i == 0 else ""
            st.markdown(
                f"**{o['pharmacy']}** — {o['price']:.0f} {o['currency']} {mark}  \n"
                f"<small>обновлено {o['observed_at']} · источник: {o['source_url']}</small>",
                unsafe_allow_html=True,
            )

# --- Статус источника ---
st.divider()
status = price_service.provider_status()
st.caption(
    f"Источник данных: провайдер «{status.get('provider')}» "
    f"({status.get('status')}, записей: {status.get('rows', '—')}). "
    "В будущем — партнёрский API аптечной сети (см. integrations/prices_provider.py)."
)
