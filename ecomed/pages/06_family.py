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

from ecomed.ui_common import household_id, page_setup

page_setup("Семья", "👪")
household_id()

st.title("👪 Семья")
st.caption("Доступ к строкам ограничен household_id и ролью. Участник видит только свою семью.")

st.subheader("Демо-семья")
st.markdown("- **Демо-пользователь** — роль: владелец (owner)")

st.subheader("Пригласить участника")
st.text_input("Ссылка-приглашение (демо)", value="https://ecomed.demo/join/DEMO-2026", disabled=True)
st.caption("Ссылки приглашения одноразовые или имеют срок действия. В демо приглашение отключено.")

st.subheader("Роли и права")
st.table([
    {"Роль": "Владелец", "Права": "Создать семью, приглашать, CRUD, отчёты", "Ограничения": "Не видит данные другой семьи"},
    {"Роль": "Редактор", "Права": "Добавлять/обновлять, отмечать покупку и утилизацию", "Ограничения": "Не управляет владельцем и настройками"},
    {"Роль": "Наблюдатель", "Права": "Просмотр, проверка перед покупкой", "Ограничения": "Не меняет остатки, не удаляет"},
    {"Роль": "Администратор данных", "Права": "Каталог, источники, пункты приёма", "Ограничения": "Нет доступа к личным запасам без основания"},
])
