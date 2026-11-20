"""Целостность каталогов переводов (ru / kk / en)."""
from __future__ import annotations

import re

import pytest

from ecomed.i18n import DEFAULT_LANG, LANGS, all_keys, load_catalog, normalize_lang, translate
from ecomed.models.schemas import STATUS_LABEL_KEY, ExpiryStatus

OTHER_LANGS = [lang for lang in LANGS if lang != DEFAULT_LANG]


def test_default_lang_is_ru():
    assert DEFAULT_LANG == "ru"
    assert set(LANGS) == {"ru", "kk", "en"}


@pytest.mark.parametrize("lang", OTHER_LANGS)
def test_catalog_keys_parity(lang):
    """В каждом языке ровно тот же набор ключей, что и в русском эталоне."""
    base = all_keys(DEFAULT_LANG)
    other = all_keys(lang)
    missing = sorted(base - other)
    extra = sorted(other - base)
    assert not missing, f"{lang}: нет ключей {missing}"
    assert not extra, f"{lang}: лишние ключи {extra}"


@pytest.mark.parametrize("lang", OTHER_LANGS)
def test_placeholders_parity(lang):
    """Плейсхолдеры совпадают с эталоном.

    Лишний {n} в переводе роняет .format уже у пользователя, причём только
    на одной странице и только на одном языке.
    """
    base = load_catalog(DEFAULT_LANG)
    other = load_catalog(lang)
    bad = []
    for key, ru_value in base.items():
        ru_ph = set(re.findall(r"\{(\w+)\}", ru_value))
        other_ph = set(re.findall(r"\{(\w+)\}", other[key]))
        if ru_ph != other_ph:
            bad.append(f"{key}: ru={sorted(ru_ph)} {lang}={sorted(other_ph)}")
    assert not bad, "Расхождение плейсхолдеров:\n" + "\n".join(bad)


@pytest.mark.parametrize("lang", LANGS)
def test_no_empty_values(lang):
    empty = sorted(k for k, v in load_catalog(lang).items() if not v.strip())
    assert not empty, f"{lang}: пустые значения {empty}"


@pytest.mark.parametrize("lang", LANGS)
def test_status_labels_unique_per_lang(lang):
    """Подписи статусов становятся ключами словаря в st.bar_chart.

    Два одинаковых перевода молча схлопнут столбец на графике «Сроки годности».
    """
    labels = [translate(STATUS_LABEL_KEY[s], lang) for s in ExpiryStatus]
    assert len(set(labels)) == len(list(ExpiryStatus)), f"{lang}: неуникальные подписи {labels}"


def test_unknown_lang_falls_back_to_ru():
    assert normalize_lang("de") == "ru"
    assert normalize_lang(None) == "ru"
    assert normalize_lang("") == "ru"
    assert normalize_lang("KK") == "kk"
    assert normalize_lang("en-US") == "en"


def test_missing_key_returns_key_itself():
    assert translate("no.such.key.anywhere", "ru") == "no.such.key.anywhere"


def test_format_survives_bad_placeholder():
    """Кривой плейсхолдер не должен ронять страницу."""
    assert translate("common.all", "ru", unexpected=1) == translate("common.all", "ru")
