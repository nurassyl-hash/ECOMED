"""ORM-модели EcoMed AI (ТЗ раздел 11).

МНН хранится как JSON-массив нормализованных идентификаторов (ТЗ 11: не одной строкой).
Ограничения целостности: quantity_remaining >= 0, packages_count >= 0, price >= 0,
household_id обязателен для пользовательских сущностей.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True)
    display_name: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class Household(Base):
    __tablename__ = "households"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class HouseholdMember(Base):
    __tablename__ = "household_members"
    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String)  # owner|editor|viewer
    status: Mapped[str] = mapped_column(String, default="active")


class MedicationCatalog(Base):
    __tablename__ = "medication_catalog"
    id: Mapped[int] = mapped_column(primary_key=True)
    trade_name: Mapped[str] = mapped_column(String)
    inn_json: Mapped[list] = mapped_column(JSON, default=list)  # нормализованные МНН
    dosage_form: Mapped[str | None] = mapped_column(String, nullable=True)
    strength: Mapped[str | None] = mapped_column(String, nullable=True)
    atc: Mapped[str | None] = mapped_column(String, nullable=True)
    registration_no: Mapped[str | None] = mapped_column(String, nullable=True)
    provider: Mapped[str | None] = mapped_column(String, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class InventoryItem(Base):
    __tablename__ = "inventory_items"
    __table_args__ = (
        CheckConstraint("quantity_remaining >= 0", name="ck_qty_nonneg"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"))
    catalog_id: Mapped[int | None] = mapped_column(ForeignKey("medication_catalog.id"), nullable=True)
    custom_name: Mapped[str] = mapped_column(String)
    inn_json: Mapped[list] = mapped_column(JSON, default=list)  # набор нормализованных МНН
    dosage_form: Mapped[str | None] = mapped_column(String, nullable=True)
    strength: Mapped[str | None] = mapped_column(String, nullable=True)
    quantity_remaining: Mapped[float] = mapped_column(Float, default=0)
    unit: Mapped[str] = mapped_column(String, default="tablet")
    package_id: Mapped[str | None] = mapped_column(String, nullable=True)  # GTIN/рег. номер
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_precision: Mapped[str] = mapped_column(String, default="day")  # day|month
    opened_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    after_open_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_place: Mapped[str | None] = mapped_column(String, nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)  # ai|manual
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    events: Mapped[list["InventoryEvent"]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )


class InventoryEvent(Base):
    __tablename__ = "inventory_events"
    __table_args__ = (
        CheckConstraint("price IS NULL OR price >= 0", name="ck_price_nonneg"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.id"))
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"))
    # added|used|discarded|correction|avoided_purchase|purchase_check
    event_type: Mapped[str] = mapped_column(String)
    quantity_delta: Mapped[float] = mapped_column(Float, default=0)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    item: Mapped["InventoryItem"] = relationship(back_populates="events")


class ScanSession(Base):
    """Аудит распознавания (ТЗ FR-18)."""
    __tablename__ = "scan_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"))
    image_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_fields_json: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence_json: Mapped[dict] = mapped_column(JSON, default=dict)
    confirmed_fields_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    model_version: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class TreatmentCourse(Base):
    """Схема лечения, назначенная врачом и введённая пользователем.

    Приложение ничего не назначает: оно хранит то, что ввёл пользователь,
    напоминает о приёме и списывает остаток после подтверждения.
    """
    __tablename__ = "treatment_courses"
    __table_args__ = (
        CheckConstraint("dose_amount > 0", name="ck_dose_positive"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"))
    item_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory_items.id"), nullable=True
    )  # препарата может не быть в аптечке
    person: Mapped[str | None] = mapped_column(String, nullable=True)  # «для кого»
    medication_name: Mapped[str] = mapped_column(String)
    dose_amount: Mapped[float] = mapped_column(Float, default=1)
    unit: Mapped[str] = mapped_column(String, default="tablet")
    times_json: Mapped[list] = mapped_column(JSON, default=list)  # ["08:00", "20:00"]
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # None — бессрочно
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="active")  # active|finished|cancelled
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class IntakeEvent(Base):
    """Факт приёма: по назначению (course_id задан) или отмеченный вручную."""
    __tablename__ = "intake_events"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_intake_qty_nonneg"),
        # Один плановый приём нельзя подтвердить дважды.
        UniqueConstraint("course_id", "scheduled_for", name="uq_course_slot"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"))
    course_id: Mapped[int | None] = mapped_column(
        ForeignKey("treatment_courses.id"), nullable=True
    )  # None — приём без назначения
    item_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_items.id"), nullable=True)
    person: Mapped[str | None] = mapped_column(String, nullable=True)
    medication_name: Mapped[str] = mapped_column(String)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    taken_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    quantity: Mapped[float] = mapped_column(Float, default=0)
    unit: Mapped[str] = mapped_column(String, default="tablet")
    status: Mapped[str] = mapped_column(String, default="taken")  # taken|skipped
    # False, если списать из аптечки не удалось (нет позиции или не хватило остатка).
    stock_applied: Mapped[bool] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class DisposalPoint(Base):
    __tablename__ = "disposal_points"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    accepted_types: Mapped[str | None] = mapped_column(String, nullable=True)
    verified_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="demo")  # demo|verified


class DisposalEvent(Base):
    __tablename__ = "disposal_events"
    __table_args__ = (
        CheckConstraint("packages_count >= 0", name="ck_packages_nonneg"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"))
    item_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_items.id"), nullable=True)
    point_id: Mapped[int | None] = mapped_column(ForeignKey("disposal_points.id"), nullable=True)
    packages_count: Mapped[int] = mapped_column(Integer, default=0)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class PriceOffer(Base):
    __tablename__ = "price_offers"
    id: Mapped[int] = mapped_column(primary_key=True)
    catalog_id: Mapped[int | None] = mapped_column(ForeignKey("medication_catalog.id"), nullable=True)
    trade_name: Mapped[str | None] = mapped_column(String, nullable=True)
    pharmacy: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String, default="KZT")
    package_desc: Mapped[str | None] = mapped_column(String, nullable=True)
    observed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
