"""Интеграция: добавить → проверить покупку → отчёт (ТЗ 18)."""
from ecomed.models.schemas import MatchLevel
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
    summary, _ = rep.generate_summary(m)
    assert "упаков" in summary.lower()


def test_duplicates_detected(household):
    inv.add_item(household, custom_name="Нурофен 200 мг", inns=["Ибупрофен"],
                 dosage_form="таблетки", strength="200 мг", quantity=20)
    inv.add_item(household, custom_name="Ибупрофен 200 мг", inns=["Ибупрофен"],
                 dosage_form="таблетки", strength="200 мг", quantity=8)
    groups = match.find_duplicates(household)
    assert len(groups) == 1
    assert groups[0]["exact"] is True
