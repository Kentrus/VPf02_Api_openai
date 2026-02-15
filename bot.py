"""
Telegram-бот на aiogram с подключением к OpenAI и контекстом диалога.
"""
import json
import logging
from typing import Any

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message

from config import BOT_TOKEN, MAX_CONTEXT_MESSAGES, OPENAI_MODEL, OPENAI_TEMPERATURE, validate_config
from context_manager import append_messages, clear_context, get_context
from openai_client import chat_completion, load_prompts, run_homework_prompt

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


@dp.message(Command("homework"))
async def cmd_homework(message: Message) -> None:
    """Команда /homework: показывает задачу и список промптов."""
    data = load_prompts()
    task = data.get("homework_task", "")
    lines = [f"*Задача:* {task}", "", "*Промпты:*"]
    for p in data.get("prompts", []):
        lines.append(f"  • {p.get('id')}: {p.get('name', '')}")
    lines.append("")
    lines.append("Отправь номер промпта (1 или 2)")
    await message.answer("\n".join(lines), parse_mode="Markdown")


def _format_prompt_for_display(prompt_entry: dict[str, Any]) -> str:
    """Собирает текст промпта для отображения (role, context, question, format, example)."""
    role = (prompt_entry.get("role") or "").strip()
    context = (prompt_entry.get("context") or "").strip()
    question = (prompt_entry.get("question") or "").strip()
    fmt = (prompt_entry.get("format") or "").strip()
    parts = []
    if role:
        parts.append(f"*Роль:*\n{role}")
    if fmt:
        parts.append(f"*Формат:*\n{fmt}")
    parts.append(f"*Контекст:*\n{context}")
    parts.append(f"*Задача:*\n{question}")
    if prompt_entry.get("example") is not None:
        ex = json.dumps(prompt_entry["example"], ensure_ascii=False, indent=2)
        parts.append(f"*Пример:*\n```json\n{ex}\n```")
    text = "\n\n".join(parts)
    if len(text) > 4000:
        text = text[:3997] + "..."
    return text


@dp.message(F.text.regexp(r"^[12]$"))
async def handle_homework_prompt_choice(message: Message) -> None:
    """Обработка выбора номера промпта (1 или 2) для ДЗ."""
    prompt_id = int(message.text.strip())
    data = load_prompts()
    prompt_entry = next((p for p in data.get("prompts", []) if p.get("id") == prompt_id), None)
    if not prompt_entry:
        await message.answer(f"Промпт с id={prompt_id} не найден.")
        return

    await message.answer(f"Запускаю промпт #{prompt_id}, подожди...")
    prompt_text = _format_prompt_for_display(prompt_entry)
    await message.answer(f"*Промпт:*\n\n{prompt_text}", parse_mode="Markdown")

    try:
        out = run_homework_prompt(prompt_id)
    except Exception as e:
        logger.exception("Ошибка при запуске промпта: %s", e)
        await message.answer(f"Ошибка: {e}")
        return

    name = prompt_entry.get("name", "")
    usage = out.get("usage", {})
    parsed = out.get("parsed", False)
    result = out.get("result", {})

    json_str = json.dumps(result, ensure_ascii=False, indent=2)
    body = (
        f"*Промпт:* {name}\n"
        f"*Валидный JSON:* {'да' if parsed else 'нет'}\n"
        f"*Токены:* вход {usage.get('prompt_tokens', 0)}, выход {usage.get('completion_tokens', 0)}, всего {usage.get('total_tokens', 0)}\n\n"
        f"```json\n{json_str}\n```"
    )
    if len(body) > 4000:
        body = body[:3980] + "\n...\n```"
    await message.answer(body, parse_mode="Markdown")
    await message.answer("Результат сохранён в logs/homework_results.json")


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

    if not response_text.strip():
        logger.warning("Пустой ответ от модели для user_id=%s", user_id)
        await message.answer(
            "Модель вернула пустой ответ. Попробуйте переформулировать или напишите «очистить контекст»."
        )
        return

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
