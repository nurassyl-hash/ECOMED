"""Валидация JSON-схемы распознавания (ТЗ 7.1)."""
from ecomed.models.schemas import RecognizedPackage


def test_parse_full_schema():
    raw = {
        "trade_name": "Панадол",
        "active_ingredients": [{"name": "Парацетамол", "strength": "500 мг"}],
        "dosage_form": "таблетки",
        "package_quantity": {"value": 12, "unit": "tablet"},
        "expiry_date": "2027-01-31",
        "batch_number": "AB123",
        "storage_text": "хранить при 25°C",
        "field_confidence": {"trade_name": 0.94},
        "needs_user_review": True,
    }
    pkg = RecognizedPackage.model_validate(raw)
    assert pkg.trade_name == "Панадол"
    assert pkg.inn_names() == ["Парацетамол"]
    assert pkg.package_quantity.value == 12


def test_defaults_for_empty():
    pkg = RecognizedPackage()
    assert pkg.trade_name is None
    assert pkg.active_ingredients == []
    assert pkg.needs_user_review is True
