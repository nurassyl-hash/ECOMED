"""Добавить препарат: по фото (OCR) или вручную (ТЗ FR-03, 7.1)."""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_r = _Path(__file__).resolve()
while _r.parent != _r and not (_r / "ecomed" / "__init__.py").exists():
    _r = _r.parent
if str(_r) not in _sys.path:
    _sys.path.insert(0, str(_r))

import streamlit as st

from ecomed.config import settings
from ecomed.services import scan_service
from ecomed.ui_common import household_id, page_setup

page_setup("Добавить", "➕")
hid = household_id()

st.title("➕ Добавить препарат")

# --- Выбор способа: фото или ручной ввод ---
mode = st.radio(
    "Как добавить препарат?",
    ["📷 Сфотографировать упаковку", "✍️ Ввести вручную"],
    horizontal=True,
)
manual = mode.startswith("✍️")

if manual:
    st.session_state.pop("scan", None)  # не подставлять старое распознавание
    st.caption("Заполните поля вручную — фотография не требуется. Обязательные поля отмечены звёздочкой.")


def _conf_note(pkg_conf: dict, field: str) -> None:
    c = pkg_conf.get(field)
    if c is None:
        return
    if c >= 0.85:
        st.caption(f"Уверенность {c:.0%} — предзаполнено, подтвердите.")
    elif c >= 0.60:
        st.caption(f"🟡 Уверенность {c:.0%} — проверьте по упаковке.")
    else:
        st.caption(f"🔴 Низкая уверенность {c:.0%} — введите вручную.")


# --- Блок фото (только в режиме фото) ---
if not manual:
    st.caption("Сфотографируйте упаковку — поля заполнятся автоматически. Каждое поле можно исправить до сохранения. Нераспознанные поля не выдумываются.")
    if not settings.llm_enabled:
        st.warning("Vision-провайдер не настроен (нет OPENAI_API_KEY). Переключитесь на «Ввести вручную».", icon="⚠️")

    image_bytes = None
    mime = "image/jpeg"
    tab_cam, tab_up = st.tabs(["📷 Камера", "📁 Загрузить"])
    with tab_cam:
        cam = st.camera_input("Сделайте фото упаковки")
        if cam is not None:
            image_bytes = cam.getvalue()
    with tab_up:
        up = st.file_uploader("JPG или PNG", type=["jpg", "jpeg", "png"])
        if up is not None:
            image_bytes = up.getvalue()
            mime = "image/png" if up.name.lower().endswith("png") else "image/jpeg"

    consent = st.checkbox("Согласен(а) отправить фото внешнему AI-провайдеру для распознавания.", value=False)
    if image_bytes is not None and st.button("🔍 Распознать", type="primary", disabled=not consent):
        with st.spinner("Распознаём упаковку..."):
            st.session_state["scan"] = scan_service.create_scan(hid, image_bytes, mime)

    scan = st.session_state.get("scan")
    if scan and not scan["provider_ok"]:
        st.error(f"Распознавание недоступно: {scan['error']} — заполните форму вручную ниже.")
else:
    scan = None

pkg = (scan or {}).get("package", {})
conf = pkg.get("field_confidence", {})

st.divider()
st.subheader("Карточка препарата")

with st.form("confirm"):
    trade = st.text_input("Торговое название *", value=pkg.get("trade_name") or "")
    if not manual:
        _conf_note(conf, "trade_name")

    inns_default = ", ".join(a["name"] for a in pkg.get("active_ingredients", []))
    inns = st.text_input("Действующие вещества (МНН, через запятую) *", value=inns_default,
                         help="Например: парацетамол. Для комбинированных — через запятую.")
    if not manual:
        _conf_note(conf, "active_ingredients")

    col1, col2 = st.columns(2)
    form = col1.text_input("Форма", value=pkg.get("dosage_form") or "", placeholder="таблетки / сироп / капсулы")
    strengths = [a.get("strength") for a in pkg.get("active_ingredients", []) if a.get("strength")]
    strength = col2.text_input("Дозировка", value=(strengths[0] if strengths else ""), placeholder="500 мг")

    col3, col4, col5 = st.columns(3)
    qty = col3.number_input("Количество *", min_value=0.0, value=float(pkg.get("package_quantity", {}).get("value", 0) or 0), step=1.0)
    unit = col4.text_input("Единица", value=pkg.get("package_quantity", {}).get("unit", "таблетка") or "таблетка")
    expiry = col5.text_input("Срок годности (ГГГГ-ММ-ДД или ГГГГ-ММ)", value=pkg.get("expiry_date") or "", placeholder="2027-05")
    if not manual:
        _conf_note(conf, "expiry_date")

    storage = st.text_input("Место хранения", value="", placeholder="Кухонный шкаф / аптечка")

    submitted = st.form_submit_button("💾 Сохранить в аптечку", type="primary")

if submitted:
    if not trade.strip() or not inns.strip() or qty <= 0:
        st.error("Заполните обязательные поля: название, действующее вещество (МНН) и количество.")
    else:
        item_id = scan_service.confirm_inventory_item(
            hid, (scan or {}).get("scan_id"),
            custom_name=trade.strip(),
            inns=[x.strip() for x in inns.split(",") if x.strip()],
            dosage_form=form.strip() or None,
            strength=strength.strip() or None,
            quantity=qty, unit=unit.strip() or "таблетка",
            expiry_raw=expiry.strip() or None,
            storage_place=storage.strip() or None,
        )
        st.session_state.pop("scan", None)
        st.success(f"Сохранено (id={item_id}). Проверьте возможные дубликаты в разделе «Анализ».")
        st.balloons()
