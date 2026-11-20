"""Моя аптечка: просмотр, поиск, фильтры, изменение остатка (ТЗ FR-05..FR-07)."""
from __future__ import annotations

import sys as _sys
from datetime import date
from pathlib import Path as _Path

_r = _Path(__file__).resolve()
while _r.parent != _r and not (_r / "ecomed" / "__init__.py").exists():
    _r = _r.parent
if str(_r) not in _sys.path:
    _sys.path.insert(0, str(_r))

import streamlit as st

from ecomed.domain import normalize_inn
from ecomed.models.schemas import ExpiryStatus
from ecomed.services import inventory_service as inv
from ecomed.ui_common import (
    household_id,
    page_setup,
    show_error,
    status_badge,
    status_dot,
    status_label,
    t,
)

page_setup("nav.inventory", "📋")
hid = household_id()

st.title(t("inventory.title"))

items = inv.list_items(hid)

# --- Фильтры ---
f1, f2, f3 = st.columns([2, 1, 1])
ALL = "__all__"  # технический sentinel: не пересекается ни со статусом, ни с местом хранения

query = f1.text_input(t("inventory.search"), "")
status_opts = [ALL] + [s.value for s in ExpiryStatus]
status_f = f2.selectbox(
    t("inventory.filter.status"), status_opts,
    format_func=lambda v: t("common.all") if v == ALL else status_label(v),
)
places = sorted({i["storage_place"] for i in items if i["storage_place"]})
place_f = f3.selectbox(
    t("inventory.filter.place"), [ALL, *places],
    format_func=lambda v: t("common.all") if v == ALL else v,
)


def _match(i: dict) -> bool:
    if query:
        q = normalize_inn(query)
        hay = normalize_inn(i["custom_name"] + " " + " ".join(i["inns"]))
        if q not in hay:
            return False
    if status_f != ALL and i["status"] != status_f:
        return False
    if place_f != ALL and i["storage_place"] != place_f:
        return False
    return True


filtered = [i for i in items if _match(i)]
st.caption(t("inventory.count", shown=len(filtered), total=len(items)))

# --- Таблица-обзор ---
if filtered:
    st.dataframe(
        [{
            "": status_dot(i["status"]),
            t("inventory.col.name"): i["custom_name"],
            t("inventory.col.inn"): ", ".join(i["inns"]),
            t("inventory.col.form"): i["dosage_form"] or "—",
            t("inventory.col.strength"): i["strength"] or "—",
            t("inventory.col.qty"): f"{i['quantity_remaining']:g} {i['unit']}",
            t("inventory.col.expiry"): i["effective_expiry"] or t("common.unknown_expiry"),
            t("inventory.col.status"): status_label(i["status"]),
            t("inventory.col.place"): i["storage_place"] or "—",
        } for i in filtered],
        width="stretch", hide_index=True,
    )

st.divider()
st.subheader(t("inventory.cards"))

for i in filtered:
    title = f"{status_dot(i['status'])} {i['custom_name']} — {i['quantity_remaining']:g} {i['unit']}"
    with st.expander(title):
        st.markdown(status_badge(i["status"]), unsafe_allow_html=True)
        meta = (f"**{t('inventory.meta.inn')}:** {', '.join(i['inns']) or '—'} · "
                f"**{t('inventory.meta.form')}:** {i['dosage_form'] or '—'} · "
                f"**{t('inventory.meta.strength')}:** {i['strength'] or '—'}")
        st.markdown(meta)
        st.markdown(
            f"**{t('inventory.meta.expiry')}:** "
            f"{i['effective_expiry'] or t('common.unknown_expiry')} · "
            f"**{t('inventory.meta.place')}:** {i['storage_place'] or '—'} · "
            f"**{t('inventory.meta.source')}:** {i['source']}"
        )
        if i["expiry_precision"] == "month":
            st.caption(t("inventory.month_precision"))

        # Изменение остатка событиями (ТЗ FR-06)
        st.markdown(f"**{t('inventory.change_qty')}**")
        a, b, c, d = st.columns(4)
        step = a.number_input(t("inventory.qty_label"), min_value=0.0, value=1.0, step=1.0, key=f"step_{i['id']}")
        if b.button(t("inventory.btn.used"), key=f"use_{i['id']}"):
            try:
                inv.update_quantity(i["id"], hid, -step, "used")
                st.rerun()
            except inv.NegativeStock as e:
                show_error("inventory.error.negative_stock", e)
        if c.button(t("inventory.btn.added"), key=f"add_{i['id']}"):
            inv.update_quantity(i["id"], hid, step, "added")
            st.rerun()
        if d.button(t("inventory.btn.discarded"), key=f"disc_{i['id']}"):
            try:
                inv.update_quantity(i["id"], hid, -step, "discarded")
                st.rerun()
            except inv.NegativeStock as e:
                show_error("inventory.error.negative_stock", e)

        # Срок после вскрытия (ТЗ FR-11)
        with st.form(f"open_{i['id']}"):
            st.markdown(f"**{t('inventory.open.title')}**")
            oc1, oc2 = st.columns(2)
            opened = oc1.date_input(t("inventory.open.date"), value=date.today(), key=f"od_{i['id']}")
            days = oc2.number_input(t("inventory.open.days"), min_value=0, value=0, step=1, key=f"ad_{i['id']}")
            if st.form_submit_button(t("inventory.open.save")):
                inv.set_opened(i["id"], hid, opened, int(days) or None)
                st.success(t("inventory.open.saved"))
                st.rerun()

        if st.button(t("inventory.delete"), key=f"del_{i['id']}", type="secondary"):
            inv.delete_item(i["id"], hid)
            st.rerun()

if not filtered:
    st.info(t("inventory.empty"))
