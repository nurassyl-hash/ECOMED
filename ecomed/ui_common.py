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
from ecomed.i18n import DEFAULT_LANG, LANG_NAMES, LANGS, normalize_lang, translate  # noqa: E402
from ecomed.models.schemas import (  # noqa: E402
    MATCH_TEXT_KEY,
    STATUS_COLOR,
    STATUS_LABEL_KEY,
    ExpiryStatus,
    MatchLevel,
)


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


# --------------------------------------------------------------------------
# Язык интерфейса
# --------------------------------------------------------------------------
# Источник истины — не-виджетный ключ: Streamlit удаляет состояние виджета,
# который не был отрисован на текущем прогоне.
LANG_KEY = "ui_lang"
LANG_WIDGET_KEY = "ui_lang_select"


def get_lang() -> str:
    """Текущий язык. При первом заходе подхватывается из ?lang= в URL."""
    if LANG_KEY in st.session_state:
        return st.session_state[LANG_KEY]
    try:
        from_url = st.query_params.get("lang")
    except Exception:
        from_url = None
    lang = normalize_lang(from_url)
    st.session_state[LANG_KEY] = lang
    return lang


def set_lang(lang: str) -> None:
    """Запоминает язык в сессии и в URL.

    URL нужен потому, что ссылки в hero (href="add") делают полную перезагрузку
    страницы — сессия Streamlit при этом создаётся заново и session_state пуст.
    """
    lang = normalize_lang(lang)
    st.session_state[LANG_KEY] = lang
    try:
        if lang == DEFAULT_LANG:
            st.query_params.pop("lang", None)
        else:
            st.query_params["lang"] = lang
    except Exception:
        pass


def t(key: str, **kwargs) -> str:
    """Перевод строки на текущий язык интерфейса."""
    return translate(key, get_lang(), **kwargs)


def lang_qs() -> str:
    """Хвост '?lang=kk' для ссылок, ведущих через полную перезагрузку."""
    lang = get_lang()
    return "" if lang == DEFAULT_LANG else f"?lang={lang}"


def status_label(status: str | ExpiryStatus) -> str:
    st_enum = ExpiryStatus(status) if isinstance(status, str) else status
    return t(STATUS_LABEL_KEY[st_enum])


def match_text(level: str | MatchLevel) -> str:
    lvl = MatchLevel(level) if isinstance(level, str) else level
    return t(MATCH_TEXT_KEY[lvl])


def show_error(msg_key: str, exc: Exception | str | None = None) -> None:
    """Локализованное сообщение + технические детали под катом.

    Текст исключений остаётся непереведённым намеренно: он диагностический
    и часто уже английский (сообщения OpenAI SDK).
    """
    st.error(t(msg_key))
    if exc:
        with st.expander(t("common.error_details")):
            st.code(str(exc))


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

/* Нативное меню страниц скрыто: его подписи берутся из имён файлов и не переводятся.
   Вместо него рисуется локализованное меню (_sidebar_nav). */
[data-testid="stSidebarNav"] { display:none; }

/* Навигация page_link: в основной области — крупные кнопки, в сайдбаре — компактный список */
.stMain a[data-testid="stPageLink-NavLink"] {
    border:1px solid var(--brand); border-radius:10px; padding:10px 14px; background:#fff;
}
.stMain a[data-testid="stPageLink-NavLink"]:hover { background:var(--brand-tint); }
.stMain a[data-testid="stPageLink-NavLink"] p { color:var(--brand-dark) !important; font-weight:700; }

section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] {
    border:none; background:transparent; padding:3px 8px; border-radius:8px;
}
section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:hover { background:var(--brand-tint); }

/* Метрики, табы, виджеты, разделители */
[data-testid="stMetricValue"] { color:var(--brand-dark); }
.stTabs [data-baseweb="tab-highlight"] { background:var(--brand) !important; }
.stTabs [aria-selected="true"] { color:var(--brand-dark) !important; }
input[type="checkbox"], input[type="radio"], input[type="range"] { accent-color:var(--brand); }
.stApp hr { border-top-color:#d5e8dd; }
.stProgress > div > div > div { background:var(--brand) !important; }
</style>
"""

# Локализованное меню: путь относительно главного скрипта, ключ перевода, иконка.
NAV: list[tuple[str, str, str]] = [
    ("app.py", "nav.home", "🌿"),
    ("pages/01_inventory.py", "nav.inventory", "📋"),
    ("pages/02_add.py", "nav.add", "➕"),
    ("pages/03_purchase_check.py", "nav.purchase_check", "🛒"),
    ("pages/09_treatment.py", "nav.treatment", "⏰"),
    ("pages/04_analysis.py", "nav.analysis", "📊"),
    ("pages/05_disposal.py", "nav.disposal", "♻️"),
    ("pages/06_family.py", "nav.family", "👪"),
    ("pages/07_settings.py", "nav.settings", "⚙️"),
    ("pages/08_prices.py", "nav.prices", "💊"),
]


def page_setup(title_key: str, icon: str = "💊", sidebar_state: str = "auto") -> None:
    st.set_page_config(
        page_title=f"EcoMed AI — {t(title_key)}", page_icon=icon,
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
        st.caption(t("sidebar.tagline"))
        key_ok = "✅" if settings.llm_enabled else t("sidebar.llm_manual")
        st.caption(f"LLM: {key_ok}")
        _sidebar_lang()
        st.divider()
        _sidebar_nav()
        st.divider()
        _sidebar_prices()


def _on_lang_change() -> None:
    # Колбэк выполняется до перезапуска скрипта, поэтому на том же прогоне
    # и set_page_config, и тело страницы рисуются уже на новом языке.
    set_lang(st.session_state[LANG_WIDGET_KEY])


def _sidebar_lang() -> None:
    current = get_lang()
    st.selectbox(
        t("sidebar.language"), list(LANGS),
        index=list(LANGS).index(current),
        key=LANG_WIDGET_KEY,
        format_func=lambda code: LANG_NAMES[code],
        on_change=_on_lang_change,
    )


def _sidebar_nav() -> None:
    for path, key, icon in NAV:
        st.page_link(path, label=t(key), icon=icon)


def _sidebar_prices() -> None:
    """Быстрое сравнение цен по городу прямо в боковой панели (ТЗ FR-16)."""
    from ecomed.services import price_service

    with st.expander(t("sidebar.prices.title"), expanded=False):
        try:
            cities = price_service.list_cities()
        except Exception:
            cities = []
        if not cities:
            st.caption(t("sidebar.prices.unavailable"))
            return

        default_city = settings.ecomed_default_city
        idx = cities.index(default_city) if default_city in cities else 0
        city = st.selectbox(t("sidebar.prices.city"), cities, index=idx, key="price_city")

        rows = price_service.compare(city)
        meds = [r["trade_name"] for r in rows]
        if not meds:
            st.caption(t("sidebar.prices.no_offers"))
            return
        med = st.selectbox(t("sidebar.prices.med"), meds, key="price_med")

        c = price_service.cheapest(city, med)
        if c:
            cheapest = t("sidebar.prices.cheapest", price=f"{c['price']:.0f}", cur=t("common.currency"))
            st.success(f"{cheapest}\n\n{c['pharmacy']}")
            for o in c["offers"][:4]:
                st.caption(f"{o['pharmacy']} — {o['price']:.0f} {t('common.currency')} · {o['observed_at']}")
            st.caption(t("sidebar.prices.demo_note"))
        st.page_link("pages/08_prices.py", label=t("sidebar.prices.full_link"))


def disclaimer() -> None:
    st.info(t("common.disclaimer"), icon="ℹ️")


def status_badge(status: str) -> str:
    st_enum = ExpiryStatus(status)
    color = STATUS_COLOR[st_enum]
    label = status_label(st_enum)
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
