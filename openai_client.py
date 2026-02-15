"""
Клиент для общения с OpenAI API.
"""
import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from openai import BadRequestError, OpenAI

from config import (
    OPENAI_API_KEY,
    OPENAI_MAX_TOKENS,
    OPENAI_MODEL,
    OPENAI_SYSTEM_MESSAGE,
    OPENAI_TEMPERATURE,
)

logger = logging.getLogger(__name__)

_client: OpenAI | None = None
_usage_run_counter = 0
_usage_log_path: Path | None = None


def _get_usage_log_path() -> Path:
    """Путь к usage.csv: папка, откуда запущен процесс (cwd)/logs/."""
    global _usage_log_path
    if _usage_log_path is None:
        _usage_log_path = Path.cwd() / "logs" / "usage.csv"
    return _usage_log_path


def _log_usage_to_file(
    model: str,
    temperature_used: str | float,
    usage: dict[str, int],
) -> None:
    """Пишет одну строку в logs/usage.csv для отчёта по использованию."""
    global _usage_run_counter
    _usage_run_counter += 1
    path = _get_usage_log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        file_exists = path.exists()
        with open(path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    "run_id", "datetime", "model", "temperature",
                    "prompt_tokens", "completion_tokens", "total_tokens",
                ])
            writer.writerow([
                _usage_run_counter,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                model,
                temperature_used,
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0),
                usage.get("total_tokens", 0),
            ])
        if not file_exists:
            print(f"[Usage] Лог создан: {path.absolute()}", flush=True)
        logger.info("Usage записан: %s (run_id=%s)", path, _usage_run_counter)
    except Exception as e:
        import sys
        print(f"[Usage] Ошибка записи лога: {e}", file=sys.stderr, flush=True)
        logger.warning("Не удалось записать usage в файл: %s", e, exc_info=True)


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def chat_completion(
    messages: list[dict[str, Any]],
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    system_message: str | None = None,
) -> tuple[str, dict[str, int]]:
    """
    Отправляет запрос в OpenAI Chat Completions.
    Возвращает (текст ответа, использование токенов).
    usage: {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}
    """
    model = model or OPENAI_MODEL
    temp = float(temperature if temperature is not None else OPENAI_TEMPERATURE)
    max_tok = max_tokens if max_tokens is not None else OPENAI_MAX_TOKENS
    system = (system_message if system_message is not None else OPENAI_SYSTEM_MESSAGE) or ""
    usage_default = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    client = _get_client()

    # Как в примере: system (если есть) + остальные сообщения
    if system.strip():
        messages = [{"role": "system", "content": system.strip()}] + list(messages)
    else:
        messages = list(messages)

    temperature_used: str | float = temp

    def _build_kwargs(include_temperature: bool) -> dict[str, Any]:
        k: dict[str, Any] = {"model": model, "messages": messages}
        if include_temperature:
            k["temperature"] = temp
        if max_tok > 0:
            k["max_completion_tokens"] = max_tok
        return k

    try:
        response = client.chat.completions.create(**_build_kwargs(include_temperature=True))
    except BadRequestError as e:
        err_msg = (getattr(e, "message", None) or str(e)).lower()
        if "temperature" in err_msg and "unsupported" in err_msg:
            logger.warning("Модель не поддерживает temperature=%s, запрос без temperature", temp)
            response = client.chat.completions.create(**_build_kwargs(include_temperature=False))
            temperature_used = "default"
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
    try:
        _log_usage_to_file(model, temperature_used, usage_default)
    except Exception as e:
        logger.warning("Не удалось записать usage в файл: %s", e, exc_info=True)
    return text, usage_default


# ---------- ДЗ: работа с prompts.json ----------

_PROMPTS_PATH = Path(__file__).resolve().parent / "prompts.json"
_HOMEWORK_RESULTS_PATH = Path.cwd() / "logs" / "homework_results.json"


def load_prompts() -> dict[str, Any]:
    """Читает и возвращает содержимое prompts.json."""
    with open(_PROMPTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_homework_result(
    prompt_id: int,
    result: dict[str, Any],
    usage: dict[str, int],
    parsed: bool = True,
    raw_text: str | None = None,
) -> None:
    """Сохраняет результат запуска домашнего промпта в logs/homework_results.json."""
    _HOMEWORK_RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "prompt_id": prompt_id,
        "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "usage": usage,
        "parsed": parsed,
        "result": result,
    }
    if raw_text is not None:
        entry["raw_text"] = raw_text
    data: list[dict[str, Any]] = []
    if _HOMEWORK_RESULTS_PATH.exists():
        with open(_HOMEWORK_RESULTS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    data.append(entry)
    with open(_HOMEWORK_RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def run_homework_prompt(prompt_id: int) -> dict[str, Any]:
    """
    Запускает промпт из prompts.json по id.
    Возвращает словарь с ключами: result (распарсенный JSON или raw), usage, parsed (bool), error (если был).
    Результат сохраняется в logs/homework_results.json.
    """
    data = load_prompts()
    prompt = None
    for p in data.get("prompts", []):
        if p.get("id") == prompt_id:
            prompt = p
            break
    if not prompt:
        raise ValueError(f"Промпт с id={prompt_id} не найден в prompts.json")

    system = (prompt.get("role") or "").strip()
    fmt = (prompt.get("format") or "").strip()
    if fmt:
        system = f"{system}\n\n{fmt}" if system else fmt

    user_parts = [
        "Контекст: " + (prompt.get("context") or ""),
        "\n\nЗадача: " + (prompt.get("question") or ""),
    ]
    if "example" in prompt and prompt["example"] is not None:
        user_parts.append("\n\nОбразец ответа:\n" + json.dumps(prompt["example"], ensure_ascii=False, indent=2))
    user_content = "".join(user_parts)

    messages = [{"role": "user", "content": user_content}]
    text, usage = chat_completion(messages, model=OPENAI_MODEL, system_message=system)

    parsed = True
    result: dict[str, Any] = {}
    try:
        result = json.loads(text)
    except json.JSONDecodeError as e:
        parsed = False
        result = {"error": f"Не удалось распарсить JSON: {e}", "raw": text}
        logger.warning("Ответ не является валидным JSON: %s", e)

    _save_homework_result(
        prompt_id=prompt_id,
        result=result,
        usage=usage,
        parsed=parsed,
        raw_text=text if not parsed else None,
    )

    return {
        "result": result,
        "usage": usage,
        "parsed": parsed,
    }
