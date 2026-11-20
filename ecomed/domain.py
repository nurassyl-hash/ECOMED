"""Детерминированное ядро бизнес-правил (ТЗ разделы 13, 7.2).

Здесь НЕТ обращений к БД и LLM — только чистые функции.
Всё, что связано с деньгами, сроками и статусами, считается кодом,
чтобы результат был воспроизводим и покрыт тестами.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

from ecomed.models.schemas import ExpiryStatus, MatchLevel


# --------------------------------------------------------------------------
# Разбор даты срока годности (ТЗ 13.1: точность «месяц/год»)
# --------------------------------------------------------------------------
def parse_expiry(raw: Optional[str]) -> Optional[date]:
    """Принимает 'YYYY-MM-DD' или 'YYYY-MM'.

    Для 'YYYY-MM' возвращает последний день месяца (хранение), исходная
    точность показывается пользователю отдельно на UI.
    """
    if not raw:
        return None
    raw = raw.strip()
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        try:
            return date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    m = re.fullmatch(r"(\d{4})-(\d{2})", raw)
    if m:
        year, month = int(m[1]), int(m[2])
        if not 1 <= month <= 12:
            return None
        # последний день месяца
        if month == 12:
            return date(year, 12, 31)
        return date(year, month + 1, 1) - timedelta(days=1)
    return None


def effective_expiry(
    expiry_date: Optional[date],
    opened_at: Optional[date],
    after_open_days: Optional[int],
) -> Optional[date]:
    """min(дата на упаковке, opened_at + after_open_days) при наличии обеих.

    ТЗ 13.1 / TC-09: используется более ранняя из двух дат.
    """
    after_open: Optional[date] = None
    if opened_at is not None and after_open_days is not None:
        after_open = opened_at + timedelta(days=int(after_open_days))

    candidates = [d for d in (expiry_date, after_open) if d is not None]
    if not candidates:
        return None
    return min(candidates)


def expiry_status(eff_expiry: Optional[date], today: Optional[date] = None) -> ExpiryStatus:
    """Статус по эффективной дате (ТЗ 13.1)."""
    if eff_expiry is None:
        return ExpiryStatus.UNKNOWN
    today = today or date.today()
    delta = (eff_expiry - today).days
    if delta < 0:
        return ExpiryStatus.EXPIRED
    if delta <= 30:
        return ExpiryStatus.CRITICAL
    if delta <= 90:
        return ExpiryStatus.SOON
    return ExpiryStatus.OK


# --------------------------------------------------------------------------
# Нормализация МНН (ТЗ 7.2)
# --------------------------------------------------------------------------
# Полная транслитерация кириллицы (рус/каз) в латиницу, чтобы «Парацетамол» и
# «Paracetamol» сводились к одной канонической форме. Порядок важен: сначала
# многобуквенные сочетания.
_TRANSLIT: list[tuple[str, str]] = [
    ("щ", "sch"), ("ж", "zh"), ("ч", "ch"), ("ш", "sh"), ("ю", "yu"), ("я", "ya"),
    ("ё", "e"), ("й", "i"), ("ъ", ""), ("ь", ""), ("э", "e"),
    ("ғ", "g"), ("қ", "k"), ("ң", "n"), ("ө", "o"), ("ұ", "u"), ("ү", "u"),
    ("һ", "h"), ("і", "i"), ("ә", "a"),
    ("а", "a"), ("б", "b"), ("в", "v"), ("г", "g"), ("д", "d"), ("е", "e"),
    ("з", "z"), ("и", "i"), ("к", "k"), ("л", "l"), ("м", "m"), ("н", "n"),
    ("о", "o"), ("п", "p"), ("р", "r"), ("с", "s"), ("т", "t"), ("у", "u"),
    ("ф", "f"), ("х", "h"), ("ц", "c"), ("ы", "y"),
]


def _transliterate(s: str) -> str:
    for cyr, lat in _TRANSLIT:
        s = s.replace(cyr, lat)
    return s


def normalize_inn(name: str) -> str:
    """Нижний регистр, свёрнутые пробелы/дефисы, кириллица→латиница-транслит."""
    if not name:
        return ""
    s = unicodedata.normalize("NFKC", name).lower().strip()
    s = s.replace("-", " ")
    s = _transliterate(s)
    s = re.sub(r"[^a-z0-9 ]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def normalize_inn_set(names: list[str]) -> frozenset[str]:
    """Комбинированный препарат = набор нормализованных МНН (ТЗ 13.2)."""
    return frozenset(n for n in (normalize_inn(x) for x in names) if n)


# --------------------------------------------------------------------------
# Уровень совпадения A–D (ТЗ 7.2)
# --------------------------------------------------------------------------
def match_level(
    *,
    same_package_id: bool,
    query_inns: frozenset[str],
    item_inns: frozenset[str],
    same_strength: bool,
    same_form: bool,
    name_similarity: float = 0.0,
    fuzzy_threshold: float = 0.82,
) -> MatchLevel:
    """Определяет уровень совпадения кандидата.

    A — та же упаковка/идентификатор.
    B — совпадают набор МНН + дозировка + форма.
    C — пересекается действующее вещество, но дозировка/форма/состав отличаются.
    D — только похожее название (fuzzy), без подтверждения по МНН.
    """
    if same_package_id:
        return MatchLevel.A

    if query_inns and item_inns:
        if query_inns == item_inns and same_strength and same_form:
            return MatchLevel.B
        if query_inns & item_inns:
            return MatchLevel.C

    if name_similarity >= fuzzy_threshold:
        return MatchLevel.D

    return MatchLevel.NONE


# --------------------------------------------------------------------------
# Схема приёма лекарств: плановые слоты (чистые функции)
# --------------------------------------------------------------------------
DOSE_STATUS_OVERDUE = "overdue"
DOSE_STATUS_DUE = "due"
DOSE_STATUS_UPCOMING = "upcoming"


def local_now(offset_hours: int) -> datetime:
    """Текущее локальное время «по настенным часам», без tzinfo.

    Сервер (Streamlit Cloud) работает в UTC, а расписание приёма пользователь
    задаёт в своём времени. Наивный datetime упрощает сравнение и хранение.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=int(offset_hours))


def parse_dose_times(times: list[str] | None) -> list[time]:
    """'08:00' -> time(8, 0). Мусор молча отбрасывается, результат отсортирован."""
    parsed: list[time] = []
    for raw in times or []:
        text = str(raw).strip()
        match = re.fullmatch(r"(\d{1,2})[:.](\d{2})", text)
        if not match:
            continue
        hour, minute = int(match.group(1)), int(match.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            parsed.append(time(hour, minute))
    return sorted(set(parsed))


def default_times_for(per_day: int) -> list[str]:
    """Разумные часы по числу приёмов в день. Это раскладка по времени суток,
    а не медицинская рекомендация: пользователь правит их вручную."""
    presets = {
        1: ["09:00"],
        2: ["09:00", "21:00"],
        3: ["08:00", "14:00", "20:00"],
        4: ["08:00", "12:00", "16:00", "20:00"],
        5: ["08:00", "11:00", "14:00", "17:00", "20:00"],
        6: ["06:00", "10:00", "14:00", "18:00", "22:00", "02:00"],
    }
    return presets.get(int(per_day), presets[3])


def iter_dose_slots(
    times: list[str] | None,
    start_date: date,
    end_date: Optional[date],
    from_dt: datetime,
    to_dt: datetime,
) -> list[datetime]:
    """Плановые моменты приёма в окне [from_dt, to_dt].

    end_date=None означает бессрочный курс. Границы окна включительные.
    """
    slot_times = parse_dose_times(times)
    if not slot_times or from_dt > to_dt:
        return []

    first_day = max(start_date, from_dt.date())
    last_day = min(end_date, to_dt.date()) if end_date else to_dt.date()

    slots: list[datetime] = []
    day = first_day
    while day <= last_day:
        for slot_time in slot_times:
            moment = datetime.combine(day, slot_time)
            if from_dt <= moment <= to_dt:
                slots.append(moment)
        day += timedelta(days=1)
    return sorted(slots)


def dose_slot_status(slot: datetime, now: datetime, due_window_minutes: int = 60) -> str:
    """overdue — время прошло; due — «пора сейчас»; upcoming — ещё впереди."""
    delta_minutes = (slot - now).total_seconds() / 60
    if delta_minutes < -due_window_minutes:
        return DOSE_STATUS_OVERDUE
    if delta_minutes <= due_window_minutes:
        return DOSE_STATUS_DUE
    return DOSE_STATUS_UPCOMING


def doses_per_day(times: list[str] | None) -> int:
    return len(parse_dose_times(times))


def stock_runs_out_on(
    quantity_remaining: float,
    dose_amount: float,
    times: list[str] | None,
    from_date: date,
) -> Optional[date]:
    """Последний день, на который хватит текущего остатка.

    None — если приёмов в дне нет или доза не задана. Считается кодом:
    это арифметика запаса, а не медицинская рекомендация.
    """
    per_day = doses_per_day(times)
    if per_day <= 0 or dose_amount <= 0:
        return None
    daily_need = per_day * float(dose_amount)
    if daily_need <= 0:
        return None
    full_days = int(float(quantity_remaining) // daily_need)
    if full_days <= 0:
        return None
    return from_date + timedelta(days=full_days - 1)
