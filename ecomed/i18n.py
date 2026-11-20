"""Каталоги переводов интерфейса EcoMed AI (ru / kk / en).

Модуль намеренно НЕ импортирует streamlit: его должны уметь использовать
и слой сервисов (report_service), и слой UI. Привязка к сессии Streamlit
живёт в ui_common.py.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

DEFAULT_LANG = "ru"
LANGS: tuple[str, ...] = ("ru", "kk", "en")
LANG_NAMES = {"ru": "Русский", "kk": "Қазақша", "en": "English"}

LOCALES_DIR = Path(__file__).resolve().parent / "locales"


def normalize_lang(lang: str | None) -> str:
    """Приводит код языка к поддерживаемому; неизвестное значение → русский."""
    if not lang:
        return DEFAULT_LANG
    code = str(lang).strip().lower()[:2]
    return code if code in LANGS else DEFAULT_LANG


@lru_cache(maxsize=8)
def _load_cached(lang: str) -> dict[str, str]:
    path = LOCALES_DIR / f"{lang}.json"
    # encoding указан явно: без него Windows берёт кодировку локали (cp1251)
    # и падает на казахских ә/ң/ғ, тогда как на Linux всё работает.
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    # Служебные ключи-комментарии (_comment.*) в каталог не попадают.
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def load_catalog(lang: str) -> dict[str, str]:
    """Каталог строк для языка. ECOMED_I18N_NOCACHE=1 отключает кэш при разработке."""
    lang = normalize_lang(lang)
    if os.getenv("ECOMED_I18N_NOCACHE") == "1":
        _load_cached.cache_clear()
    return _load_cached(lang)


def all_keys(lang: str) -> set[str]:
    """Множество ключей каталога — используется тестами паритета."""
    return set(load_catalog(lang))


def translate(key: str, lang: str = DEFAULT_LANG, **kwargs) -> str:
    """Строка по ключу.

    Цепочка фолбэков: выбранный язык → русский → сам ключ. Возврат ключа
    вместо KeyError означает, что демо не падает, а пропущенный перевод
    сразу виден в интерфейсе как `inventory.filter.status`.
    """
    lang = normalize_lang(lang)
    value = load_catalog(lang).get(key)
    if value is None and lang != DEFAULT_LANG:
        value = load_catalog(DEFAULT_LANG).get(key)
    if value is None:
        return key
    if not kwargs:
        # .format не вызываем без аргументов: литеральные { } в переводе не должны падать
        return value
    try:
        return value.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        return value
