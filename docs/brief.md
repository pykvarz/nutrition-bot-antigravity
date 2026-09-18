# Telegram-бот учёта питания

## Что

Персональный Telegram-бот для одного пользователя. Ведёт дневник еды,
калорий, КБЖУ и активности. Основной интерфейс — голос, но также
поддерживаются текст и фото.

## Зачем

Пользователь должен вести дневник практически не отвлекаясь:
сказал голосом «съел 500 г курицы и 200 г чечевицы» — запись появилась.
Может исправлять, повторять прошлую еду, создавать шаблоны и рецепты,
работать с порциями, отменять действия.

## Стек

- Python 3.11+, aiogram 3.x, aiohttp
- Groq API (whisper-large-v3) — транскрипция голоса
- Google GenAI SDK (gemini flash) — понимание текста и фото
- Google Sheets (gspread) — единственное persistent-хранилище
- Pydantic — валидация
- Google Cloud Run — хостинг, webhook, scale-to-zero
- Google Cloud Scheduler — напоминания и отчёты

## Платформа

Google Cloud Run. min=0, max=1, concurrency=1.
Telegram Webhook, не polling. APScheduler не использовать.
Всё состояние — в Google Sheets.