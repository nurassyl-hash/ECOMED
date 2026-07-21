"""Проверка перед покупкой: уровни совпадения A–D (ТЗ FR-08, 4.2)."""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_r = _Path(__file__).resolve()
while _r.parent != _r and not (_r / "ecomed" / "__init__.py").exists():
    _r = _r.parent
if str(_r) not in _sys.path:
    _sys.path.insert(0, str(_r))

import streamlit as st

from ecomed.integrations import catalog_provider
from ecomed.models.schemas import MatchLevel
from ecomed.services import matching_service as match
from ecomed.services import report_service as rep
from ecomed.ui_common import disclaimer, household_id, page_setup

page_setup("Проверить покупку", "🛒")
hid = household_id()

st.title("🛒 Проверить перед покупкой")
st.caption("Проверьте, есть ли препарат дома, прежде чем покупать. Результат — информация о запасах, а не разрешение на замену.")

_LEVEL_STYLE = {
    MatchLevel.A: ("✅", "#388e3c"),
    MatchLevel.B: ("⚠️", "#f57c00"),
    MatchLevel.C: ("ℹ️", "#fbc02d"),
    MatchLevel.D: ("❔", "#9e9e9e"),
}

# Автоподстановка из каталога (упрощённая замена сканирования штрихкода)
catalog_rows = catalog_provider._rows()
options = ["— ввести вручную —"] + [f"{r['trade_name']} {r['strength']}" for r in catalog_rows]
picked = st.selectbox("Выберите из каталога или введите вручную", options)

if picked != "— ввести вручную —":
    idx = options.index(picked) - 1
    row = catalog_rows[idx]
    default_name = row["trade_name"]
    default_inns = row["inn"].replace(";", ", ")
    default_strength = row["strength"]
    default_form = row["dosage_form"]
else:
    default_name = default_inns = default_strength = default_form = ""

c1, c2 = st.columns(2)
name = c1.text_input("Название", value=default_name)
inns = c2.text_input("Действующие вещества (через запятую)", value=default_inns)
c3, c4 = st.columns(2)
strength = c3.text_input("Дозировка", value=default_strength)
form = c4.text_input("Форма", value=default_form)

if st.button("🔍 Проверить", type="primary"):
    match.record_purchase_check(hid)  # факт проверки (эко-показатель)
    st.session_state["pc_matches"] = [
        m.model_dump() for m in match.check_purchase(
            hid, name=name,
            inns=[x.strip() for x in inns.split(",") if x.strip()],
            strength=strength, dosage_form=form,
        )
    ]
    st.session_state["pc_query_name"] = name

matches = st.session_state.get("pc_matches")
if matches is not None:
    st.divider()
    if not matches:
        st.success("Дома такого препарата не найдено — покупка может быть оправдана.")
    for m in matches:
        level = MatchLevel(m["level"])
        icon, color = _LEVEL_STYLE.get(level, ("•", "#666"))
        st.markdown(
            f"<div style='border-left:5px solid {color};padding:8px 12px;margin:6px 0;background:#00000008'>"
            f"<b>{icon} Уровень {level.value}: {m['trade_name']}</b><br>{m['text']}<br>"
            f"<small>Остаток дома: {m['quantity_remaining']:g} {m['unit']} · "
            f"срок: {m['expiry_date'] or 'неизвестен'} · место: {m['storage_place'] or '—'}</small></div>",
            unsafe_allow_html=True,
        )
        if level in (MatchLevel.A, MatchLevel.B):
            price = rep.price_lookup(st.session_state.get("pc_query_name", "") or m["trade_name"])
            label = f"🚫 Не купил — уже есть дома" + (f" (экономия {price:.0f} ₸)" if price else "")
            if st.button(label, key=f"avoid_{m['inventory_item_id']}"):
                match.record_avoided_purchase(hid, m["inventory_item_id"], price=price)
                st.success("Засчитано как подтверждённая предотвращённая покупка.")

    st.divider()
    disclaimer()
