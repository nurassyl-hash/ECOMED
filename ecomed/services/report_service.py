"""Аналитика и ежемесячный отчёт (ТЗ FR-12, 7.3, 13.3, 14.2).

Все числа считаются кодом детерминированно. LLM получает только готовый JSON
агрегатов и превращает его в текст; вывод проходит пост-фильтр безопасности.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from ecomed.config import settings
from ecomed.db.database import get_session
from ecomed.db.models import DisposalEvent, InventoryEvent, InventoryItem, PriceOffer
from ecomed.domain import expiry_status, effective_expiry, normalize_inn
from ecomed.models.schemas import ExpiryStatus, ReportMetrics
from ecomed.policies.medical_safety import REPORT_SYSTEM_PROMPT, post_filter
from ecomed.services.matching_service import find_duplicates

_QTY_EVENTS = {"added", "used", "discarded", "correction"}


def _price_map() -> dict[str, float]:
    with get_session() as s:
        offers = s.query(PriceOffer).all()
        m: dict[str, float] = {}
        for o in offers:
            if o.price is None:
                continue
            key = normalize_inn(o.trade_name or "")
            if key:
                m[key] = o.price
        return m


def price_lookup(name: str) -> Optional[float]:
    """Демо-цена по торговому названию (первый токен), или None."""
    if not name:
        return None
    prices = _price_map()
    key = normalize_inn(name)
    if key in prices:
        return prices[key]
    first = key.split(" ")[0] if key else ""
    return prices.get(first)


def compute_metrics(
    household_id: int,
    *,
    stale_days: int = 365,
    today: Optional[date] = None,
    period_label: str = "",
) -> ReportMetrics:
    today = today or date.today()
    cutoff = datetime.now(timezone.utc) - timedelta(days=stale_days)
    prices = _price_map()

    with get_session() as s:
        items = s.query(InventoryItem).filter(InventoryItem.household_id == household_id).all()
        events = s.query(InventoryEvent).filter(InventoryEvent.household_id == household_id).all()
        disposed = s.query(DisposalEvent).filter(DisposalEvent.household_id == household_id).all()

        by_status: dict[str, int] = {st.value: 0 for st in ExpiryStatus}
        unique_inns: set[str] = set()
        gaps = {"missing_expiry": 0, "missing_inn": 0, "missing_storage": 0}
        potential = 0.0

        for it in items:
            eff = effective_expiry(it.expiry_date, it.opened_at, it.after_open_days)
            by_status[expiry_status(eff, today).value] += 1
            for inn in (it.inn_json or []):
                unique_inns.add(inn)
            if it.expiry_date is None:
                gaps["missing_expiry"] += 1
            if not (it.inn_json or []):
                gaps["missing_inn"] += 1
            if not it.storage_place:
                gaps["missing_storage"] += 1
            price = prices.get(normalize_inn(it.custom_name))
            if price is not None:
                potential += price

        # события расхода по позициям → «застоявшиеся» позиции
        last_qty_event: dict[int, datetime] = {}
        confirmed_savings = 0.0
        avoided = 0
        checks = 0
        for ev in events:
            created = ev.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if ev.event_type in _QTY_EVENTS:
                prev = last_qty_event.get(ev.item_id)
                if prev is None or created > prev:
                    last_qty_event[ev.item_id] = created
            elif ev.event_type == "avoided_purchase":
                avoided += 1
                if ev.price:
                    confirmed_savings += ev.price
            elif ev.event_type == "purchase_check":
                checks += 1

        stale = 0
        for it in items:
            last = last_qty_event.get(it.id)
            if last is None or last < cutoff:
                stale += 1

        disposed_packages = sum(d.packages_count for d in disposed)

    dup_groups = len(find_duplicates(household_id))

    return ReportMetrics(
        total_items=len(items),
        unique_inns=len(unique_inns),
        by_status=by_status,
        duplicate_groups=dup_groups,
        stale_items=stale,
        data_gaps=gaps,
        confirmed_savings=round(confirmed_savings, 2),
        potential_stock_value=round(potential, 2),
        avoided_purchases=avoided,
        disposed_packages=disposed_packages,
        purchase_checks=checks,
        period_label=period_label,
    )


def _template_summary(m: ReportMetrics) -> str:
    parts = [
        f"{m.total_items} упаковок, {m.unique_inns} уникальных действующих веществ.",
        f"По срокам: просрочено {m.by_status.get('expired',0)}, "
        f"до 30 дней {m.by_status.get('critical',0)}, "
        f"31–90 дней {m.by_status.get('soon',0)}, "
        f"более 90 дней {m.by_status.get('ok',0)}, "
        f"неизвестно {m.by_status.get('unknown',0)}.",
        f"Возможных групп дубликатов: {m.duplicate_groups}.",
        f"Позиций без зафиксированных изменений остатка за период: {m.stale_items}.",
        f"Подтверждённая экономия: {m.confirmed_savings} KZT; "
        f"предотвращённых покупок: {m.avoided_purchases}; "
        f"подтверждённо переданных упаковок: {m.disposed_packages}.",
    ]
    return " ".join(parts)


def generate_summary(m: ReportMetrics) -> tuple[str, bool]:
    """Текст пояснения к отчёту. Возвращает (текст, использован_llm).

    Всегда проходит через пост-фильтр медицинской безопасности.
    """
    if not settings.llm_enabled:
        return _template_summary(m), False

    try:
        from agents import Agent, Runner

        agent = Agent(
            name="ReportExplainer",
            instructions=REPORT_SYSTEM_PROMPT,
            model=settings.ecomed_text_model,
        )
        prompt = "Опиши эти показатели домашней аптечки:\n" + m.model_dump_json()
        result = Runner.run_sync(agent, prompt)
        text = str(result.final_output)
    except Exception:
        return _template_summary(m), False

    safe_text, replaced = post_filter(text)
    if replaced:
        # модель нарушила правила — возвращаем безопасный детерминированный текст
        return _template_summary(m), False
    return safe_text, True
