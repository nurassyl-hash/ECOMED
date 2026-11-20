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
from ecomed.ui_common import household_id, page_setup, status_label, t

page_setup("nav.disposal", "♻️")
hid = household_id()

st.title(t("disposal.title"))
st.info(t("disposal.disclaimer"), icon="📘")

cities = sorted({p["city"] for p in disp.list_points() if p["city"]})
default_city = settings.ecomed_default_city
idx = cities.index(default_city) if default_city in cities else 0
city = st.selectbox(t("disposal.city"), cities or ["—"], index=idx if cities else 0)

points = disp.list_points(city)

if not points:
    st.warning(t("disposal.no_point"), icon="⚠️")
else:
    verified_points = [p for p in points if p["status"] == "verified"]
    st.subheader(t("disposal.points.title", city=city))
    st.caption(t("disposal.points.count", total=len(points), verified=len(verified_points)))

    for p in points:
        verified = p["status"] == "verified"
        badge = t("disposal.badge.verified") if verified else t("disposal.badge.demo")
        src = (f"[{t('disposal.source')}]({p['source_url']})"
               if str(p["source_url"]).startswith("http") else t("disposal.source.demo"))
        no_geo = "" if (p["lat"] and p["lon"]) else t("disposal.no_geo")
        st.markdown(
            f"**{p['name']}**  \n"
            f"{p['address']} · {t('disposal.accepts')}: {p['accepted_types']}  \n"
            f"{t('disposal.status')}: {badge} · {t('disposal.checked')}: "
            f"{p['verified_at'] or '—'} · {src}{no_geo}"
        )

    if verified_points:
        st.caption(t("disposal.not_accepted"))
    else:
        st.warning(t("disposal.no_verified"))

    # Карта (гео помогает показать, но не доказывает приём отходов — ТЗ 8)
    df = pd.DataFrame([{"lat": p["lat"], "lon": p["lon"]} for p in points if p["lat"] and p["lon"]])
    if not df.empty:
        st.map(df, size=40)
        st.caption(t("disposal.map_note"))

    # --- Отметка передачи ---
    st.divider()
    st.subheader(t("disposal.record.title"))
    items = inv.list_items(hid)
    expired = [i for i in items if i["status"] == "expired"] or items
    with st.form("disposal"):
        item_opt = st.selectbox(
            t("disposal.record.what"), expired,
            format_func=lambda i: f"{i['custom_name']} ({status_label(i['status'])})",
        )
        point_opt = st.selectbox(t("disposal.record.point"), points, format_func=lambda p: p["name"])
        count = st.number_input(t("disposal.record.count"), min_value=1, value=1, step=1)
        if st.form_submit_button(t("disposal.record.submit"), type="primary"):
            disp.record_disposal(hid, point_opt["id"], int(count), item_id=item_opt["id"])
            st.success(t("disposal.record.ok"))
            st.balloons()
