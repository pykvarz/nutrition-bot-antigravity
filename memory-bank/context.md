# Memory Bank

## Project Brief
Персональный Telegram-бот для одного пользователя, ведущий дневник еды, калорий, КБЖУ и активности.
Основной интерфейс взаимодействия: голос (распознавание через Groq Whisper), текст и фото (анализ через Gemini).
Отличительная особенность: максимальная скорость и удобство (например, «Съел 500 г курицы и 200 г чечевицы» → готовая запись). Бот поддерживает отмену действий (Undo), создание рецептов, шаблонов блюд, повтор прошлых приёмов пищи и масштабирование порций (например, "съел половину").

## System Patterns
- Архитектура: Cloud Run stateless (scale-to-zero, min=0, max=1). Между запросами нет in-memory состояния.
- Persistent Storage: Google Sheets (листы: Дневник, Шаблоны, Рецепты, Настройки, Состояние, История_действий). Вызовы gspread всегда обернуты в `asyncio.to_thread`.
- Bot API: Webhook-модель (не polling).
- State Management: FSM от aiogram не используется. Состояние (например, pending_action) хранится в листе «Состояние» в Google Sheets (TTL 30 мин).
- Обработка обновлений: Идемпотентность, Telegram update_id проверяется до бизнес-логики.
- Провайдеры LLM: Groq (Whisper-large-v3) для транскрибации, Google Gemini Flash для photo/text понимания, structured output и intent detection.
- Валидация данных: Pydantic. Если Gemini возвращает malformed JSON — ограниченный retry.
- Разделение ответственности: Handlers не работают напрямую с gspread и не считают КБЖУ. Все AI-выводы конвертируются в детерминированные структуры.

## Tech Context
Стек:
- Python 3.11+
- aiogram 3.x
- aiohttp
- Google GenAI SDK (gemini flash)
- Groq API (whisper-large-v3)
- Google Sheets (gspread)
- Pydantic
- Google Cloud Run (хостинг), Google Cloud Scheduler (напоминания и отчеты)

### Команды
- Установка зависимостей: `python -m venv venv && .\venv\Scripts\activate && pip install -r requirements.txt` (или `pip install -r requirements-dev.txt` для разработки)
- Dev-сервер: `python bot/main.py`
- Линтер: `flake8 bot/` или `ruff check bot/`
- Проверка типов: `mypy bot/`
- Тесты: `pytest`
- Сборка: Docker-образ для Cloud Run (через gcloud)

## Progress
- Прочитана документация из папки `docs/` (`brief.md`, `data.md`, `intends.md`, `INVARIANTS.md`, `FUNCTIONALITY.md`, `ACCEPTANCE.md`).
- Сформирована структура `memory-bank/context.md`.
- Ожидается создание плана реализации (Implementation Plan) и начало настройки репозитория (Git/GitHub, scaffolding, .env).
