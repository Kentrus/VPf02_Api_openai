# Telegram-бот с OpenAI

Telegram-бот на Python (aiogram) с подключением к OpenAI API. У каждого пользователя свой контекст диалога; поддерживается режим общения через CLI и режим ДЗ (управляемые промпты из `prompts.json`).

## Требования

- Python 3.10+
- Токен бота от [@BotFather](https://t.me/BotFather)
- API-ключ [OpenAI](https://platform.openai.com/api-keys)

## Установка

1. Клонируйте репозиторий и перейдите в папку проекта.

2. Создайте виртуальное окружение и установите зависимости:

   ```bash
   python -m venv venv
   venv\Scripts\activate   # Windows
   # source venv/bin/activate   # Linux/macOS
   pip install -r requirements.txt
   ```

3. Создайте файл `.env` в корне проекта (скопируйте из `.env.example`) и укажите только секреты:

   ```env
   BOT_TOKEN=ваш_токен_от_BotFather
   OPENAI_API_KEY=ваш_ключ_OpenAI
   ```

   Модель, температура и лимит контекста настраиваются в `config.py`.

## Запуск

### Telegram-бот

```bash
python main.py
```

или:

```bash
python bot.py
```

Бот отвечает в Telegram с учётом истории диалога.

- **очистить контекст** — сброс истории диалога  
- **/homework** — режим ДЗ: выбор промпта из `prompts.json` (1 или 2), запуск и вывод результата в JSON

### CLI (терминал)

```bash
python cli.py
```

Общение с той же моделью и логикой контекста в терминале. Для CLI нужен только `OPENAI_API_KEY` в `.env`.

- **очистить контекст** — сброс истории диалога  
- **homework** — режим ДЗ: выбор промпта по id, запуск и вывод результата (и самого промпта)  
- **exit** / **quit** / **выход** — выход из CLI  

Контекст CLI хранится отдельно от контекста пользователей в Telegram.

## Структура проекта

| Файл / папка | Назначение |
|--------------|------------|
| `main.py` | Точка входа для запуска бота |
| `bot.py` | Логика Telegram-бота (aiogram), команды /start, /homework и обработка текста |
| `cli.py` | Режим общения в терминале (CLI) и режим ДЗ по команде `homework` |
| `config.py` | Секреты из `.env`, остальные настройки (модель, температура, max_tokens, system message, лимит контекста) |
| `openai_client.py` | Запросы к OpenAI API, логирование usage, функции ДЗ (`load_prompts`, `run_homework_prompt`) |
| `context_manager.py` | Хранение контекста диалога в памяти (dict) |
| `prompts.json` | Промпты для ДЗ: задача и список промптов (id, name, role, context, question, format, example) |
| `logs/usage.csv` | Автозапись токенов по каждому запросу (бот, CLI, ДЗ) |
| `logs/homework_results.json` | Результаты запусков промптов ДЗ (после команды /homework или homework) |
| `.env` | Только секреты — не коммитить (есть в `.gitignore`) |
| `.env.example` | Шаблон для `.env` (только BOT_TOKEN и OPENAI_API_KEY) |
| `.gitignore` | Исключения для git (.env, venv, logs/, __pycache__ и др.) |

## Используемые библиотеки

- **aiogram** — работа с Telegram Bot API  
- **openai** — официальный клиент OpenAI  
- **python-dotenv** — загрузка переменных из `.env`  

## Обработка ошибок и логи

- Ошибки OpenAI логируются; пользователю отправляется сообщение с просьбой повторить или очистить контекст.
- Если модель не поддерживает параметр `temperature`, запрос повторяется без него (в логах — предупреждение).
- Для лимита длины ответа используется `max_completion_tokens` (в config — `OPENAI_MAX_TOKENS`).
- Уровень логирования для бота — INFO, для CLI — WARNING (чтобы не засорять вывод в терминале).
- После каждого ответа ведётся подсчёт токенов (вход, выход, всего): в боте — в логах, в CLI — под ответом; все запросы пишутся в `logs/usage.csv`.
