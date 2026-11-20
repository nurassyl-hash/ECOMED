"""Хранение выбранного языка: session_state + ?lang= в URL.

Streamlit здесь не запускается — подменяются st.session_state и st.query_params,
поэтому проверяется именно наша логика get_lang/set_lang/_on_lang_change.
"""
from __future__ import annotations

import pytest


class FakeQueryParams(dict):
    """st.query_params ведёт себя как dict, но нам важны только get/setitem/pop."""


@pytest.fixture
def ui(monkeypatch):
    import streamlit as st

    from ecomed import ui_common

    monkeypatch.setattr(st, "session_state", {}, raising=False)
    monkeypatch.setattr(st, "query_params", FakeQueryParams(), raising=False)
    return ui_common


def test_default_is_russian_and_url_stays_clean(ui):
    import streamlit as st

    assert ui.get_lang() == "ru"
    assert "lang" not in st.query_params


def test_lang_is_read_from_url_on_fresh_session(ui):
    """Ссылки в hero делают полную перезагрузку — сессия новая, язык берётся из URL."""
    import streamlit as st

    st.query_params["lang"] = "kk"
    assert ui.get_lang() == "kk"
    assert st.session_state[ui.LANG_KEY] == "kk"


def test_garbage_lang_falls_back_quietly(ui):
    import streamlit as st

    st.query_params["lang"] = "de"
    assert ui.get_lang() == "ru"          # без ValueError в selectbox(index=...)


def test_set_lang_writes_session_and_url(ui):
    import streamlit as st

    ui.set_lang("en")
    assert st.session_state[ui.LANG_KEY] == "en"
    assert st.query_params["lang"] == "en"
    assert ui.lang_qs() == "?lang=en"


def test_switching_back_to_ru_clears_url_param(ui):
    import streamlit as st

    ui.set_lang("kk")
    assert st.query_params["lang"] == "kk"
    ui.set_lang("ru")
    assert "lang" not in st.query_params, "дефолтный язык не должен мусорить в URL"
    assert ui.lang_qs() == ""


def test_widget_callback_applies_selection(ui):
    """_on_lang_change вызывается Streamlit'ом до перезапуска скрипта."""
    import streamlit as st

    st.session_state[ui.LANG_WIDGET_KEY] = "kk"
    ui._on_lang_change()
    assert ui.get_lang() == "kk"
    assert st.query_params["lang"] == "kk"


def test_translation_helpers_follow_current_lang(ui):
    import streamlit as st

    ui.set_lang("en")
    assert ui.t("nav.inventory") == "My medicine cabinet"
    assert ui.status_label("expired") == "Expired"
    assert ui.match_text("B").startswith("Your home cabinet")

    ui.set_lang("kk")
    assert ui.t("nav.inventory") == "Менің дәрі қобдишам"
    assert ui.status_label("expired") == "Мерзімі өткен"
