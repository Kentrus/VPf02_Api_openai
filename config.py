"""
Конфигурация: секреты из .env, остальные настройки — здесь.
В .env хранятся только BOT_TOKEN и OPENAI_API_KEY.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

# ---------- Из .env (только токены/ключи) ----------
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

# ---------- Настройки в config (редактировать здесь) ----------
OPENAI_MODEL: str = "gpt-4o-mini"
OPENAI_TEMPERATURE: float = 0.2  # 0.0–2.0: выше — случайнее, ниже — предсказуемее
OPENAI_MAX_TOKENS: int = 1024  # макс. токенов в ответе модели (None = по умолчанию API)
OPENAI_SYSTEM_MESSAGE: str = ""  # необязательный system prompt (пусто = не отправляем)
MAX_CONTEXT_MESSAGES: int = 20


def validate_config() -> None:
    """Проверяет наличие обязательных переменных для Telegram-бота."""
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не задан в .env")
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY не задан в .env")


def validate_config_openai() -> None:
    """Проверяет наличие OpenAI API ключа (для CLI и др.)."""
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY не задан в .env")
