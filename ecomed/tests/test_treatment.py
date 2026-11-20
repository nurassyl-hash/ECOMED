"""Схема лечения: слоты, напоминания, подтверждение приёма и списание остатка."""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from ecomed.domain import (
    default_times_for,
    dose_slot_status,
    doses_per_day,
    iter_dose_slots,
    parse_dose_times,
    stock_runs_out_on,
)
from ecomed.services import inventory_service as inv
from ecomed.services import treatment_service as tr


# --------------------------------------------------------------------------
# Чистые функции расписания
# --------------------------------------------------------------------------
def test_parse_dose_times_sorts_and_drops_garbage():
    parsed = parse_dose_times(["20:00", "08:00", "нет", "25:00", "08:00", "9.30"])
    assert [t.strftime("%H:%M") for t in parsed] == ["08:00", "09:30", "20:00"]


def test_doses_per_day_counts_unique_times():
    assert doses_per_day(["08:00", "20:00", "08:00"]) == 2
    assert doses_per_day([]) == 0
    assert doses_per_day(None) == 0


def test_default_times_are_distinct_and_match_count():
    for per_day in (1, 2, 3, 4, 5, 6):
        times = default_times_for(per_day)
        assert len(times) == per_day
        assert len(set(times)) == per_day


def test_iter_dose_slots_respects_window_and_course_dates():
    slots = iter_dose_slots(
        ["08:00", "20:00"],
        start_date=date(2026, 8, 26),
        end_date=date(2026, 8, 27),
        from_dt=datetime(2026, 8, 25, 0, 0),
        to_dt=datetime(2026, 8, 31, 23, 59),
    )
    assert slots == [
        datetime(2026, 8, 26, 8, 0),
        datetime(2026, 8, 26, 20, 0),
        datetime(2026, 8, 27, 8, 0),
        datetime(2026, 8, 27, 20, 0),
    ]


def test_iter_dose_slots_open_ended_course():
    """end_date=None — курс бессрочный, окно ограничивает только to_dt."""
    slots = iter_dose_slots(
        ["09:00"], date(2026, 8, 26), None,
        datetime(2026, 8, 26, 0, 0), datetime(2026, 8, 28, 23, 59),
    )
    assert len(slots) == 3


def test_iter_dose_slots_empty_for_inverted_window():
    assert iter_dose_slots(["09:00"], date(2026, 8, 1), None,
                           datetime(2026, 8, 10, 0, 0), datetime(2026, 8, 1, 0, 0)) == []


def test_dose_slot_status_transitions():
    now = datetime(2026, 8, 26, 12, 0)
    assert dose_slot_status(datetime(2026, 8, 26, 8, 0), now) == "overdue"
    assert dose_slot_status(datetime(2026, 8, 26, 12, 30), now) == "due"
    assert dose_slot_status(datetime(2026, 8, 26, 11, 30), now) == "due"
    assert dose_slot_status(datetime(2026, 8, 26, 20, 0), now) == "upcoming"


def test_stock_runs_out_on():
    # 10 таблеток, по 1 штуке дважды в день -> хватит на 5 дней включительно
    assert stock_runs_out_on(10, 1, ["08:00", "20:00"], date(2026, 8, 26)) == date(2026, 8, 30)
    # запаса нет даже на один день
    assert stock_runs_out_on(1, 1, ["08:00", "20:00"], date(2026, 8, 26)) is None
    assert stock_runs_out_on(10, 0, ["08:00"], date(2026, 8, 26)) is None
    assert stock_runs_out_on(10, 1, [], date(2026, 8, 26)) is None


# --------------------------------------------------------------------------
# Курс + приёмы
# --------------------------------------------------------------------------
@pytest.fixture
def item(household):
    return inv.add_item(household, custom_name="Амоксициллин 500 мг", inns=["Амоксициллин"],
                        dosage_form="капсулы", strength="500 мг", quantity=20, unit="капсула")


@pytest.fixture
def course(household, item):
    return tr.add_course(
        household,
        item_id=item,
        medication_name="Амоксициллин 500 мг",
        dose_amount=1,
        times=["08:00", "20:00"],
        start_date=date(2026, 8, 20),
        end_date=date(2026, 8, 30),
        person="Айгерим",
        note="по назначению врача",
    )


def test_add_course_validates_input(household, item):
    with pytest.raises(ValueError):
        tr.add_course(household, medication_name="X", dose_amount=1, times=[],
                      start_date=date(2026, 8, 26))
    with pytest.raises(ValueError):
        tr.add_course(household, medication_name="X", dose_amount=0, times=["08:00"],
                      start_date=date(2026, 8, 26))
    with pytest.raises(ValueError):
        tr.add_course(household, medication_name="X", dose_amount=1, times=["08:00"],
                      start_date=date(2026, 8, 26), end_date=date(2026, 8, 25))


def test_course_view_reports_stock_forecast(household, course):
    (view,) = tr.list_courses(household)
    assert view["per_day"] == 2
    assert view["person"] == "Айгерим"
    assert view["quantity_remaining"] == 20


def test_stock_short_flag_compares_forecast_with_course_end(household):
    """«Хватит до» считается от сегодня, поэтому даты в тесте — относительные."""
    today = tr.now_local().date()
    item_id = inv.add_item(household, custom_name="Курсовой препарат", inns=["Ибупрофен"],
                           quantity=20, unit="таблетка")

    long_course = tr.add_course(household, item_id=item_id, medication_name="Курсовой препарат",
                                dose_amount=1, times=["08:00", "20:00"],
                                start_date=today, end_date=today + timedelta(days=30))
    short_course = tr.add_course(household, item_id=item_id, medication_name="Курсовой препарат",
                                 dose_amount=1, times=["08:00", "20:00"],
                                 start_date=today, end_date=today + timedelta(days=3))

    by_id = {c["id"]: c for c in tr.list_courses(household)}
    # 20 таблеток по 2 в день -> хватит на 10 дней, последний день = сегодня + 9
    assert by_id[long_course]["stock_runs_out_on"] == (today + timedelta(days=9)).isoformat()
    assert by_id[long_course]["stock_short"] is True, "курса на 30 дней запаса не хватит"
    assert by_id[short_course]["stock_short"] is False, "на 3 дня запаса достаточно"


def test_pending_doses_lists_unrecorded_slots(household, course):
    now = datetime(2026, 8, 26, 12, 0)
    doses = tr.pending_doses(household, now=now)
    assert doses, "плановые приёмы должны появиться"
    assert all(d["course_id"] == course for d in doses)
    statuses = {d["dose_status"] for d in doses}
    assert "overdue" in statuses          # утренний приём пропущен
    assert "upcoming" in statuses         # вечерний ещё впереди


def test_confirm_dose_decrements_stock(household, item, course):
    slot = datetime(2026, 8, 26, 8, 0)
    before = inv.get_item(item, household)["quantity_remaining"]

    result = tr.confirm_dose(household, course, slot)

    assert result["stock_applied"] is True
    assert result["status"] == "taken"
    after = inv.get_item(item, household)["quantity_remaining"]
    assert after == before - 1


def test_confirmed_dose_disappears_from_pending(household, course):
    now = datetime(2026, 8, 26, 12, 0)
    slot = datetime(2026, 8, 26, 8, 0)
    assert any(d["scheduled_for"] == slot for d in tr.pending_doses(household, now=now))

    tr.confirm_dose(household, course, slot)

    assert not any(d["scheduled_for"] == slot for d in tr.pending_doses(household, now=now))


def test_same_dose_cannot_be_confirmed_twice(household, course):
    slot = datetime(2026, 8, 26, 8, 0)
    tr.confirm_dose(household, course, slot)
    with pytest.raises(tr.DoseAlreadyRecorded):
        tr.confirm_dose(household, course, slot)


def test_skipped_dose_does_not_touch_stock(household, item, course):
    before = inv.get_item(item, household)["quantity_remaining"]
    result = tr.confirm_dose(household, course, datetime(2026, 8, 26, 8, 0), taken=False)
    assert result["status"] == "skipped"
    assert result["stock_applied"] is False
    assert inv.get_item(item, household)["quantity_remaining"] == before


def test_intake_recorded_even_when_stock_is_empty(household):
    """Факт приёма важнее бухгалтерии: остаток не уходит в минус, приём сохраняется."""
    empty = inv.add_item(household, custom_name="Но-шпа 40 мг", inns=["Дротаверин"],
                         quantity=0, unit="таблетка")
    course = tr.add_course(household, item_id=empty, medication_name="Но-шпа 40 мг",
                           dose_amount=1, times=["08:00"], start_date=date(2026, 8, 20))

    result = tr.confirm_dose(household, course, datetime(2026, 8, 26, 8, 0))

    assert result["status"] == "taken"
    assert result["stock_applied"] is False, "списывать было нечего"
    assert inv.get_item(empty, household)["quantity_remaining"] == 0
    assert tr.intake_history(household)[0]["stock_applied"] is False


def test_course_without_inventory_item_still_tracks(household):
    course = tr.add_course(household, medication_name="Препарат вне аптечки",
                           dose_amount=2, times=["09:00"], start_date=date(2026, 8, 20))
    result = tr.confirm_dose(household, course, datetime(2026, 8, 26, 9, 0))
    assert result["stock_applied"] is False
    (view,) = tr.list_courses(household)
    assert view["quantity_remaining"] is None
    assert view["stock_short"] is False


# --------------------------------------------------------------------------
# Ручная отметка приёма (без назначения)
# --------------------------------------------------------------------------
def test_manual_intake_updates_inventory(household, item):
    before = inv.get_item(item, household)["quantity_remaining"]

    result = tr.log_manual_intake(household, item_id=item,
                                  medication_name="Амоксициллин 500 мг",
                                  quantity=2, person="Нурасыл")

    assert result["stock_applied"] is True
    assert inv.get_item(item, household)["quantity_remaining"] == before - 2
    entry = tr.intake_history(household)[0]
    assert entry["planned"] is False
    assert entry["course_id"] is None
    assert entry["person"] == "Нурасыл"


def test_manual_intake_without_item_is_allowed(household):
    result = tr.log_manual_intake(household, medication_name="Что-то из сумки", quantity=1)
    assert result["stock_applied"] is False
    assert tr.intake_history(household)[0]["item_id"] is None


def test_manual_intake_validates_input(household):
    with pytest.raises(ValueError):
        tr.log_manual_intake(household, medication_name="   ", quantity=1)
    with pytest.raises(ValueError):
        tr.log_manual_intake(household, medication_name="X", quantity=0)


def test_manual_intakes_are_not_deduplicated(household, item):
    """У ручных отметок нет планового слота — принять дважды за день можно."""
    tr.log_manual_intake(household, item_id=item, medication_name="A", quantity=1)
    tr.log_manual_intake(household, item_id=item, medication_name="A", quantity=1)
    assert len(tr.intake_history(household)) == 2


# --------------------------------------------------------------------------
# Изоляция семьи и статусы курса
# --------------------------------------------------------------------------
def test_other_household_cannot_touch_course(household, course):
    with pytest.raises(tr.CourseNotFound):
        tr.confirm_dose(household + 999, course, datetime(2026, 8, 26, 8, 0))
    with pytest.raises(tr.CourseNotFound):
        tr.set_course_status(course, household + 999, tr.STATUS_CANCELLED)


def test_other_household_cannot_attach_foreign_item(household, item):
    with pytest.raises(PermissionError):
        tr.add_course(household + 999, item_id=item, medication_name="X",
                      dose_amount=1, times=["08:00"], start_date=date(2026, 8, 26))


def test_finished_course_stops_reminding(household, course):
    now = datetime(2026, 8, 26, 12, 0)
    assert tr.pending_doses(household, now=now)
    tr.set_course_status(course, household, tr.STATUS_FINISHED)
    assert tr.pending_doses(household, now=now) == []
    assert tr.list_courses(household) == []
    assert len(tr.list_courses(household, include_inactive=True)) == 1


def test_due_count_ignores_upcoming(household, course):
    now = datetime(2026, 8, 26, 12, 0)
    doses = tr.pending_doses(household, now=now)
    expected = sum(1 for d in doses if d["dose_status"] in ("overdue", "due"))
    assert tr.due_count(household, now=now) == expected
    assert tr.due_count(household, now=now) < len(doses)


def test_adherence_counts_recorded_doses(household, course):
    now = datetime(2026, 8, 26, 12, 0)
    tr.confirm_dose(household, course, datetime(2026, 8, 25, 8, 0), taken_at=now)
    tr.confirm_dose(household, course, datetime(2026, 8, 25, 20, 0), taken=False, taken_at=now)

    stats = tr.adherence(household, days=7, now=now)
    assert stats["taken"] == 1
    assert stats["skipped"] == 1
    assert stats["recorded"] == 2


# --------------------------------------------------------------------------
# Демо-данные: раздел не должен быть пустым при показе
# --------------------------------------------------------------------------
def test_seed_creates_demo_course_with_pending_doses(db):
    from ecomed.db.seed import seed_demo

    hid = seed_demo()
    courses = tr.list_courses(hid)
    assert len(courses) == 1, "в демо должна быть ровно одна схема лечения"

    course = courses[0]
    assert course["per_day"] == 3
    assert course["item_id"] is not None, "схема привязана к позиции аптечки"

    doses = tr.pending_doses(hid)
    assert doses, "у демо-схемы должны быть плановые приёмы"
    assert {d["dose_status"] for d in doses} & {"overdue", "due"}, "должен быть повод напомнить"
