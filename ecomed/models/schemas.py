"""Pydantic-схемы EcoMed AI.

Схема распознавания повторяет JSON-контракт из ТЗ раздел 7.1.
Схемы совпадений — уровни A–D из ТЗ раздел 7.2.
"""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------
# Распознавание упаковки (ТЗ 7.1)
# --------------------------------------------------------------------------
class ActiveIngredient(BaseModel):
    name: str
    strength: Optional[str] = None


class PackageQuantity(BaseModel):
    value: float = 0
    unit: str = "tablet"


class RecognizedPackage(BaseModel):
    """Строгий JSON-выход vision-LLM (или ручной формы)."""

    trade_name: Optional[str] = None
    active_ingredients: list[ActiveIngredient] = Field(default_factory=list)
    dosage_form: Optional[str] = None
    package_quantity: PackageQuantity = Field(default_factory=PackageQuantity)
    expiry_date: Optional[str] = None  # "YYYY-MM-DD" | "YYYY-MM" | None
    batch_number: Optional[str] = None
    storage_text: Optional[str] = None
    field_confidence: dict[str, float] = Field(default_factory=dict)
    needs_user_review: bool = True

    def inn_names(self) -> list[str]:
        return [i.name for i in self.active_ingredients if i.name]


# --------------------------------------------------------------------------
# Статусы срока годности (ТЗ 13.1)
# --------------------------------------------------------------------------
class ExpiryStatus(str, Enum):
    EXPIRED = "expired"
    CRITICAL = "critical"   # 0–30 дней
    SOON = "soon"           # 31–90 дней
    OK = "ok"               # > 90 дней
    UNKNOWN = "unknown"     # даты нет / не подтверждена


STATUS_COLOR = {
    ExpiryStatus.EXPIRED: "#d32f2f",
    ExpiryStatus.CRITICAL: "#f57c00",
    ExpiryStatus.SOON: "#fbc02d",
    ExpiryStatus.OK: "#388e3c",
    ExpiryStatus.UNKNOWN: "#9e9e9e",
}

STATUS_LABEL = {
    ExpiryStatus.EXPIRED: "Просрочено",
    ExpiryStatus.CRITICAL: "До 30 дней",
    ExpiryStatus.SOON: "31–90 дней",
    ExpiryStatus.OK: "Более 90 дней",
    ExpiryStatus.UNKNOWN: "Срок неизвестен",
}


# --------------------------------------------------------------------------
# Совпадения при проверке покупки (ТЗ 7.2)
# --------------------------------------------------------------------------
class MatchLevel(str, Enum):
    A = "A"  # точное — та же упаковка
    B = "B"  # МНН + дозировка + форма
    C = "C"  # только МНН
    D = "D"  # текстовый кандидат

    NONE = "none"


# Тексты пользователю (ТЗ 7.2 + Приложение A)
MATCH_TEXT = {
    MatchLevel.A: "Такая упаковка уже есть дома.",
    MatchLevel.B: (
        "В домашней аптечке найден препарат с тем же действующим веществом, "
        "дозировкой и формой. Это не означает, что препараты можно "
        "самостоятельно заменять."
    ),
    MatchLevel.C: (
        "Совпадает действующее вещество, но отличается дозировка, форма или "
        "состав. Проверьте упаковку и уточните у врача или фармацевта."
    ),
    MatchLevel.D: "Возможное совпадение — проверьте вручную.",
    MatchLevel.NONE: "Дома такого препарата не найдено.",
}


class PurchaseMatch(BaseModel):
    level: MatchLevel
    text: str
    inventory_item_id: Optional[int] = None
    trade_name: Optional[str] = None
    quantity_remaining: float = 0
    unit: str = ""
    expiry_date: Optional[str] = None
    storage_place: Optional[str] = None
    score: float = 0.0
    reason: str = ""


# --------------------------------------------------------------------------
# Отчёт (ТЗ 7.3, 14.2) — детерминированные агрегаты
# --------------------------------------------------------------------------
class ReportMetrics(BaseModel):
    total_items: int = 0
    unique_inns: int = 0
    by_status: dict[str, int] = Field(default_factory=dict)
    duplicate_groups: int = 0
    stale_items: int = 0            # без изменения остатка за период
    data_gaps: dict[str, int] = Field(default_factory=dict)  # missing expiry/inn/storage
    confirmed_savings: float = 0.0
    potential_stock_value: float = 0.0
    avoided_purchases: int = 0
    disposed_packages: int = 0
    purchase_checks: int = 0
    period_label: str = ""
