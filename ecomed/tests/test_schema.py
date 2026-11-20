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


def test_nulls_from_vision_fall_back_to_defaults():
    """Vision-LLM присылает null для нечитаемых полей — разбор не должен падать.

    Реальный ответ модели на фото «Кетанов»: количество на упаковке не читалось,
    и вместо отсутствующего поля пришло `"value": null`. Дефолт при явном null
    не подставляется, поэтому раньше валидация роняла всю распознанную карточку.
    """
    raw = {
        "trade_name": "Кетанов",
        "active_ingredients": [{"name": "Кеторолак", "strength": "10 мг"}],
        "dosage_form": None,
        "package_quantity": {"value": None, "unit": ""},
        "expiry_date": None,
        "batch_number": None,
        "storage_text": None,
        "field_confidence": {"trade_name": 0.9},
        "needs_user_review": True,
    }
    pkg = RecognizedPackage.model_validate(raw)
    assert pkg.trade_name == "Кетанов"
    assert pkg.package_quantity.value == 0
    assert pkg.package_quantity.unit == ""
    assert pkg.dosage_form is None
    assert pkg.inn_names() == ["Кеторолак"]


def test_null_collections_fall_back_to_defaults():
    pkg = RecognizedPackage.model_validate(
        {"trade_name": "Ибупрофен", "active_ingredients": None, "field_confidence": None}
    )
    assert pkg.active_ingredients == []
    assert pkg.field_confidence == {}
