"""Общие помощники для страниц Streamlit."""
from __future__ import annotations

import base64
import mimetypes
import sys
from functools import lru_cache
from pathlib import Path


def ensure_path() -> None:
    """Добавляет корень проекта (папку, содержащую пакет ecomed) в sys.path.

    Нужно, потому что Streamlit кладёт в sys.path каталог запускаемого скрипта,
    а не корень репозитория.
    """
    root = Path(__file__).resolve()
    while root.parent != root and not (root / "ecomed" / "__init__.py").exists():
        root = root.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


ensure_path()

import streamlit as st  # noqa: E402

from ecomed.config import settings  # noqa: E402
from ecomed.db.seed import seed_demo  # noqa: E402
from ecomed.models.schemas import STATUS_COLOR, STATUS_LABEL, ExpiryStatus  # noqa: E402
from ecomed.policies.medical_safety import DISCLAIMER  # noqa: E402


@st.cache_resource
def _bootstrap() -> int:
    """Однократно создаёт демо-данные и возвращает household_id."""
    return seed_demo()


def household_id() -> int:
    return _bootstrap()


ASSETS = Path(__file__).resolve().parent / "assets"


@lru_cache(maxsize=8)
def asset_data_uri(filename: str) -> str:
    """Возвращает data-URI ассета (base64) для встраивания в HTML/CSS. '' если нет файла."""
    path = ASSETS / filename
    if not path.exists():
        return ""
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


# Фирменная тема EcoMed — применяется на каждой странице.
BRAND = "#0a815c"
BRAND_DARK = "#087452"
BRAND_TINT = "#e2f6ec"

THEME_CSS = """
<style>
:root { --brand:#0a815c; --brand-dark:#087452; --brand-tint:#e2f6ec; }
.stApp { background:#f4faf6; }

.stApp h1 { color:#0d3d2c; }
.stApp h2, .stApp h3 { color:var(--brand-dark); }
.stApp a, .stApp a:visited { color:var(--brand-dark); }

/* Кнопки: вторичные — контур, первичные — заливка фирменным зелёным */
button[kind="secondary"] {
    border:1px solid var(--brand) !important; color:var(--brand-dark) !important;
    background:#fff !important; border-radius:10px !important; font-weight:700 !important;
}
button[kind="secondary"]:hover { background:var(--brand-tint) !important; }
button[kind="primary"] {
    background:var(--brand) !important; border:1px solid var(--brand) !important;
    color:#fff !important; border-radius:10px !important; font-weight:700 !important;
}
button[kind="primary"]:hover { background:var(--brand-dark) !important; border-color:var(--brand-dark) !important; }

/* Навигация page_link */
a[data-testid="stPageLink-NavLink"] {
    border:1px solid var(--brand); border-radius:10px; padding:10px 14px; background:#fff;
}
a[data-testid="stPageLink-NavLink"]:hover { background:var(--brand-tint); }
a[data-testid="stPageLink-NavLink"] p { color:var(--brand-dark) !important; font-weight:700; }

/* Метрики, табы, виджеты, разделители */
[data-testid="stMetricValue"] { color:var(--brand-dark); }
.stTabs [data-baseweb="tab-highlight"] { background:var(--brand) !important; }
.stTabs [aria-selected="true"] { color:var(--brand-dark) !important; }
input[type="checkbox"], input[type="radio"], input[type="range"] { accent-color:var(--brand); }
[data-testid="stSidebarNav"] a[aria-current="page"] span { color:var(--brand-dark) !important; font-weight:700; }
.stApp hr { border-top-color:#d5e8dd; }
.stProgress > div > div > div { background:var(--brand) !important; }
</style>
"""


def page_setup(title: str, icon: str = "💊", sidebar_state: str = "auto") -> None:
    st.set_page_config(
        page_title=f"EcoMed AI — {title}", page_icon=icon,
        layout="wide", initial_sidebar_state=sidebar_state,
    )
    st.html(THEME_CSS)
    logo_path = ASSETS / "logo.png"
    if logo_path.exists():
        try:
            st.logo(str(logo_path), size="large")
        except Exception:
            pass
    with st.sidebar:
        st.markdown("### EcoMed AI")
        st.caption("Умная экологичная домашняя аптечка")
        key_ok = "✅" if settings.llm_enabled else "⚠️ ручной режим"
        st.caption(f"LLM: {key_ok}")
        st.divider()
        _sidebar_prices()


def _sidebar_prices() -> None:
    """Быстрое сравнение цен по городу прямо в боковой панели (ТЗ FR-16)."""
    from ecomed.services import price_service

    with st.expander("💊 Цены в аптеках города", expanded=False):
        try:
            cities = price_service.list_cities()
        except Exception:
            cities = []
        if not cities:
            st.caption("Данные о ценах недоступны.")
            return

        default_city = settings.ecomed_default_city
        idx = cities.index(default_city) if default_city in cities else 0
        city = st.selectbox("Город", cities, index=idx, key="price_city")

        rows = price_service.compare(city)
        meds = [r["trade_name"] for r in rows]
        if not meds:
            st.caption("Нет предложений для этого города.")
            return
        med = st.selectbox("Препарат", meds, key="price_med")

        c = price_service.cheapest(city, med)
        if c:
            st.success(f"Дешевле всего: **{c['price']:.0f} ₸**\n\n{c['pharmacy']}")
            for o in c["offers"][:4]:
                st.caption(f"{o['pharmacy']} — {o['price']:.0f} ₸ · {o['observed_at']}")
            st.caption("Демонстрационные данные. Проверьте актуальную цену у аптеки.")
        st.page_link("pages/08_prices.py", label="→ Полное сравнение цен")


def disclaimer() -> None:
    st.info(DISCLAIMER, icon="ℹ️")


def status_badge(status: str) -> str:
    st_enum = ExpiryStatus(status)
    color = STATUS_COLOR[st_enum]
    label = STATUS_LABEL[st_enum]
    return (
        f"<span style='background:{color};color:white;padding:2px 8px;"
        f"border-radius:10px;font-size:0.8em;white-space:nowrap'>{label}</span>"
    )


def status_dot(status: str) -> str:
    """Текстовый дублирующий сигнал (доступность: цвет — не единственный сигнал)."""
    return {
        "expired": "⛔",
        "critical": "🟠",
        "soon": "🟡",
        "ok": "🟢",
        "unknown": "⚪",
    }.get(status, "⚪")
