"""Остатки, запрет отрицательного остатка, изоляция семьи (ТЗ FR-06, TC-10, TC-13)."""
import pytest

from ecomed.services import inventory_service as inv


def test_add_and_update(household):
    item_id = inv.add_item(household, custom_name="Парацетамол 500 мг",
                           inns=["Парацетамол"], quantity=10, unit="таблетка",
                           expiry_raw="2027-01-01")
    view = inv.get_item(item_id, household)
    assert view["quantity_remaining"] == 10
    assert view["inns"] == ["paracetamol"]

    new_qty = inv.update_quantity(item_id, household, -3, "used")
    assert new_qty == 7


def test_negative_stock_rejected(household):
    item_id = inv.add_item(household, custom_name="X", inns=["ибупрофен"], quantity=2)
    with pytest.raises(inv.NegativeStock):
        inv.update_quantity(item_id, household, -5, "used")  # TC-10
    # остаток не изменился
    assert inv.get_item(item_id, household)["quantity_remaining"] == 2


def test_household_isolation(household):
    item_id = inv.add_item(household, custom_name="X", inns=["ибупрофен"], quantity=2)
    other_household = household + 999
    assert inv.get_item(item_id, other_household) is None  # TC-13
    with pytest.raises(PermissionError):
        inv.update_quantity(item_id, other_household, -1, "used")
