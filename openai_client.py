"""
Клиент для общения с OpenAI API.
"""
import logging
from typing import Any

from openai import OpenAI
from openai import BadRequestError

from config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_TEMPERATURE

logger = logging.getLogger(__name__)

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def chat_completion(
    messages: list[dict[str, Any]],
    model: str | None = None,
    temperature: float | None = None,
) -> tuple[str, dict[str, int]]:
    """
    Отправляет запрос в OpenAI Chat Completions.
    Возвращает (текст ответа, использование токенов).
    usage: {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}
    """
    model = model or OPENAI_MODEL
    temp = temperature if temperature is not None else OPENAI_TEMPERATURE
    usage_default = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    client = _get_client()

    def _request(use_temperature: bool) -> Any:
        kwargs = {"model": model, "messages": messages}
        if use_temperature:
            kwargs["temperature"] = temp
        return client.chat.completions.create(**kwargs)

    try:
        response = _request(use_temperature=True)
    except BadRequestError as e:
        err_msg = (e.message or str(e)).lower()
        if "temperature" in err_msg and "unsupported" in err_msg:
            logger.warning("Модель не поддерживает temperature=%s, запрос без temperature", temp)
            response = _request(use_temperature=False)
        else:
            raise

    content = response.choices[0].message.content
    text = (content or "").strip()
    if response.usage:
        usage_default = {
            "prompt_tokens": getattr(response.usage, "prompt_tokens", 0) or 0,
            "completion_tokens": getattr(response.usage, "completion_tokens", 0) or 0,
            "total_tokens": getattr(response.usage, "total_tokens", 0) or 0,
        }
    return text, usage_default
