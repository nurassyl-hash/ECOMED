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
from ecomed.models.schemas import STATUS_LABEL, ExpiryStatus
from ecomed.services import inventory_service as inv
from ecomed.ui_common import household_id, page_setup, status_badge, status_dot

page_setup("Моя аптечка", "📋")
hid = household_id()

st.title("📋 Моя аптечка")

items = inv.list_items(hid)

# --- Фильтры ---
f1, f2, f3 = st.columns([2, 1, 1])
query = f1.text_input("Поиск по названию или МНН", "")
status_opts = ["все"] + [s.value for s in ExpiryStatus]
status_f = f2.selectbox("Статус срока", status_opts, format_func=lambda v: "Все" if v == "все" else STATUS_LABEL[ExpiryStatus(v)])
places = sorted({i["storage_place"] for i in items if i["storage_place"]})
place_f = f3.selectbox("Место хранения", ["все", *places])


def _match(i: dict) -> bool:
    if query:
        q = normalize_inn(query)
        hay = normalize_inn(i["custom_name"] + " " + " ".join(i["inns"]))
        if q not in hay:
            return False
    if status_f != "все" and i["status"] != status_f:
        return False
    if place_f != "все" and i["storage_place"] != place_f:
        return False
    return True


filtered = [i for i in items if _match(i)]
st.caption(f"Показано {len(filtered)} из {len(items)} позиций")

# --- Таблица-обзор ---
if filtered:
    st.dataframe(
        [{
            "": status_dot(i["status"]),
            "Название": i["custom_name"],
            "МНН": ", ".join(i["inns"]),
            "Форма": i["dosage_form"] or "—",
            "Дозировка": i["strength"] or "—",
            "Остаток": f"{i['quantity_remaining']:g} {i['unit']}",
            "Срок": i["effective_expiry"] or "неизвестен",
            "Статус": STATUS_LABEL[ExpiryStatus(i["status"])],
            "Место": i["storage_place"] or "—",
        } for i in filtered],
        width="stretch", hide_index=True,
    )

st.divider()
st.subheader("Карточки и действия")

for i in filtered:
    title = f"{status_dot(i['status'])} {i['custom_name']} — {i['quantity_remaining']:g} {i['unit']}"
    with st.expander(title):
        st.markdown(status_badge(i["status"]), unsafe_allow_html=True)
        meta = f"**МНН:** {', '.join(i['inns']) or '—'} · **Форма:** {i['dosage_form'] or '—'} · **Дозировка:** {i['strength'] or '—'}"
        st.markdown(meta)
        st.markdown(f"**Срок (эффективный):** {i['effective_expiry'] or 'неизвестен'} · **Место:** {i['storage_place'] or '—'} · **Источник:** {i['source']}")
        if i["expiry_precision"] == "month":
            st.caption("Срок указан с точностью до месяца.")

        # Изменение остатка событиями (ТЗ FR-06)
        st.markdown("**Изменить остаток**")
        a, b, c, d = st.columns(4)
        step = a.number_input("Кол-во", min_value=0.0, value=1.0, step=1.0, key=f"step_{i['id']}")
        if b.button("➖ Использовано", key=f"use_{i['id']}"):
            try:
                inv.update_quantity(i["id"], hid, -step, "used")
                st.rerun()
            except inv.NegativeStock as e:
                st.error(f"Операция отклонена: {e}")
        if c.button("➕ Добавлено", key=f"add_{i['id']}"):
            inv.update_quantity(i["id"], hid, step, "added")
            st.rerun()
        if d.button("🗑 Выброшено/передано", key=f"disc_{i['id']}"):
            try:
                inv.update_quantity(i["id"], hid, -step, "discarded")
                st.rerun()
            except inv.NegativeStock as e:
                st.error(f"Операция отклонена: {e}")

        # Срок после вскрытия (ТЗ FR-11)
        with st.form(f"open_{i['id']}"):
            st.markdown("**Отметить вскрытие (срок после открытия)**")
            oc1, oc2 = st.columns(2)
            opened = oc1.date_input("Дата открытия", value=date.today(), key=f"od_{i['id']}")
            days = oc2.number_input("Годен после вскрытия, дней", min_value=0, value=0, step=1, key=f"ad_{i['id']}")
            if st.form_submit_button("Сохранить вскрытие"):
                inv.set_opened(i["id"], hid, opened, int(days) or None)
                st.success("Сохранено. Используется более ранняя из дат.")
                st.rerun()

        if st.button("Удалить запись", key=f"del_{i['id']}", type="secondary"):
            inv.delete_item(i["id"], hid)
            st.rerun()

if not filtered:
    st.info("Нет позиций по заданным фильтрам.")
