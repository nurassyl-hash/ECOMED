"""Адаптер распознавания упаковки (ТЗ 7.1, раздел 8).

Провайдер заменяемый. Реализация по умолчанию — vision-LLM через OpenAI Agents
SDK со структурированным выводом (output_type=RecognizedPackage). Если ключ не
задан или провайдер недоступен — поднимается ProviderUnavailable, и UI переводит
пользователя на ручную форму (ТЗ 10.3: сбой AI не завершает сценарий ошибкой).
"""
from __future__ import annotations

import base64

from ecomed.config import settings
from ecomed.models.schemas import RecognizedPackage


class ProviderUnavailable(RuntimeError):
    """OCR-провайдер недоступен — нужно перейти на ручной ввод."""


_INSTRUCTIONS = (
    "Ты извлекаешь данные с фотографии упаковки лекарства. Верни СТРОГО поля схемы. "
    "Если поле не читается уверенно — ставь null и снижай field_confidence. "
    "Никогда не выдумывай срок годности и дозировку. Для каждого поля укажи "
    "field_confidence от 0 до 1. Если хоть одно обязательное поле ненадёжно, "
    "поставь needs_user_review=true."
)


def healthcheck() -> dict:
    return {"provider": "openai-vision", "enabled": settings.llm_enabled,
            "model": settings.ecomed_vision_model}


def recognize(image_bytes: bytes, mime: str = "image/jpeg") -> tuple[RecognizedPackage, str]:
    """Распознаёт упаковку. Возвращает (RecognizedPackage, model_version).

    Бросает ProviderUnavailable, если LLM недоступен.
    """
    if not settings.llm_enabled:
        raise ProviderUnavailable("OPENAI_API_KEY не задан — доступен только ручной ввод.")

    try:
        from agents import Agent, Runner  # openai-agents
    except ImportError as e:  # pragma: no cover
        raise ProviderUnavailable(f"openai-agents не установлен: {e}")

    b64 = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{mime};base64,{b64}"

    agent = Agent(
        name="PackageRecognizer",
        instructions=_INSTRUCTIONS,
        model=settings.ecomed_vision_model,
        output_type=RecognizedPackage,
    )
    content = [
        {"type": "input_text", "text": "Извлеки поля с этой упаковки."},
        {"type": "input_image", "image_url": data_url},
    ]
    try:
        result = Runner.run_sync(agent, [{"role": "user", "content": content}])
    except Exception as e:  # сеть/квота/модель без vision
        raise ProviderUnavailable(f"Сбой vision-провайдера: {e}")

    pkg: RecognizedPackage = result.final_output
    return pkg, settings.ecomed_vision_model
