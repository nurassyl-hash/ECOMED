"""Статусы срока и effective_expiry (ТЗ 13.1, TC-08, TC-09)."""
from datetime import date

from ecomed.domain import effective_expiry, expiry_status, parse_expiry
from ecomed.models.schemas import ExpiryStatus

TODAY = date(2026, 7, 19)


def test_parse_month_precision():
    assert parse_expiry("2026-09") == date(2026, 9, 30)
    assert parse_expiry("2026-09-05") == date(2026, 9, 5)
    assert parse_expiry("") is None
    assert parse_expiry(None) is None
    assert parse_expiry("2026-13") is None


def test_effective_expiry_uses_earlier_after_open():
    # TC-09: срок после вскрытия раньше упаковочного → берём рассчитанную дату
    eff = effective_expiry(date(2026, 12, 31), date(2026, 7, 1), 14)
    assert eff == date(2026, 7, 15)


def test_effective_expiry_missing():
    assert effective_expiry(None, None, None) is None
    assert effective_expiry(date(2027, 1, 1), None, None) == date(2027, 1, 1)


def test_status_thresholds():
    assert expiry_status(date(2026, 7, 18), TODAY) == ExpiryStatus.EXPIRED  # TC-08
    assert expiry_status(date(2026, 8, 1), TODAY) == ExpiryStatus.CRITICAL   # 13 дней
    assert expiry_status(date(2026, 9, 30), TODAY) == ExpiryStatus.SOON      # ~73 дня
    assert expiry_status(date(2027, 1, 1), TODAY) == ExpiryStatus.OK
    assert expiry_status(None, TODAY) == ExpiryStatus.UNKNOWN


def test_status_boundaries():
    assert expiry_status(date(2026, 8, 18), TODAY) == ExpiryStatus.CRITICAL  # ровно 30 дней
    assert expiry_status(date(2026, 8, 19), TODAY) == ExpiryStatus.SOON      # 31 день
    assert expiry_status(date(2026, 10, 17), TODAY) == ExpiryStatus.SOON     # 90 дней
    assert expiry_status(date(2026, 10, 18), TODAY) == ExpiryStatus.OK       # 91 день
