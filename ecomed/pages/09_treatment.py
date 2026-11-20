"""Приём лекарств: напоминания по назначенной схеме и ручные отметки (FR-19..FR-21)."""
from __future__ import annotations

import sys as _sys
from datetime import timedelta
from pathlib import Path as _Path

_r = _Path(__file__).resolve()
while _r.parent != _r and not (_r / "ecomed" / "__init__.py").exists():
    _r = _r.parent
if str(_r) not in _sys.path:
    _sys.path.insert(0, str(_r))

import streamlit as st

from ecomed.domain import default_times_for
from ecomed.services import inventory_service as inv
from ecomed.services import treatment_service as tr
from ecomed.ui_common import household_id, page_setup, show_error, t

page_setup("nav.treatment", "⏰")
hid = household_id()

st.title(t("treatment.title"))
st.info(t("treatment.disclaimer"), icon="ℹ️")
st.caption(t("treatment.reminder.note"))

items = inv.list_items(hid)
items_by_id = {i["id"]: i for i in items}
now = tr.now_local()

DOSE_BADGE = {
    "overdue": "treatment.due.overdue",
    "due": "treatment.due.now",
    "upcoming": "treatment.due.upcoming",
}


def _person_suffix(person: str | None) -> str:
    return f" · {t('treatment.due.for_person', person=person)}" if person else ""


# --------------------------------------------------------------------------
# 1. Пора принять
# --------------------------------------------------------------------------
st.subheader(t("treatment.due.title"))

doses = tr.pending_doses(hid, now=now)
if not doses:
    st.caption(t("treatment.due.empty"))

for dose in doses:
    slot = dose["scheduled_for"]
    badge = t(DOSE_BADGE[dose["dose_status"]])
    line = (
        f"**{slot.strftime('%d.%m %H:%M')}** · {badge} · {dose['medication_name']} — "
        f"{dose['dose_amount']:g} {dose['unit']}{_person_suffix(dose['person'])}"
    )
    st.markdown(line)
    if dose["item_id"] is not None and not dose["stock_enough"]:
        st.caption(t("treatment.due.no_stock"))

    key = f"{dose['course_id']}_{slot.isoformat()}"
    take_col, skip_col, _rest = st.columns([1, 1, 4])

    if take_col.button(t("treatment.due.take"), key=f"take_{key}", type="primary"):
        try:
            result = tr.confirm_dose(hid, dose["course_id"], slot)
        except tr.DoseAlreadyRecorded:
            st.warning(t("treatment.already"))
        else:
            if result["stock_applied"]:
                st.success(t("treatment.confirmed",
                             amount=f"{result['quantity']:g}", unit=dose["unit"]))
            else:
                st.warning(t("treatment.confirmed_no_stock"))
            st.rerun()

    if skip_col.button(t("treatment.due.skip"), key=f"skip_{key}"):
        try:
            tr.confirm_dose(hid, dose["course_id"], slot, taken=False)
        except tr.DoseAlreadyRecorded:
            st.warning(t("treatment.already"))
        else:
            st.info(t("treatment.skipped"))
            st.rerun()

stats = tr.adherence(hid, days=7, now=now)
if stats["recorded"]:
    st.caption(t("treatment.adherence", days=stats["days"],
                 taken=stats["taken"], skipped=stats["skipped"]))

st.divider()

# --------------------------------------------------------------------------
# 2. Ручная отметка приёма (без назначения)
# --------------------------------------------------------------------------
st.subheader(t("treatment.manual.title"))
st.caption(t("treatment.manual.hint"))

NO_ITEM = -1

with st.form("manual_intake"):
    m1, m2 = st.columns(2)
    manual_item = m1.selectbox(
        t("treatment.manual.item"),
        [NO_ITEM] + [i["id"] for i in items],
        format_func=lambda i: (
            t("treatment.manual.other") if i == NO_ITEM
            else f"{items_by_id[i]['custom_name']} ({items_by_id[i]['quantity_remaining']:g} {items_by_id[i]['unit']})"
        ),
    )
    manual_name = m2.text_input(
        t("treatment.manual.name"),
        value="" if manual_item == NO_ITEM else items_by_id[manual_item]["custom_name"],
    )
    m3, m4 = st.columns(2)
    manual_qty = m3.number_input(t("treatment.manual.qty"), min_value=0.0, value=1.0, step=1.0)
    manual_person = m4.text_input(t("treatment.manual.person"), value="")

    if st.form_submit_button(t("treatment.manual.submit"), type="primary"):
        try:
            fallback_name = (
                "" if manual_item == NO_ITEM else items_by_id[manual_item]["custom_name"]
            )
            result = tr.log_manual_intake(
                hid,
                medication_name=manual_name.strip() or fallback_name,
                quantity=manual_qty,
                item_id=None if manual_item == NO_ITEM else manual_item,
                person=manual_person or None,
            )
        except (ValueError, PermissionError) as exc:
            show_error("treatment.form.error", exc)
        else:
            if result["stock_applied"]:
                unit = items_by_id[manual_item]["unit"] if manual_item != NO_ITEM else ""
                st.success(t("treatment.confirmed", amount=f"{result['quantity']:g}", unit=unit))
            else:
                st.warning(t("treatment.confirmed_no_stock"))
            st.rerun()

st.divider()

# --------------------------------------------------------------------------
# 3. Активные схемы лечения
# --------------------------------------------------------------------------
st.subheader(t("treatment.courses.title"))

courses = tr.list_courses(hid)
if not courses:
    st.caption(t("treatment.courses.empty"))

for course in courses:
    header = course["medication_name"] + _person_suffix(course["person"])
    with st.expander(header, expanded=course["stock_short"]):
        if course["end_date"]:
            st.markdown(t("treatment.courses.period",
                          start=course["start_date"], end=course["end_date"]))
        else:
            st.markdown(t("treatment.courses.open_ended", start=course["start_date"]))

        st.markdown(t("treatment.courses.schedule",
                      amount=f"{course['dose_amount']:g}", unit=course["unit"],
                      per_day=course["per_day"], times=", ".join(course["times"])))

        if course["item_id"] is None:
            st.caption(t("treatment.courses.stock_none"))
        elif course["stock_runs_out_on"]:
            st.caption(t("treatment.courses.stock_left", date=course["stock_runs_out_on"]))
        if course["stock_short"]:
            st.warning(t("treatment.courses.stock_short"))

        if course["note"]:
            st.caption(course["note"])

        fin_col, cancel_col, _rest = st.columns([1, 1, 3])
        if fin_col.button(t("treatment.courses.finish"), key=f"fin_{course['id']}"):
            tr.set_course_status(course["id"], hid, tr.STATUS_FINISHED)
            st.success(t("treatment.courses.status_changed"))
            st.rerun()
        if cancel_col.button(t("treatment.courses.cancel"), key=f"cnl_{course['id']}"):
            tr.set_course_status(course["id"], hid, tr.STATUS_CANCELLED)
            st.success(t("treatment.courses.status_changed"))
            st.rerun()

# --------------------------------------------------------------------------
# 4. Новая схема лечения
# --------------------------------------------------------------------------
with st.expander(t("treatment.form.title")):
    # Число приёмов выбирается вне формы: часы должны пересчитаться сразу.
    per_day = st.number_input(t("treatment.form.per_day"), min_value=1, max_value=6,
                              value=3, step=1, key="course_per_day")

    with st.form("new_course"):
        c1, c2 = st.columns(2)
        course_item = c1.selectbox(
            t("treatment.form.item"),
            [NO_ITEM] + [i["id"] for i in items],
            format_func=lambda i: (
                t("treatment.manual.other") if i == NO_ITEM
                else f"{items_by_id[i]['custom_name']} ({items_by_id[i]['quantity_remaining']:g} {items_by_id[i]['unit']})"
            ),
            key="course_item",
        )
        course_name = c2.text_input(
            t("treatment.form.name"),
            value="" if course_item == NO_ITEM else items_by_id[course_item]["custom_name"],
        )

        c3, c4 = st.columns(2)
        dose_amount = c3.number_input(t("treatment.form.dose"), min_value=0.0, value=1.0, step=0.5)
        course_person = c4.text_input(t("treatment.form.person"), value="")

        times_raw = st.text_input(
            t("treatment.form.times"),
            value=", ".join(default_times_for(int(per_day))),
            help=t("treatment.form.times_help"),
        )

        c5, c6 = st.columns(2)
        start_date = c5.date_input(t("treatment.form.start"), value=now.date())
        open_ended = c6.checkbox(t("treatment.form.open_ended"), value=False)
        end_date = c6.date_input(
            t("treatment.form.end"), value=now.date() + timedelta(days=6), disabled=open_ended,
        )

        course_note = st.text_input(t("treatment.form.note"),
                                    placeholder=t("treatment.form.note_ph"))

        if st.form_submit_button(t("treatment.form.submit"), type="primary"):
            try:
                course_fallback = (
                    "" if course_item == NO_ITEM else items_by_id[course_item]["custom_name"]
                )
                tr.add_course(
                    hid,
                    medication_name=course_name.strip() or course_fallback,
                    dose_amount=dose_amount,
                    times=[x.strip() for x in times_raw.split(",") if x.strip()],
                    start_date=start_date,
                    end_date=None if open_ended else end_date,
                    item_id=None if course_item == NO_ITEM else course_item,
                    person=course_person or None,
                    note=course_note or None,
                )
            except (ValueError, PermissionError) as exc:
                show_error("treatment.form.error", exc)
            else:
                st.success(t("treatment.form.saved", section=t("treatment.due.title")))
                st.rerun()

st.divider()

# --------------------------------------------------------------------------
# 5. История приёмов
# --------------------------------------------------------------------------
st.subheader(t("treatment.history.title"))

history = tr.intake_history(hid, limit=50)
if not history:
    st.caption(t("treatment.history.empty"))
else:
    st.dataframe(
        [{
            t("treatment.history.col.when"): e["taken_at"].strftime("%d.%m.%Y %H:%M"),
            t("treatment.history.col.med"): e["medication_name"],
            t("treatment.history.col.qty"): f"{e['quantity']:g} {e['unit']}",
            t("treatment.history.col.person"): e["person"] or "—",
            t("treatment.history.col.kind"): "{} · {}".format(
                t("treatment.history.planned") if e["planned"] else t("treatment.history.manual"),
                t("treatment.history.taken") if e["status"] == "taken"
                else t("treatment.history.skipped"),
            ),
            t("treatment.history.col.stock"): (
                t("treatment.history.stock_yes") if e["stock_applied"]
                else t("treatment.history.stock_no")
            ),
        } for e in history],
        width="stretch", hide_index=True,
    )
