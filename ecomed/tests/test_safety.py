"""Фильтр медицинских формулировок (ТЗ 15.2, TC-12)."""
from ecomed.policies.medical_safety import SAFE_TEMPLATE, is_safe, post_filter


def test_allows_inventory_facts():
    text = "В аптечке 18 упаковок, 4 истекают в течение 90 дней."
    assert is_safe(text)
    out, replaced = post_filter(text)
    assert not replaced and out == text


def test_blocks_take_advice():
    out, replaced = post_filter("Принимайте по одной таблетке два раза в день.")
    assert replaced and out == SAFE_TEMPLATE


def test_blocks_replacement_advice():
    out, replaced = post_filter("Можно заменить на аналог с тем же веществом.")
    assert replaced and out == SAFE_TEMPLATE


def test_blocks_dosage():
    assert not is_safe("Назначьте дозу 500 мг три раза в сутки.")
