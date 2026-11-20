"""Анализ аптечки и ежемесячный отчёт (ТЗ 7.3, 14.2)."""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_r = _Path(__file__).resolve()
while _r.parent != _r and not (_r / "ecomed" / "__init__.py").exists():
    _r = _r.parent
if str(_r) not in _sys.path:
    _sys.path.insert(0, str(_r))

import streamlit as st

from ecomed.services import matching_service as match
from ecomed.services import report_service as rep
from ecomed.ui_common import get_lang, household_id, page_setup, status_label, t

page_setup("nav.analysis", "📊")
hid = household_id()

st.title(t("analysis.title"))
CUR = t("common.currency")
st.caption(t("analysis.subtitle"))

m = rep.compute_metrics(hid, period_label=t("analysis.period"))

# --- Деньги / эффект ---
c1, c2, c3, c4 = st.columns(4)
c1.metric(t("analysis.metric.total"), m.total_items)
c2.metric(t("analysis.metric.inns"), m.unique_inns)
c3.metric(t("analysis.metric.savings"), f"{m.confirmed_savings:.0f} {CUR}")
c4.metric(t("analysis.metric.disposed"), m.disposed_packages)
st.caption(t("analysis.stock_value", value=f"{m.potential_stock_value:.0f}", cur=CUR))

# --- Статусы срока ---
st.subheader(t("analysis.expiry.title"))
chart_data = {status_label(k): v for k, v in m.by_status.items()}
st.bar_chart(chart_data)

# --- Дубликаты ---
st.subheader(t("analysis.dups.title"))
dups = match.find_duplicates(hid)
if not dups:
    st.caption(t("analysis.dups.empty"))
for g in dups:
    kind = t("analysis.dups.exact") if g["exact"] else t("analysis.dups.partial")
    st.markdown(f"• **{', '.join(g['inns'])}** — {kind}: " + ", ".join(x["name"] for x in g["items"]))
st.caption(t("home.dups.note"))

# --- Качество данных ---
st.subheader(t("analysis.gaps.title"))
g = m.data_gaps
st.markdown(
    f"- {t('analysis.gaps.expiry')}: **{g.get('missing_expiry',0)}**\n"
    f"- {t('analysis.gaps.inn')}: **{g.get('missing_inn',0)}**\n"
    f"- {t('analysis.gaps.storage')}: **{g.get('missing_storage',0)}**\n"
    f"- {t('analysis.gaps.stale')}: **{m.stale_items}**"
)

# --- Текстовое пояснение (LLM через пост-фильтр) ---
st.subheader(t("analysis.summary.title"))
summary, used_llm = rep.generate_summary(m, lang=get_lang())
st.write(summary)
st.caption(t("analysis.summary.llm") if used_llm else t("analysis.summary.template"))
# Промпт к модели остаётся русским (пост-фильтр безопасности собран из русских
# регулярок), поэтому на другом языке интерфейса это стоит проговорить честно.
if used_llm and get_lang() != "ru":
    st.caption(t("analysis.summary.lang_note"))

# --- Три следующих шага (без медицинских советов) ---
steps = []
if m.by_status.get("expired", 0):
    steps.append(t("analysis.steps.dispose", count=m.by_status["expired"]))
if g.get("missing_expiry", 0):
    steps.append(t("analysis.steps.expiry", count=g["missing_expiry"]))
if m.duplicate_groups:
    steps.append(t("analysis.steps.dups", count=m.duplicate_groups))
steps = steps[:3]
if steps:
    st.subheader(t("analysis.steps.title"))
    for i, s in enumerate(steps, 1):
        st.markdown(f"{i}. {s}")

# --- Экспорт ---
report_lines = [
    "# " + t("analysis.md.title"),
    "",
    f'- {t("analysis.metric.total")}: {m.total_items}',
    f'- {t("analysis.metric.inns")}: {m.unique_inns}',
    "- " + t(
        "analysis.md.expiry",
        expired=m.by_status.get("expired", 0),
        critical=m.by_status.get("critical", 0),
        soon=m.by_status.get("soon", 0),
        ok=m.by_status.get("ok", 0),
        unknown=m.by_status.get("unknown", 0),
    ),
    f'- {t("analysis.md.dups")}: {m.duplicate_groups}',
    f'- {t("analysis.metric.savings")}: {m.confirmed_savings:.0f} {CUR}',
    f'- {t("analysis.md.avoided")}: {m.avoided_purchases}',
    f'- {t("analysis.metric.disposed")}: {m.disposed_packages}',
    "",
    "## " + t("analysis.md.summary"),
    summary,
    "",
    "## " + t("analysis.md.steps"),
]
report_lines += [f"{i}. {step}" for i, step in enumerate(steps, 1)]
# Имя файла остаётся ASCII: не-ASCII в Content-Disposition браузеры обрабатывают по-разному.
report_md = chr(10).join(report_lines)

st.download_button(t("analysis.download"), report_md, file_name="ecomed_report.md", mime="text/markdown")
