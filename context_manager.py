"""
Управление контекстом диалога пользователей (хранение в оперативной памяти).
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)

# user_id -> list of {"role": "user"|"assistant", "content": str}
_context: dict[int, list[dict[str, Any]]] = {}


def get_context(user_id: int) -> list[dict[str, Any]]:
    """Возвращает список сообщений контекста для пользователя."""
    return _context.get(user_id, []).copy()


def append_messages(user_id: int, user_message: dict[str, Any], assistant_message: dict[str, Any]) -> None:
    """
    Добавляет пару сообщений (пользователь + ответ бота) в контекст и обрезает по лимиту.
    """
    if user_id not in _context:
        _context[user_id] = []
    _context[user_id].append(user_message)
    _context[user_id].append(assistant_message)
    # Обрезка по MAX_CONTEXT_MESSAGES делается в bot при подготовке messages
    logger.debug("Контекст обновлён для user_id=%s, сообщений: %s", user_id, len(_context[user_id]))


def clear_context(user_id: int) -> None:
    """Очищает контекст для указанного пользователя."""
    if user_id in _context:
        del _context[user_id]
        logger.info("Контекст очищен для user_id=%s", user_id)
