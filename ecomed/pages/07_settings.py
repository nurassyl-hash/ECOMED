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
from ecomed.ui_common import household_id, page_setup

page_setup("Настройки", "⚙️")
household_id()

st.title("⚙️ Настройки")

st.subheader("Язык и регион")
st.selectbox("Язык интерфейса", ["Русский", "Қазақша (P1)"])
st.text_input("Город", value=settings.ecomed_default_city)

st.subheader("Согласия (ТЗ раздел 16)")
st.checkbox("Согласие на обработку данных домашней аптечки", value=True)
st.checkbox("Согласие на отправку фото внешнему AI-провайдеру", value=False)
st.caption("Список аптечки может косвенно раскрывать сведения о здоровье. Собираются только запасы — без диагнозов, симптомов и рецептов.")

st.subheader("Уведомления")
st.checkbox("Баннеры о сроках при входе (90 / 30 / 7 дней)", value=True)
st.checkbox("Уведомление о возможном дубликате после добавления", value=True)

st.subheader("Данные")
st.caption("В демо данные хранятся в локальной SQLite и переживают перезапуск приложения.")
if st.button("🔄 Сбросить демо-данные и пересоздать эталонную аптечку", type="secondary"):
    from ecomed.db.database import _engine
    from ecomed.db.models import Base
    from ecomed.db.seed import seed_demo
    Base.metadata.drop_all(_engine)
    st.cache_resource.clear()
    seed_demo()
    st.success("Демо-данные пересозданы. Обновите страницу «Главная».")
