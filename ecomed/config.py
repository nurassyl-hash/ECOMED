"""Конфигурация и секреты EcoMed AI.

Паттерн скопирован из practical_ai_engineering (rag_workshop/config.py):
pydantic-settings + экспорт ключа в os.environ для OpenAI Agents SDK.
"""
from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Абсолютный путь: .env лежит рядом с пакетом, а рабочая папка при
        # `streamlit run ecomed/app.py` — родительская (ECOMED), не ecomed/.
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        env_prefix="",
        extra="ignore",
    )

    # LLM
    openai_api_key: str = ""
    ecomed_vision_model: str = "gpt-4o"
    ecomed_text_model: str = "gpt-4o-mini"

    # Хранилище
    ecomed_db_path: str = "ecomed.db"

    # Продуктовые дефолты
    ecomed_default_city: str = "Алматы"

    # Провайдер цен в аптеках: "demo" (локальный CSV) или "api" (партнёрский сервис).
    ecomed_prices_provider: str = "demo"
    ecomed_prices_api_url: str = ""
    ecomed_prices_api_key: str = ""

    @property
    def db_url(self) -> str:
        path = Path(self.ecomed_db_path)
        if not path.is_absolute():
            path = ROOT / path
        return f"sqlite:///{path}"

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key.strip())


settings = Settings()

# SDK-библиотеки (openai-agents) читают ключ из окружения.
if settings.openai_api_key:
    os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)
