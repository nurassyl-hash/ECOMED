"""Добавить препарат: по фото (OCR) или вручную (ТЗ FR-03, 7.1)."""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_r = _Path(__file__).resolve()
while _r.parent != _r and not (_r / "ecomed" / "__init__.py").exists():
    _r = _r.parent
if str(_r) not in _sys.path:
    _sys.path.insert(0, str(_r))

import streamlit as st

from ecomed.config import settings
from ecomed.services import scan_service
from ecomed.ui_common import household_id, page_setup, show_error, t

page_setup("nav.add", "➕")
hid = household_id()

st.title(t("add.title"))

# --- Выбор способа: фото или ручной ввод ---
MODE_PHOTO, MODE_MANUAL = "photo", "manual"
mode = st.radio(
    t("add.mode.label"),
    [MODE_PHOTO, MODE_MANUAL],
    horizontal=True,
    format_func=lambda m: t(f"add.mode.{m}"),
)
manual = mode == MODE_MANUAL

if manual:
    st.session_state.pop("scan", None)  # не подставлять старое распознавание
    st.caption(t("add.manual_hint"))


def _conf_note(pkg_conf: dict, field: str) -> None:
    c = pkg_conf.get(field)
    if c is None:
        return
    if c >= 0.85:
        st.caption(t("add.conf.high", pct=f"{c:.0%}"))
    elif c >= 0.60:
        st.caption(t("add.conf.mid", pct=f"{c:.0%}"))
    else:
        st.caption(t("add.conf.low", pct=f"{c:.0%}"))


# --- Блок фото (только в режиме фото) ---
if not manual:
    st.caption(t("add.photo_hint"))
    if not settings.llm_enabled:
        st.warning(t("add.warn.no_vision"), icon="⚠️")

    image_bytes = None
    mime = "image/jpeg"
    tab_cam, tab_up = st.tabs([t("add.tab.camera"), t("add.tab.upload")])
    with tab_cam:
        cam = st.camera_input(t("add.camera"))
        if cam is not None:
            image_bytes = cam.getvalue()
    with tab_up:
        up = st.file_uploader(t("add.uploader"), type=["jpg", "jpeg", "png"])
        if up is not None:
            image_bytes = up.getvalue()
            mime = "image/png" if up.name.lower().endswith("png") else "image/jpeg"

    consent = st.checkbox(t("add.consent"), value=False)
    if image_bytes is not None and st.button(t("add.recognize"), type="primary", disabled=not consent):
        with st.spinner(t("add.spinner")):
            st.session_state["scan"] = scan_service.create_scan(hid, image_bytes, mime)

    scan = st.session_state.get("scan")
    if scan and not scan["provider_ok"]:
        show_error("add.error.ocr", scan["error"])
else:
    scan = None

pkg = (scan or {}).get("package", {})
conf = pkg.get("field_confidence", {})

st.divider()
st.subheader(t("add.card"))

with st.form("confirm"):
    trade = st.text_input(t("add.field.trade"), value=pkg.get("trade_name") or "")
    if not manual:
        _conf_note(conf, "trade_name")

    inns_default = ", ".join(a["name"] for a in pkg.get("active_ingredients", []))
    inns = st.text_input(t("add.field.inns"), value=inns_default,
                         help=t("add.field.inns_help"))
    if not manual:
        _conf_note(conf, "active_ingredients")

    col1, col2 = st.columns(2)
    form = col1.text_input(t("add.field.form"), value=pkg.get("dosage_form") or "",
                          placeholder=t("add.field.form_ph"))
    strengths = [a.get("strength") for a in pkg.get("active_ingredients", []) if a.get("strength")]
    strength = col2.text_input(t("add.field.strength"), value=(strengths[0] if strengths else ""),
                              placeholder=t("add.field.strength_ph"))

    col3, col4, col5 = st.columns(3)
    qty = col3.number_input(t("add.field.qty"), min_value=0.0, value=float(pkg.get("package_quantity", {}).get("value", 0) or 0), step=1.0)
    unit = col4.text_input(t("add.field.unit"), value=pkg.get("package_quantity", {}).get("unit", "таблетка") or "таблетка")
    expiry = col5.text_input(t("add.field.expiry"), value=pkg.get("expiry_date") or "",
                             placeholder="2027-05")
    if not manual:
        _conf_note(conf, "expiry_date")

    storage = st.text_input(t("add.field.storage"), value="", placeholder=t("add.field.storage_ph"))

    submitted = st.form_submit_button(t("add.save"), type="primary")

if submitted:
    if not trade.strip() or not inns.strip() or qty <= 0:
        st.error(t("add.error.required"))
    else:
        item_id = scan_service.confirm_inventory_item(
            hid, (scan or {}).get("scan_id"),
            custom_name=trade.strip(),
            inns=[x.strip() for x in inns.split(",") if x.strip()],
            dosage_form=form.strip() or None,
            strength=strength.strip() or None,
            quantity=qty, unit=unit.strip() or "таблетка",
            expiry_raw=expiry.strip() or None,
            storage_place=storage.strip() or None,
        )
        st.session_state.pop("scan", None)
        st.success(t("add.saved", id=item_id, section=t("nav.analysis")))
        st.balloons()
