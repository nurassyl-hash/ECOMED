"""Утилизация: проверенные пункты и подтверждённая передача (ТЗ FR-13, 4.4)."""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_r = _Path(__file__).resolve()
while _r.parent != _r and not (_r / "ecomed" / "__init__.py").exists():
    _r = _r.parent
if str(_r) not in _sys.path:
    _sys.path.insert(0, str(_r))

import pandas as pd
import streamlit as st

from ecomed.config import settings
from ecomed.services import disposal_service as disp
from ecomed.services import inventory_service as inv
from ecomed.ui_common import household_id, page_setup

page_setup("Утилизация", "♻️")
hid = household_id()

st.title("♻️ Безопасная утилизация")
st.info(disp.DISCLAIMER_TEXT, icon="📘")

cities = sorted({p["city"] for p in disp.list_points() if p["city"]})
default_city = settings.ecomed_default_city
idx = cities.index(default_city) if default_city in cities else 0
city = st.selectbox("Город", cities or ["—"], index=idx if cities else 0)

points = disp.list_points(city)

if not points:
    st.warning(disp.NO_POINT_TEXT, icon="⚠️")
else:
    verified_points = [p for p in points if p["status"] == "verified"]
    st.subheader(f"Пункты приёма — {city}")
    st.caption(f"Найдено пунктов: {len(points)} · подтверждённых: {len(verified_points)}")

    for p in points:
        verified = p["status"] == "verified"
        badge = ("🟢 подтверждён" if verified
                 else "🟡 демонстрационный — не использовать как действующий адрес")
        src = (f"[источник]({p['source_url']})"
               if str(p["source_url"]).startswith("http") else "демо-данные")
        no_geo = "" if (p["lat"] and p["lon"]) else " · нет координат для карты"
        st.markdown(
            f"**{p['name']}**  \n"
            f"{p['address']} · принимает: {p['accepted_types']}  \n"
            f"Статус: {badge} · проверено: {p['verified_at'] or '—'} · {src}{no_geo}"
        )

    if verified_points:
        st.caption(
            "⛔ Подтверждённые пункты НЕ принимают: шприцы, иглы, системы для инфузий "
            "и отходы, загрязнённые кровью."
        )
    else:
        st.warning("В этом городе нет подтверждённых пунктов. Непроверенные точки не выдаются как действующие.")

    # Карта (гео помогает показать, но не доказывает приём отходов — ТЗ 8)
    df = pd.DataFrame([{"lat": p["lat"], "lon": p["lon"]} for p in points if p["lat"] and p["lon"]])
    if not df.empty:
        st.map(df, size=40)
        st.caption("На карте — пункты с известными координатами (приблизительно). "
                   "Карта не доказывает, что пункт принимает лекарства; ориентируйтесь на адрес.")

    # --- Отметка передачи ---
    st.divider()
    st.subheader("Отметить передачу")
    items = inv.list_items(hid)
    expired = [i for i in items if i["status"] == "expired"] or items
    with st.form("disposal"):
        item_opt = st.selectbox(
            "Что передаёте", expired,
            format_func=lambda i: f"{i['custom_name']} ({i['status']})",
        )
        point_opt = st.selectbox("Пункт", points, format_func=lambda p: p["name"])
        count = st.number_input("Количество упаковок", min_value=1, value=1, step=1)
        if st.form_submit_button("✅ Подтвердить передачу", type="primary"):
            disp.record_disposal(hid, point_opt["id"], int(count), item_id=item_opt["id"])
            st.success("Записано как подтверждённое экологическое действие.")
            st.balloons()
