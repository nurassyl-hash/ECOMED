"""Схемы лечения, напоминания о приёме и списание остатка (FR-19..FR-21).

Границы ответственности: приложение НИЧЕГО не назначает. Пользователь вводит
схему, которую ему назначил врач; сервис только хранит её, показывает, что пора
принять, и после подтверждения списывает остаток из аптечки.

Все расчёты (слоты, «хватит до») — детерминированный код из domain.py.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from ecomed.config import settings
from ecomed.db.database import get_session
from ecomed.db.models import InventoryItem, IntakeEvent, TreatmentCourse
from ecomed.domain import (
    dose_slot_status,
    doses_per_day,
    iter_dose_slots,
    local_now,
    parse_dose_times,
    stock_runs_out_on,
)
from ecomed.services import inventory_service as inv

STATUS_ACTIVE = "active"
STATUS_FINISHED = "finished"
STATUS_CANCELLED = "cancelled"

INTAKE_TAKEN = "taken"
INTAKE_SKIPPED = "skipped"

# Насколько назад показывать пропущенные приёмы. Без ограничения список
# просроченных рос бы бесконечно и перестал быть полезным.
DEFAULT_LOOKBACK_HOURS = 36
DEFAULT_LOOKAHEAD_HOURS = 24


class CourseNotFound(LookupError):
    """Курс не найден или принадлежит другой семье."""


class DoseAlreadyRecorded(ValueError):
    """Этот плановый приём уже подтверждён или пропущен."""


def now_local() -> datetime:
    return local_now(settings.ecomed_tz_offset_hours)


# --------------------------------------------------------------------------
# Курсы лечения
# --------------------------------------------------------------------------
def _course_view(course: TreatmentCourse, item: Optional[InventoryItem]) -> dict:
    times = list(course.times_json or [])
    remaining = float(item.quantity_remaining) if item is not None else 0.0
    runs_out = (
        stock_runs_out_on(remaining, course.dose_amount, times, now_local().date())
        if item is not None
        else None
    )
    return {
        "id": course.id,
        "item_id": course.item_id,
        "person": course.person,
        "medication_name": course.medication_name,
        "dose_amount": course.dose_amount,
        "unit": course.unit,
        "times": times,
        "per_day": doses_per_day(times),
        "start_date": course.start_date.isoformat() if course.start_date else None,
        "end_date": course.end_date.isoformat() if course.end_date else None,
        "note": course.note,
        "status": course.status,
        "quantity_remaining": remaining if item is not None else None,
        "stock_runs_out_on": runs_out.isoformat() if runs_out else None,
        # Запаса не хватит до конца курса — повод пополнить заранее.
        "stock_short": bool(
            item is not None and course.end_date and runs_out and runs_out < course.end_date
        ),
    }


def add_course(
    household_id: int,
    *,
    medication_name: str,
    dose_amount: float,
    times: list[str],
    start_date: date,
    end_date: Optional[date] = None,
    item_id: Optional[int] = None,
    person: Optional[str] = None,
    unit: str = "tablet",
    note: Optional[str] = None,
) -> int:
    """Заводит схему приёма. Значения берутся как есть — это назначение врача."""
    clean_times = [t.strftime("%H:%M") for t in parse_dose_times(times)]
    if not clean_times:
        raise ValueError("Не задано ни одного времени приёма.")
    if float(dose_amount) <= 0:
        raise ValueError("Доза за приём должна быть больше нуля.")
    if end_date and end_date < start_date:
        raise ValueError("Дата окончания раньше даты начала.")

    with get_session() as s:
        if item_id is not None:
            item = s.get(InventoryItem, item_id)
            if item is None or item.household_id != household_id:
                raise PermissionError("Нет доступа к записи другой семьи.")
            if not unit or unit == "tablet":
                unit = item.unit

        course = TreatmentCourse(
            household_id=household_id,
            item_id=item_id,
            person=(person or None),
            medication_name=medication_name,
            dose_amount=float(dose_amount),
            unit=unit,
            times_json=clean_times,
            start_date=start_date,
            end_date=end_date,
            note=(note or None),
            status=STATUS_ACTIVE,
        )
        s.add(course)
        s.flush()
        return course.id


def list_courses(household_id: int, include_inactive: bool = False) -> list[dict]:
    with get_session() as s:
        query = s.query(TreatmentCourse).filter(TreatmentCourse.household_id == household_id)
        if not include_inactive:
            query = query.filter(TreatmentCourse.status == STATUS_ACTIVE)
        courses = query.order_by(TreatmentCourse.created_at.desc()).all()
        return [_course_view(c, s.get(InventoryItem, c.item_id) if c.item_id else None) for c in courses]


def set_course_status(course_id: int, household_id: int, status: str) -> None:
    if status not in (STATUS_ACTIVE, STATUS_FINISHED, STATUS_CANCELLED):
        raise ValueError(f"Недопустимый статус курса: {status}")
    with get_session() as s:
        course = s.get(TreatmentCourse, course_id)
        if course is None or course.household_id != household_id:
            raise CourseNotFound("Курс не найден.")
        course.status = status


# --------------------------------------------------------------------------
# Напоминания: какие приёмы ждут пользователя
# --------------------------------------------------------------------------
def pending_doses(
    household_id: int,
    now: Optional[datetime] = None,
    lookback_hours: int = DEFAULT_LOOKBACK_HOURS,
    lookahead_hours: int = DEFAULT_LOOKAHEAD_HOURS,
) -> list[dict]:
    """Плановые приёмы в окне вокруг «сейчас», по которым ещё нет отметки.

    Напоминание показывается при открытии приложения: фоновых задач и push
    у Streamlit нет, поэтому список считается на лету при каждом заходе.
    """
    now = now or now_local()
    from_dt = now - timedelta(hours=lookback_hours)
    to_dt = now + timedelta(hours=lookahead_hours)

    with get_session() as s:
        courses = (
            s.query(TreatmentCourse)
            .filter(
                TreatmentCourse.household_id == household_id,
                TreatmentCourse.status == STATUS_ACTIVE,
            )
            .all()
        )
        if not courses:
            return []

        recorded = {
            (e.course_id, e.scheduled_for)
            for e in s.query(IntakeEvent)
            .filter(
                IntakeEvent.household_id == household_id,
                IntakeEvent.scheduled_for.isnot(None),
                IntakeEvent.scheduled_for >= from_dt,
                IntakeEvent.scheduled_for <= to_dt,
            )
            .all()
        }

        result: list[dict] = []
        for course in courses:
            item = s.get(InventoryItem, course.item_id) if course.item_id else None
            for slot in iter_dose_slots(
                list(course.times_json or []), course.start_date, course.end_date, from_dt, to_dt
            ):
                if (course.id, slot) in recorded:
                    continue
                result.append({
                    "course_id": course.id,
                    "item_id": course.item_id,
                    "person": course.person,
                    "medication_name": course.medication_name,
                    "dose_amount": course.dose_amount,
                    "unit": course.unit,
                    "scheduled_for": slot,
                    "dose_status": dose_slot_status(slot, now),
                    "quantity_remaining": float(item.quantity_remaining) if item else None,
                    # Подтвердить можно всегда; это лишь подсказка, что списывать нечего.
                    "stock_enough": bool(item is not None and item.quantity_remaining >= course.dose_amount),
                })
        result.sort(key=lambda d: d["scheduled_for"])
        return result


def due_count(household_id: int, now: Optional[datetime] = None) -> int:
    """Сколько приёмов просрочено или наступило прямо сейчас (для баннера)."""
    return sum(
        1 for d in pending_doses(household_id, now=now)
        if d["dose_status"] in ("overdue", "due")
    )


# --------------------------------------------------------------------------
# Отметка приёма
# --------------------------------------------------------------------------
def _apply_stock(household_id: int, item_id: Optional[int], quantity: float) -> bool:
    """Списывает количество из аптечки. False, если списать нечего.

    Факт приёма важнее бухгалтерии: при нехватке остатка приём всё равно
    записывается, а расхождение показывается пользователю.
    """
    if item_id is None or quantity <= 0:
        return False
    try:
        inv.update_quantity(item_id, household_id, -float(quantity), "used")
        return True
    except inv.NegativeStock:
        return False


def confirm_dose(
    household_id: int,
    course_id: int,
    scheduled_for: datetime,
    *,
    taken: bool = True,
    taken_at: Optional[datetime] = None,
) -> dict:
    """Подтверждает («принял») или пропускает плановый приём.

    Возвращает {'intake_id', 'stock_applied', 'quantity', ...}. Списание остатка
    происходит только для taken=True.
    """
    with get_session() as s:
        course = s.get(TreatmentCourse, course_id)
        if course is None or course.household_id != household_id:
            raise CourseNotFound("Курс не найден.")

        already = (
            s.query(IntakeEvent)
            .filter(
                IntakeEvent.course_id == course_id,
                IntakeEvent.scheduled_for == scheduled_for,
            )
            .first()
        )
        if already is not None:
            raise DoseAlreadyRecorded("Этот приём уже отмечен.")

        item_id = course.item_id
        quantity = float(course.dose_amount) if taken else 0.0
        medication_name = course.medication_name
        person = course.person
        unit = course.unit

    stock_applied = _apply_stock(household_id, item_id, quantity) if taken else False

    with get_session() as s:
        event = IntakeEvent(
            household_id=household_id,
            course_id=course_id,
            item_id=item_id,
            person=person,
            medication_name=medication_name,
            scheduled_for=scheduled_for,
            taken_at=taken_at or now_local(),
            quantity=quantity,
            unit=unit,
            status=INTAKE_TAKEN if taken else INTAKE_SKIPPED,
            stock_applied=int(stock_applied),
        )
        s.add(event)
        s.flush()
        return {
            "intake_id": event.id,
            "stock_applied": stock_applied,
            "quantity": quantity,
            "medication_name": medication_name,
            "status": event.status,
        }


def log_manual_intake(
    household_id: int,
    *,
    medication_name: str,
    quantity: float,
    item_id: Optional[int] = None,
    person: Optional[str] = None,
    unit: str = "tablet",
    taken_at: Optional[datetime] = None,
) -> dict:
    """Приём без назначения: пользователь сам отмечает, что принял лекарство."""
    if not str(medication_name).strip():
        raise ValueError("Не указано название лекарства.")
    if float(quantity) <= 0:
        raise ValueError("Количество должно быть больше нуля.")

    with get_session() as s:
        if item_id is not None:
            item = s.get(InventoryItem, item_id)
            if item is None or item.household_id != household_id:
                raise PermissionError("Нет доступа к записи другой семьи.")
            unit = item.unit

    stock_applied = _apply_stock(household_id, item_id, float(quantity))

    with get_session() as s:
        event = IntakeEvent(
            household_id=household_id,
            course_id=None,
            item_id=item_id,
            person=(person or None),
            medication_name=medication_name.strip(),
            scheduled_for=None,
            taken_at=taken_at or now_local(),
            quantity=float(quantity),
            unit=unit,
            status=INTAKE_TAKEN,
            stock_applied=int(stock_applied),
        )
        s.add(event)
        s.flush()
        return {
            "intake_id": event.id,
            "stock_applied": stock_applied,
            "quantity": float(quantity),
            "medication_name": event.medication_name,
            "status": event.status,
        }


def intake_history(household_id: int, limit: int = 50) -> list[dict]:
    with get_session() as s:
        events = (
            s.query(IntakeEvent)
            .filter(IntakeEvent.household_id == household_id)
            .order_by(IntakeEvent.taken_at.desc(), IntakeEvent.id.desc())
            .limit(limit)
            .all()
        )
        return [{
            "id": e.id,
            "course_id": e.course_id,
            "item_id": e.item_id,
            "person": e.person,
            "medication_name": e.medication_name,
            "scheduled_for": e.scheduled_for,
            "taken_at": e.taken_at,
            "quantity": e.quantity,
            "unit": e.unit,
            "status": e.status,
            "stock_applied": bool(e.stock_applied),
            "planned": e.course_id is not None,
        } for e in events]


def adherence(household_id: int, days: int = 7, now: Optional[datetime] = None) -> dict:
    """Сколько плановых приёмов подтверждено за период. Чистая статистика, без оценок."""
    now = now or now_local()
    since = now - timedelta(days=days)
    with get_session() as s:
        events = (
            s.query(IntakeEvent)
            .filter(
                IntakeEvent.household_id == household_id,
                IntakeEvent.course_id.isnot(None),
                IntakeEvent.scheduled_for.isnot(None),
                IntakeEvent.scheduled_for >= since,
                IntakeEvent.scheduled_for <= now,
            )
            .all()
        )
    taken = sum(1 for e in events if e.status == INTAKE_TAKEN)
    skipped = sum(1 for e in events if e.status == INTAKE_SKIPPED)
    return {"taken": taken, "skipped": skipped, "recorded": len(events), "days": days}
