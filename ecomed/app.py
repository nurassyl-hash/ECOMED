"""EcoMed AI — Главная (дашборд). Точка входа: streamlit run ecomed/app.py"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_r = _Path(__file__).resolve()
while _r.parent != _r and not (_r / "ecomed" / "__init__.py").exists():
    _r = _r.parent
if str(_r) not in _sys.path:
    _sys.path.insert(0, str(_r))

from ecomed.ui_common import (  # noqa: E402
    asset_data_uri,
    disclaimer,
    household_id,
    page_setup,
    status_badge,
    status_dot,
)

import streamlit as st

from ecomed.services import inventory_service as inv
from ecomed.services import matching_service as match
from ecomed.services import report_service as rep

page_setup("Главная", "🌿")
hid = household_id()

items = inv.list_items(hid)
metrics = rep.compute_metrics(hid)
soon_cnt = (
    metrics.by_status.get("expired", 0)
    + metrics.by_status.get("critical", 0)
    + metrics.by_status.get("soon", 0)
)

hero_uri = asset_data_uri("hero.jpg")
logo_uri = asset_data_uri("logo.png")

# --- Hero (адаптировано из фирменного дизайна EcoMedd) ---
HERO_CSS = """
<style>
.block-container { max-width: 100%; padding: 0 0 1.5rem 0; }
header[data-testid="stHeader"] { background: transparent; }
.stApp { background: #f4faf6; }

.ecomed-hero {
    position: relative; min-height: 520px; overflow: hidden;
    border-radius: 0 0 26px 26px; margin-bottom: 26px;
    background: linear-gradient(90deg, rgba(255,255,255,0.08), rgba(255,255,255,0.02)),
                url("__HERO__");
    background-size: cover; background-position: center right;
}
.ecomed-hero-overlay {
    position: absolute; inset: 0; width: 64%;
    background: linear-gradient(135deg, rgba(10,129,92,0.98), rgba(24,164,126,0.92));
    clip-path: polygon(0 0, 88% 0, 65% 100%, 0 100%);
}
.ecomed-hero-content {
    position: relative; z-index: 2; width: 48%;
    padding: 40px 0 46px 48px; color: #fff;
}
.ecomed-logo { display: flex; align-items: center; gap: 14px; margin-bottom: 54px; }
.ecomed-logo-icon {
    width: 60px; height: 60px; border-radius: 16px; overflow: hidden;
    box-shadow: 0 6px 16px rgba(0,0,0,0.25); flex: 0 0 auto;
}
.ecomed-logo-icon img { width: 100%; height: 100%; object-fit: cover; display: block; }
.ecomed-logo-name { font-size: 26px; line-height: 1.05; font-weight: 750; }
.ecomed-logo-desc { margin-top: 4px; font-size: 13px; opacity: 0.85; }
.ecomed-hero-title { max-width: 480px; font-size: 40px; line-height: 1.16; font-weight: 450; margin-bottom: 18px; }
.ecomed-hero-title strong { font-weight: 800; }
.ecomed-hero-sub { max-width: 440px; font-size: 17px; line-height: 1.55; opacity: 0.92; margin-bottom: 30px; }
.ecomed-buttons { display: flex; gap: 12px; flex-wrap: wrap; }
.ecomed-btn {
    display: inline-block; padding: 13px 22px; border-radius: 12px; font-weight: 700;
    text-decoration: none !important; transition: 0.2s ease;
}
.ecomed-btn-primary { background: #fff; color: #087452 !important; }
.ecomed-btn-secondary { border: 1px solid rgba(255,255,255,0.65); color: #fff !important; background: rgba(255,255,255,0.12); }
.ecomed-btn:hover { transform: translateY(-2px); }

.ecomed-preview {
    position: absolute; z-index: 3; right: 5%; top: 24%; width: 40%; min-height: 260px;
    padding: 22px; color: #17382d; background: rgba(255,255,255,0.96);
    border: 9px solid #16241f; border-radius: 24px; box-shadow: 0 22px 55px rgba(0,0,0,0.28);
}
.ecomed-preview-head { display: flex; justify-content: space-between; align-items: center; }
.ecomed-preview-logo { color: #0a815c; font-size: 17px; font-weight: 800; }
.ecomed-preview-status { color: #13865f; background: #e2f6ec; padding: 6px 10px; border-radius: 20px; font-size: 12px; }
.ecomed-preview-title { margin-top: 26px; font-size: 25px; font-weight: 800; }
.ecomed-preview-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 20px; }
.ecomed-preview-card { padding: 15px 12px; background: #f1f8f4; border-radius: 14px; }
.ecomed-preview-num { color: #087452; font-size: 25px; font-weight: 800; }
.ecomed-preview-lbl { margin-top: 4px; color: #667a70; font-size: 12px; }

@media (max-width: 900px) {
    .ecomed-hero { min-height: 760px; }
    .ecomed-hero-overlay { width: 100%; clip-path: none; }
    .ecomed-hero-content { width: auto; padding: 32px 22px; }
    .ecomed-logo { margin-bottom: 40px; }
    .ecomed-hero-title { font-size: 32px; }
    .ecomed-preview { top: 430px; right: 5%; width: 88%; box-sizing: border-box; }
}
</style>
"""

HERO_HTML = """
<section class="ecomed-hero">
    <div class="ecomed-hero-overlay"></div>
    <div class="ecomed-hero-content">
        <div class="ecomed-logo">
            <div class="ecomed-logo-icon"><img src="__LOGO__" alt="EcoMed AI"></div>
            <div>
                <div class="ecomed-logo-name">EcoMed AI</div>
                <div class="ecomed-logo-desc">Умная экологичная аптечка</div>
            </div>
        </div>
        <div class="ecomed-hero-title">
            Домашняя аптечка без <strong>лишних покупок и просроченных лекарств</strong>
        </div>
        <div class="ecomed-hero-sub">
            Сканируйте упаковки, находите дубликаты, контролируйте срок годности
            и узнавайте, как безопасно утилизировать лекарства.
        </div>
        <div class="ecomed-buttons">
            <a class="ecomed-btn ecomed-btn-primary" href="add" target="_self">Добавить препарат</a>
            <a class="ecomed-btn ecomed-btn-secondary" href="purchase_check" target="_self">Проверить покупку</a>
        </div>
    </div>
    <div class="ecomed-preview">
        <div class="ecomed-preview-head">
            <div class="ecomed-preview-logo">EcoMed AI</div>
            <div class="ecomed-preview-status">Аптечка проверена</div>
        </div>
        <div class="ecomed-preview-title">Обзор домашней аптечки</div>
        <div class="ecomed-preview-grid">
            <div class="ecomed-preview-card"><div class="ecomed-preview-num">__TOTAL__</div><div class="ecomed-preview-lbl">Всего препаратов</div></div>
            <div class="ecomed-preview-card"><div class="ecomed-preview-num">__SOON__</div><div class="ecomed-preview-lbl">Скоро истекает срок</div></div>
            <div class="ecomed-preview-card"><div class="ecomed-preview-num">__DUP__</div><div class="ecomed-preview-lbl">Найдено дубликатов</div></div>
        </div>
    </div>
</section>
"""

hero = (HERO_CSS + HERO_HTML)
hero = (hero.replace("__HERO__", hero_uri).replace("__LOGO__", logo_uri)
        .replace("__TOTAL__", str(metrics.total_items))
        .replace("__SOON__", str(soon_cnt))
        .replace("__DUP__", str(metrics.duplicate_groups)))
st.html(hero)

# --- Навигация (native page_link — надёжно работает в multipage) ---
st.subheader("Быстрые действия")
n1, n2, n3 = st.columns(3)
n1.page_link("pages/03_purchase_check.py", label="🛒 Проверить перед покупкой", width="stretch")
n2.page_link("pages/02_add.py", label="➕ Добавить препарат", width="stretch")
n3.page_link("pages/01_inventory.py", label="📋 Моя аптечка", width="stretch")

disclaimer()
st.divider()

# --- Ближайшие действия ---
left, right = st.columns(2)
with left:
    st.subheader("⏳ Требуют внимания")
    attention = [i for i in items if i["status"] in ("expired", "critical", "soon")]
    attention.sort(key=lambda x: (x["effective_expiry"] or "9999"))
    if not attention:
        st.success("Нет позиций с близким сроком.")
    for i in attention:
        st.markdown(
            f"{status_dot(i['status'])} **{i['custom_name']}** — до {i['effective_expiry'] or '—'} "
            f"{status_badge(i['status'])}",
            unsafe_allow_html=True,
        )
    unknowns = [i for i in items if i["status"] == "unknown"]
    if unknowns:
        st.warning(f"⚪ Без подтверждённого срока: {len(unknowns)} — проверьте по упаковке.")

with right:
    st.subheader("🔁 Возможные дубликаты")
    dups = match.find_duplicates(hid)
    if not dups:
        st.caption("Дубликаты не найдены.")
    for g in dups:
        names = ", ".join(x["name"] for x in g["items"])
        tag = "точный набор МНН" if g["exact"] else "частичное совпадение"
        st.markdown(f"• **{', '.join(g['inns'])}** ({tag}): {names}")
    st.caption("Совпадение по действующему веществу — информация о запасах, не рекомендация по замене.")
