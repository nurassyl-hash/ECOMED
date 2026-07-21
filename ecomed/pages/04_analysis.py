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

from ecomed.models.schemas import STATUS_LABEL, ExpiryStatus
from ecomed.services import matching_service as match
from ecomed.services import report_service as rep
from ecomed.ui_common import household_id, page_setup

page_setup("Анализ", "📊")
hid = household_id()

st.title("📊 Анализ и отчёт")
st.caption("Все показатели рассчитаны кодом. Текстовое пояснение только пересказывает эти числа.")

m = rep.compute_metrics(hid, period_label="Текущий срез")

# --- Деньги / эффект ---
c1, c2, c3, c4 = st.columns(4)
c1.metric("Всего упаковок", m.total_items)
c2.metric("Уникальных МНН", m.unique_inns)
c3.metric("Подтверждённая экономия", f"{m.confirmed_savings:.0f} ₸")
c4.metric("Переданных упаковок", m.disposed_packages)
st.caption(f"Потенциальная стоимость запасов (оценка по демо-ценам): {m.potential_stock_value:.0f} ₸")

# --- Статусы срока ---
st.subheader("Сроки годности")
chart_data = {STATUS_LABEL[ExpiryStatus(k)]: v for k, v in m.by_status.items()}
st.bar_chart(chart_data)

# --- Дубликаты ---
st.subheader("Возможные дубликаты")
dups = match.find_duplicates(hid)
if not dups:
    st.caption("Не найдено.")
for g in dups:
    kind = "точное совпадение набора МНН, дозировки и формы" if g["exact"] else "частичное совпадение (не точный аналог)"
    st.markdown(f"• **{', '.join(g['inns'])}** — {kind}: " + ", ".join(x["name"] for x in g["items"]))
st.caption("Совпадение по действующему веществу — информация о запасах, не рекомендация по замене.")

# --- Качество данных ---
st.subheader("Пробелы в данных")
g = m.data_gaps
st.markdown(
    f"- Без срока годности: **{g.get('missing_expiry',0)}**\n"
    f"- Без МНН: **{g.get('missing_inn',0)}**\n"
    f"- Без места хранения: **{g.get('missing_storage',0)}**\n"
    f"- Без изменений остатка за период: **{m.stale_items}**"
)

# --- Текстовое пояснение (LLM через пост-фильтр) ---
st.subheader("Пояснение к отчёту")
summary, used_llm = rep.generate_summary(m)
st.write(summary)
st.caption("Сгенерировано моделью и проверено фильтром безопасности." if used_llm else "Детерминированный текст (LLM отключён или отфильтрован).")

# --- Три следующих шага (без медицинских советов) ---
steps = []
if m.by_status.get("expired", 0):
    steps.append(f"Передать на утилизацию просроченные упаковки: {m.by_status['expired']}.")
if g.get("missing_expiry", 0):
    steps.append(f"Уточнить срок у {g['missing_expiry']} позиций без даты.")
if m.duplicate_groups:
    steps.append(f"Проверить {m.duplicate_groups} групп(ы) возможных дубликатов перед следующей покупкой.")
steps = steps[:3]
if steps:
    st.subheader("Следующие шаги")
    for i, s in enumerate(steps, 1):
        st.markdown(f"{i}. {s}")

# --- Экспорт ---
report_md = f"""# EcoMed AI — отчёт по аптечке

- Всего упаковок: {m.total_items}
- Уникальных МНН: {m.unique_inns}
- Просрочено: {m.by_status.get('expired',0)}, до 30 дней: {m.by_status.get('critical',0)}, 31–90 дней: {m.by_status.get('soon',0)}, более 90 дней: {m.by_status.get('ok',0)}, неизвестно: {m.by_status.get('unknown',0)}
- Групп дубликатов: {m.duplicate_groups}
- Подтверждённая экономия: {m.confirmed_savings:.0f} ₸
- Предотвращённых покупок: {m.avoided_purchases}
- Переданных упаковок: {m.disposed_packages}

## Пояснение
{summary}

## Следующие шаги
""" + "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))

st.download_button("⬇️ Скачать отчёт (Markdown)", report_md, file_name="ecomed_report.md", mime="text/markdown")
