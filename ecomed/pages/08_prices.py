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
from ecomed.ui_common import household_id, page_setup, t

page_setup("nav.prices", "💊")
household_id()

CUR = t("common.currency")

st.title(t("prices.title"))
st.caption(t("prices.subtitle"))

cities = price_service.list_cities()
if not cities:
    st.warning(t("prices.unavailable"))
    st.stop()

# Город: по умолчанию — выбранный в боковой панели
pre = st.session_state.get("price_city")
idx = cities.index(pre) if pre in cities else 0
c1, c2 = st.columns([1, 2])
city = c1.selectbox(t("prices.city"), cities, index=idx)
query = c2.text_input(t("prices.search"), "", placeholder=t("prices.search_ph"))

rows = price_service.compare(city, query or None)
if not rows:
    st.info(t("prices.nothing"))
    st.stop()

# --- Сводная таблица ---
st.subheader(t("prices.overview", city=city))
st.dataframe(
    [{
        t("prices.col.med"): r["trade_name"],
        t("prices.col.package"): r["package_desc"],
        t("prices.col.min"): f"{r['min_price']:.0f} {CUR}",
        t("prices.col.pharmacy"): r["min_pharmacy"],
        t("prices.col.max"): f"{r['max_price']:.0f} {CUR}",
        t("prices.col.savings"): f"{r['savings']:.0f} {CUR} ({r['savings_pct']:.0f}%)",
        t("prices.col.updated"): r["latest_observed"],
    } for r in rows],
    width="stretch", hide_index=True,
)

# --- Детализация по аптекам ---
st.subheader(t("prices.details"))
for r in rows:
    title = t("prices.expander", name=r["trade_name"],
              min=f"{r['min_price']:.0f}", savings=f"{r['savings']:.0f}", cur=CUR)
    with st.expander(title):
        st.caption(t("prices.package", desc=r["package_desc"]))
        for i, o in enumerate(r["offers"]):
            mark = t("prices.cheapest_mark") if i == 0 else ""
            st.markdown(
                f"**{o['pharmacy']}** — {o['price']:.0f} {o['currency']} {mark}  \n"
                f"<small>{t('prices.updated', date=o['observed_at'], src=o['source_url'])}</small>",
                unsafe_allow_html=True,
            )

# --- Статус источника ---
st.divider()
status = price_service.provider_status()
st.caption(t(
    "prices.source",
    provider=status.get("provider"),
    status=status.get("status"),
    rows=status.get("rows", "—"),
))
