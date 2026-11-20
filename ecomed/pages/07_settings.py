"""Настройки: язык, город, согласия, удаление данных (ТЗ раздел 9, 16)."""
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
from ecomed.ui_common import household_id, page_setup, t

page_setup("nav.settings", "⚙️")
household_id()

st.title(t("settings.title"))

st.subheader(t("settings.lang.section"))
st.caption(t("settings.lang.hint"))
st.text_input(t("settings.city"), value=settings.ecomed_default_city)

st.subheader(t("settings.consent.title"))
st.checkbox(t("settings.consent.data"), value=True)
st.checkbox(t("settings.consent.photo"), value=False)
st.caption(t("settings.consent.note"))

st.subheader(t("settings.notify.title"))
st.checkbox(t("settings.notify.expiry"), value=True)
st.checkbox(t("settings.notify.dup"), value=True)

st.subheader(t("settings.data.title"))
st.caption(t("settings.data.note"))
if st.button(t("settings.data.reset"), type="secondary"):
    from ecomed.db.database import _engine
    from ecomed.db.models import Base
    from ecomed.db.seed import seed_demo
    Base.metadata.drop_all(_engine)
    st.cache_resource.clear()
    seed_demo()
    st.success(t("settings.data.reset_ok", page=t("nav.home")))
