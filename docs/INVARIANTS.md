# INVARIANTS — правила, которые нельзя нарушать

## Архитектура

1. Cloud Run stateless. Никакого in-memory state как источника истины.
   Между запросами контейнер может исчезнуть. Всё persistent — в Sheets.

2. In-memory FSM aiogram не использовать. Pending state (EDIT_RECORD,
   target_record_id и т.п.) хранится в листе «Состояние».

3. gspread синхронный. ВСЕГДА оборачивать в `asyncio.to_thread(...)`.
   Прямой вызов из async-хендлера блокирует event loop.

4. Обработка Telegram update — внутри request lifecycle.
   Никаких `asyncio.create_task` после ответа.

5. Ответ пользователю («Добавил 👍») отправляется ТОЛЬКО после
   успешного ответа от Google Sheets API. Не оптимистично.

## Данные

6. ID записи — UUID. Номер строки Sheets использовать нельзя.

7. Каждая food/activity запись содержит поле `Структура_JSON`
   (items + portion_multiplier). Строки «Курица 500г — 825 ккал»
   недостаточно.

8. Пищевая дата считается ОДНОЙ функцией:
   `calculate_food_date(dt, cutoff_hour)`.
   Используется везде: запись, /today, /advice, отчёты, scheduler.
   Cutoff по умолчанию 04:00, timezone Asia/Almaty.
   Никогда не использовать `date.today()`.

9. Telegram update_id проверяется ДО бизнес-логики.
   Если уже обработан — немедленно 200 без обработки.

## Бизнес-правила

10. Приоритет источников данных:
    пользовательский шаблон → рецепт → история → Gemini.
    Что система знает — Gemini не пересчитывает.

11. Activity calories НЕ вычитаются автоматически из food calories.
    Показываются отдельно.

12. Undo работает для всех mutating-операций:
    add/edit/delete food, add activity, 50%, settings, template,
    recipe, repeat. Не работает для /today, /advice, отчётов.

13. КБЖУ всегда пересчитывается из `Структура_JSON` одной функцией.
    Никаких «сохранённых итогов» в обход структуры.

14. Все AI outputs валидируются через Pydantic.
    Malformed JSON → ограниченный retry → ошибка в лог → не создавать
    некорректную запись.

## Границы ответственности

15. Gemini НЕ пишет в Sheets, НЕ удаляет, НЕ меняет settings,
    НЕ подтверждает успешность. Только возвращает structured JSON.

16. Handlers НЕ работают с gspread напрямую. Только через SheetsService.

17. Handlers НЕ считают КБЖУ. Только через NutritionService.

## Безопасность

18. Проверка `ALLOWED_TELEGRAM_USER_ID` — на каждом update.
    Проверка `X-Telegram-Bot-Api-Secret-Token` — на каждом webhook.
    Проверка `X-Scheduler-Secret` — на /jobs/*.

19. Секреты (TELEGRAM_TOKEN, GROQ_API_KEY, GEMINI_API_KEY,
    SCHEDULER_SECRET, WEBHOOK_SECRET) НИКОГДА не логируются.

## Кэш

20. Листы «Шаблоны» и «Настройки» кэшируются in-memory на 5 минут.
    Сброс кэша — только при мутации (создание шаблона, смена целей).