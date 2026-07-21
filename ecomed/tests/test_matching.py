"""Нормализация МНН и уровни совпадения A–D (ТЗ 7.2, TC-04..TC-07)."""
from ecomed.domain import match_level, normalize_inn, normalize_inn_set
from ecomed.models.schemas import MatchLevel


def test_normalize_transliteration():
    assert normalize_inn("Парацетамол") == "paracetamol"
    assert normalize_inn("paracetamol") == "paracetamol"
    assert normalize_inn("Ибупрофен") == "ibuprofen"
    assert normalize_inn("  ПАРА-ЦЕТАМОЛ ") == "para cetamol"


def test_level_a_same_package():
    assert match_level(
        same_package_id=True, query_inns=frozenset(), item_inns=frozenset(),
        same_strength=False, same_form=False,
    ) == MatchLevel.A


def test_level_b_same_inn_strength_form():
    q = normalize_inn_set(["Парацетамол"])
    i = normalize_inn_set(["paracetamol"])
    assert match_level(same_package_id=False, query_inns=q, item_inns=i,
                       same_strength=True, same_form=True) == MatchLevel.B


def test_level_c_same_inn_diff_strength():
    q = normalize_inn_set(["Парацетамол"])
    i = normalize_inn_set(["paracetamol"])
    # TC-06: то же МНН, другая дозировка → C
    assert match_level(same_package_id=False, query_inns=q, item_inns=i,
                       same_strength=False, same_form=True) == MatchLevel.C


def test_level_c_combo_partial_overlap():
    # TC-07: комбинированный с одним общим ингредиентом → C (не точный аналог)
    q = normalize_inn_set(["Парацетамол"])
    i = normalize_inn_set(["парацетамол", "фенилэфрин", "фенирамин"])
    assert match_level(same_package_id=False, query_inns=q, item_inns=i,
                       same_strength=True, same_form=True) == MatchLevel.C


def test_level_d_fuzzy_only():
    assert match_level(same_package_id=False, query_inns=frozenset(), item_inns=frozenset(),
                       same_strength=False, same_form=False, name_similarity=0.9) == MatchLevel.D


def test_level_none():
    assert match_level(same_package_id=False, query_inns=frozenset(["a"]), item_inns=frozenset(["b"]),
                       same_strength=False, same_form=False, name_similarity=0.1) == MatchLevel.NONE
