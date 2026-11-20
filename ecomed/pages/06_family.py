"""Семья: участники и роли (ТЗ раздел 3, FR-02)."""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_r = _Path(__file__).resolve()
while _r.parent != _r and not (_r / "ecomed" / "__init__.py").exists():
    _r = _r.parent
if str(_r) not in _sys.path:
    _sys.path.insert(0, str(_r))

import streamlit as st

from ecomed.ui_common import household_id, page_setup, t

page_setup("nav.family", "👪")
household_id()

st.title(t("family.title"))
st.caption(t("family.subtitle"))

st.subheader(t("family.demo.title"))
st.markdown("- " + t("family.demo.member"))

st.subheader(t("family.invite.title"))
st.text_input(t("family.invite.link"), value="https://ecomed.demo/join/DEMO-2026", disabled=True)
st.caption(t("family.invite.note"))

st.subheader(t("family.roles.title"))
st.table([
    {
        t("family.col.role"): t(f"family.role.{role}"),
        t("family.col.rights"): t(f"family.role.{role}.rights"),
        t("family.col.limits"): t(f"family.role.{role}.limits"),
    }
    for role in ("owner", "editor", "viewer", "dataadmin")
])
