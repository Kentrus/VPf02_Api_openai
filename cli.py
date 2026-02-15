"""
CLI для общения с OpenAI с тем же контекстом и логикой, что и бот.
Запуск: python cli.py
"""
import logging
from typing import Any

from config import MAX_CONTEXT_MESSAGES, OPENAI_MODEL, validate_config_openai
from context_manager import append_messages, clear_context, get_context
from openai_client import chat_completion

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Отдельный user_id для CLI, чтобы не смешивать контекст с Telegram
CLI_USER_ID = -1
CLEAR_PHRASE = "очистить контекст"
EXIT_COMMANDS = ("exit", "quit", "выход")


def _trim_context(messages: list[dict[str, Any]], max_messages: int) -> list[dict[str, Any]]:
    """Оставляет только последние max_messages сообщений."""
    if len(messages) <= max_messages:
        return messages
    return messages[-max_messages:]


def run() -> None:
    validate_config_openai()
    print(f"CLI-чат с OpenAI (модель: {OPENAI_MODEL})")
    print('Введите сообщение. "очистить контекст" — сброс истории. exit / quit / выход — выход.\n')

    while True:
        try:
            text = input("Вы: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nВыход.")
            break

        if not text:
            continue

        if text.lower() in EXIT_COMMANDS:
            print("Выход.")
            break

        if text.lower() == CLEAR_PHRASE.lower():
            clear_context(CLI_USER_ID)
            print("Контекст очищен.\n")
            continue

        context = get_context(CLI_USER_ID)
        context = _trim_context(context, MAX_CONTEXT_MESSAGES)
        messages: list[dict[str, Any]] = context + [{"role": "user", "content": text}]

        try:
            response_text, usage = chat_completion(messages, model=OPENAI_MODEL)
        except Exception as e:
            logger.exception("Ошибка OpenAI: %s", e)
            print("Ошибка при запросе к OpenAI. Попробуйте позже или очистите контекст.\n")
            continue

        append_messages(
            CLI_USER_ID,
            {"role": "user", "content": text},
            {"role": "assistant", "content": response_text},
        )
        print(f"Бот: {response_text}")
        print(f"  [Токены: вход {usage['prompt_tokens']}, выход {usage['completion_tokens']}, всего {usage['total_tokens']}]\n")


if __name__ == "__main__":
    run()
