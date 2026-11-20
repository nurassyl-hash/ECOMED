"""Интеграция: добавить → проверить покупку → отчёт (ТЗ 18)."""
import pytest

from ecomed.i18n import LANGS
from ecomed.models.schemas import MatchLevel
from ecomed.policies.medical_safety import is_safe
from ecomed.services import inventory_service as inv
from ecomed.services import matching_service as match
from ecomed.services import report_service as rep


def test_add_check_report_flow(household):
    # дома есть Парацетамол 500 мг таблетки
    inv.add_item(household, custom_name="Парацетамол 500 мг", inns=["Парацетамол"],
                 dosage_form="таблетки", strength="500 мг", quantity=10, expiry_raw="2027-01-01")

    # проверяем покупку Панадола (то же МНН/дозировка/форма) → уровень B
    matches = match.check_purchase(household, name="Панадол", inns=["Парацетамол"],
                                   strength="500 мг", dosage_form="таблетки")
    assert matches and matches[0].level == MatchLevel.B

    # отмечаем «не купил» с ценой → подтверждённая экономия
    match.record_avoided_purchase(household, matches[0].inventory_item_id, price=850)

    m = rep.compute_metrics(household)
    assert m.total_items == 1
    assert m.avoided_purchases == 1
    assert m.confirmed_savings == 850
    for lang in LANGS:
        summary, used_llm = rep.generate_summary(m, lang=lang)
        assert used_llm is False          # без ключа — детерминированный шаблон
        assert str(m.total_items) in summary
        assert str(m.avoided_purchases) in summary


def test_duplicates_detected(household):
    inv.add_item(household, custom_name="Нурофен 200 мг", inns=["Ибупрофен"],
                 dosage_form="таблетки", strength="200 мг", quantity=20)
    inv.add_item(household, custom_name="Ибупрофен 200 мг", inns=["Ибупрофен"],
                 dosage_form="таблетки", strength="200 мг", quantity=8)
    groups = match.find_duplicates(household)
    assert len(groups) == 1
    assert groups[0]["exact"] is True


@pytest.mark.parametrize("lang", LANGS)
def test_template_summary_is_medically_safe(household, lang):
    """Переведённый шаблон не должен содержать медицинских рекомендаций.

    Для kk/en проверка слабая (пост-фильтр собран из русских регулярок), но она
    фиксирует намерение и ловит регресс в русском тексте.
    """
    inv.add_item(household, custom_name="Парацетамол 500 мг", inns=["Парацетамол"],
                 dosage_form="таблетки", strength="500 мг", quantity=10, expiry_raw="2027-01-01")
    m = rep.compute_metrics(household)
    text = rep._template_summary(m, lang)
    assert is_safe(text), f"{lang}: шаблон отчёта содержит запрещённую формулировку: {text}"
    assert str(m.total_items) in text
