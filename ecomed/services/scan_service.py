"""Сканирование и подтверждение карточки (ТЗ 12: create_scan / confirm_inventory_item)."""
from __future__ import annotations

from datetime import date
from typing import Optional

from ecomed.db.database import get_session
from ecomed.db.models import ScanSession
from ecomed.integrations import catalog_provider
from ecomed.integrations.ocr_provider import ProviderUnavailable, recognize
from ecomed.models.schemas import RecognizedPackage
from ecomed.services.inventory_service import add_item


def create_scan(household_id: int, image_bytes: bytes, mime: str = "image/jpeg") -> dict:
    """Распознаёт упаковку и сохраняет аудит-сессию (ТЗ FR-18).

    Возвращает {scan_id, package(dict), candidates, provider_ok, error}.
    При сбое провайдера возвращает пустую карточку для ручного ввода.
    """
    error = None
    model_version = None
    try:
        pkg, model_version = recognize(image_bytes, mime)
        provider_ok = True
    except ProviderUnavailable as e:
        pkg = RecognizedPackage(needs_user_review=True)
        provider_ok = False
        error = str(e)

    candidates = []
    if pkg.trade_name:
        candidates = catalog_provider.search(pkg.trade_name)

    with get_session() as s:
        scan = ScanSession(
            household_id=household_id,
            raw_fields_json=pkg.model_dump(),
            confidence_json=pkg.field_confidence,
            model_version=model_version,
        )
        s.add(scan)
        s.flush()
        scan_id = scan.id

    return {
        "scan_id": scan_id,
        "package": pkg.model_dump(),
        "candidates": candidates,
        "provider_ok": provider_ok,
        "error": error,
    }


def confirm_inventory_item(
    household_id: int,
    scan_id: Optional[int],
    *,
    custom_name: str,
    inns: list[str],
    dosage_form: Optional[str] = None,
    strength: Optional[str] = None,
    quantity: float = 0,
    unit: str = "tablet",
    expiry_raw: Optional[str] = None,
    storage_place: Optional[str] = None,
    price: Optional[float] = None,
) -> int:
    """Сохраняет подтверждённую карточку и фиксирует исправления в аудите."""
    item_id = add_item(
        household_id,
        custom_name=custom_name, inns=inns, dosage_form=dosage_form, strength=strength,
        quantity=quantity, unit=unit, expiry_raw=expiry_raw,
        storage_place=storage_place, source="ai" if scan_id else "manual", price=price,
    )
    if scan_id is not None:
        with get_session() as s:
            scan = s.get(ScanSession, scan_id)
            if scan is not None and scan.household_id == household_id:
                scan.confirmed_fields_json = {
                    "custom_name": custom_name, "inns": inns, "dosage_form": dosage_form,
                    "strength": strength, "quantity": quantity, "unit": unit,
                    "expiry_raw": expiry_raw, "storage_place": storage_place,
                    "inventory_item_id": item_id,
                }
    return item_id
