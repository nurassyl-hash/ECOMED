"""Замок против регресса: в слое UI не должно остаться русских литералов.

Разбор через ast, а не regex: regex зацепил бы комментарии и докстринги, которых
в этих файлах несколько десятков строк и которые переводу не подлежат.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

UI_ROOT = Path(__file__).resolve().parent.parent
FILES = [UI_ROOT / "app.py", UI_ROOT / "ui_common.py", *sorted((UI_ROOT / "pages").glob("*.py"))]

CYRILLIC = re.compile("[А-Яа-яЁёӘәҒғҚқҢңӨөҰұҮүҺһІі]")

# Комментарии внутри CSS/HTML-блоков пользователю не видны — это комментарии
# разработчика, и в этом проекте они по-русски, как и весь остальной код.
MARKUP_COMMENT = re.compile(r"/\*.*?\*/|<!--.*?-->", re.DOTALL)

# Осознанные исключения: данные, а не интерфейс.
ALLOWED = {
    # Единица измерения по умолчанию уходит в БД. Перевод сделал бы базу разноязычной
    # и в списке аптечки перемешались бы «таблетка» / «tablet» / «таблетка (kk)».
    "таблетка",
}


def _ui_string_literals(path: Path) -> list[tuple[int, str]]:
    """Строковые константы файла без докстрингов модуля, функций и классов."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                if isinstance(body[0].value.value, str):
                    docstrings.add(id(body[0].value))

    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) not in docstrings:
                found.append((node.lineno, node.value))
    return found


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_no_cyrillic_literals(path: Path):
    bad = [
        (lineno, value)
        for lineno, value in _ui_string_literals(path)
        if CYRILLIC.search(MARKUP_COMMENT.sub("", value)) and value.strip() not in ALLOWED
    ]
    assert not bad, "Русский текст мимо каталога переводов:\n" + "\n".join(
        f"  {path.name}:{lineno}: {value!r}" for lineno, value in bad
    )


def test_detector_actually_detects():
    """Страховка от того, что детектор молча перестал что-либо находить."""
    assert CYRILLIC.search("Просрочено")
    assert CYRILLIC.search("Мерзімі өткен")
    assert not CYRILLIC.search("Expired")
    assert not CYRILLIC.search(MARKUP_COMMENT.sub("", "a { color:red } /* Кнопки */"))
    assert CYRILLIC.search(MARKUP_COMMENT.sub("", "<div>Кнопки</div>"))
