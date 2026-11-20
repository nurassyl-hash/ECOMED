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
from ecomed.ui_common import disclaimer, household_id, match_text, page_setup, t

page_setup("nav.purchase_check", "🛒")
hid = household_id()

st.title(t("pc.title"))
st.caption(t("pc.subtitle"))

_LEVEL_STYLE = {
    MatchLevel.A: ("✅", "#388e3c"),
    MatchLevel.B: ("⚠️", "#f57c00"),
    MatchLevel.C: ("ℹ️", "#fbc02d"),
    MatchLevel.D: ("❔", "#9e9e9e"),
}

# Автоподстановка из каталога (упрощённая замена сканирования штрихкода)
catalog_rows = catalog_provider._rows()
MANUAL = -1
options = [MANUAL] + list(range(len(catalog_rows)))
picked = st.selectbox(
    t("pc.catalog.label"), options,
    format_func=lambda i: (
        t("pc.catalog.manual") if i == MANUAL
        else f"{catalog_rows[i]['trade_name']} {catalog_rows[i]['strength']}"
    ),
)

if picked != MANUAL:
    row = catalog_rows[picked]
    default_name = row["trade_name"]
    default_inns = row["inn"].replace(";", ", ")
    default_strength = row["strength"]
    default_form = row["dosage_form"]
else:
    default_name = default_inns = default_strength = default_form = ""

c1, c2 = st.columns(2)
name = c1.text_input(t("pc.field.name"), value=default_name)
inns = c2.text_input(t("pc.field.inns"), value=default_inns)
c3, c4 = st.columns(2)
strength = c3.text_input(t("pc.field.strength"), value=default_strength)
form = c4.text_input(t("pc.field.form"), value=default_form)

if st.button(t("pc.check"), type="primary"):
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
        st.success(t("pc.not_found"))
    for m in matches:
        level = MatchLevel(m["level"])
        icon, color = _LEVEL_STYLE.get(level, ("•", "#666"))
        st.markdown(
            f"<div style='border-left:5px solid {color};padding:8px 12px;margin:6px 0;background:#00000008'>"
            f"<b>{icon} {t('pc.level', level=level.value)}: {m['trade_name']}</b><br>"
            f"{match_text(level)}<br>"
            f"<small>{t('pc.remaining')}: {m['quantity_remaining']:g} {m['unit']} · "
            f"{t('pc.expiry')}: {m['expiry_date'] or t('common.unknown_expiry')} · "
            f"{t('pc.place')}: {m['storage_place'] or '—'}</small></div>",
            unsafe_allow_html=True,
        )
        if level in (MatchLevel.A, MatchLevel.B):
            price = rep.price_lookup(st.session_state.get("pc_query_name", "") or m["trade_name"])
            label = t("pc.avoided") + (
                t("pc.avoided_savings", price=f"{price:.0f}", cur=t("common.currency")) if price else ""
            )
            if st.button(label, key=f"avoid_{m['inventory_item_id']}"):
                match.record_avoided_purchase(hid, m["inventory_item_id"], price=price)
                st.success(t("pc.avoided_ok"))

    st.divider()
    disclaimer()
