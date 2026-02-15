"""
Telegram-бот на aiogram с подключением к OpenAI и контекстом диалога.
"""
import logging
from typing import Any

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message

from config import BOT_TOKEN, MAX_CONTEXT_MESSAGES, OPENAI_MODEL, OPENAI_TEMPERATURE, validate_config
from context_manager import append_messages, clear_context, get_context
from openai_client import chat_completion

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

CLEAR_PHRASE = "очистить контекст"


def _trim_context(messages: list[dict[str, Any]], max_messages: int) -> list[dict[str, Any]]:
    """Оставляет только последние max_messages сообщений (парами user+assistant)."""
    if len(messages) <= max_messages:
        return messages
    return messages[-max_messages:]


@dp.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Привет! Я бот с GPT. Пиши мне сообщения — я буду отвечать с учётом контекста.\n"
        'Чтобы сбросить историю, напиши: "очистить контекст"'
    )


@dp.message(F.text)
async def handle_text(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    text = (message.text or "").strip()

    if not text:
        return

    # Команда очистки контекста
    if text.lower() == CLEAR_PHRASE.lower():
        clear_context(user_id)
        await message.answer("Контекст очищен. Можем начать диалог заново.")
        return

    # Собираем контекст и добавляем новое сообщение пользователя
    context = get_context(user_id)
    context = _trim_context(context, MAX_CONTEXT_MESSAGES)
    messages: list[dict[str, Any]] = context + [{"role": "user", "content": text}]

    try:
        response_text, usage = chat_completion(messages, model=OPENAI_MODEL)
    except Exception as e:
        logger.exception("OpenAI error for user_id=%s: %s", user_id, e)
        await message.answer(
            "Произошла ошибка при обращении к OpenAI. Попробуйте позже или очистите контекст."
        )
        return

    logger.info(
        "user_id=%s | токены: вход=%s, выход=%s, всего=%s",
        user_id,
        usage["prompt_tokens"],
        usage["completion_tokens"],
        usage["total_tokens"],
    )

    # Обновляем контекст: добавляем сообщение пользователя и ответ ассистента
    append_messages(
        user_id,
        {"role": "user", "content": text},
        {"role": "assistant", "content": response_text},
    )

    # Telegram лимит длины сообщения ~4096
    if len(response_text) > 4000:
        response_text = response_text[:3997] + "..."
    await message.answer(response_text)


async def main() -> None:
    validate_config()
    logger.info("Бот запущен, модель: %s, температура: %s", OPENAI_MODEL, OPENAI_TEMPERATURE)
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
