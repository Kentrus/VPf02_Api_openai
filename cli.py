"""
CLI для общения с OpenAI с тем же контекстом и логикой, что и бот.
Запуск: python cli.py
"""
import json
import logging
from typing import Any

from config import MAX_CONTEXT_MESSAGES, OPENAI_MODEL, validate_config_openai
from context_manager import append_messages, clear_context, get_context
from openai_client import chat_completion, load_prompts, run_homework_prompt

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


def run_homework_interactive() -> None:
    """Интерактивный режим для запуска промптов из prompts.json (ДЗ)."""
    print("=== ДЗ VPf03: Управляемый промпт ===\n")
    data = load_prompts()
    print("Задача:", data.get("homework_task", ""), "\n")
    prompts = data.get("prompts", [])
    for p in prompts:
        print(f"  {p.get('id')}: {p.get('name', '')}")
    print("  0: Выход\n")

    while True:
        try:
            raw = input("Номер промпта (или 0 для выхода): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n")
            return
        if not raw:
            continue
        try:
            prompt_id = int(raw)
        except ValueError:
            print("Введите число (id промпта или 0).\n")
            continue
        if prompt_id == 0:
            print("Выход из режима ДЗ.\n")
            return

        prompt_entry = next((p for p in prompts if p.get("id") == prompt_id), None)
        if not prompt_entry:
            print(f"Промпт с id={prompt_id} не найден.\n")
            continue

        # Вывод самого промпта
        role = (prompt_entry.get("role") or "").strip()
        context = (prompt_entry.get("context") or "").strip()
        question = (prompt_entry.get("question") or "").strip()
        fmt = (prompt_entry.get("format") or "").strip()
        print("\n--- Промпт (system) ---")
        if role:
            print("Роль:", role)
        if fmt:
            print("Формат:", fmt)
        print("\n--- Промпт (user) ---")
        print("Контекст:", context)
        print("\nЗадача:", question)
        if prompt_entry.get("example") is not None:
            print("\nПример (example):")
            print(json.dumps(prompt_entry["example"], ensure_ascii=False, indent=2))
        print("\n--- Запуск ---\n")

        try:
            out = run_homework_prompt(prompt_id)
        except Exception as e:
            logger.exception("Ошибка при запуске промпта: %s", e)
            print(f"Ошибка: {e}\n")
            continue

        name = prompt_entry.get("name", "")
        usage = out.get("usage", {})
        parsed = out.get("parsed", False)
        result = out.get("result", {})

        print(f"\nПромпт: {name}")
        print(f"Валидный JSON: {'да' if parsed else 'нет'}")
        print(f"Токены: вход {usage.get('prompt_tokens', 0)}, выход {usage.get('completion_tokens', 0)}, всего {usage.get('total_tokens', 0)}")
        print("Результат (JSON):")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("\nРезультат сохранён в logs/homework_results.json\n")


def run() -> None:
    validate_config_openai()
    print(f"CLI-чат с OpenAI (модель: {OPENAI_MODEL})")
    print('Введите сообщение. "очистить контекст" — сброс истории. "homework" — режим ДЗ. exit / quit / выход — выход.\n')

    while True:
        try:
            text = input("Вы: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nВыход.")
            break

        if not text:
            continue

        if text.lower() == "homework":
            run_homework_interactive()
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

        if not response_text.strip():
            print("Бот: (пустой ответ от модели — попробуйте переформулировать или «очистить контекст»)\n")
        else:
            append_messages(
                CLI_USER_ID,
                {"role": "user", "content": text},
                {"role": "assistant", "content": response_text},
            )
            print(f"Бот: {response_text}")
        print(f"  [Токены: вход {usage['prompt_tokens']}, выход {usage['completion_tokens']}, всего {usage['total_tokens']}]\n")


if __name__ == "__main__":
    run()
