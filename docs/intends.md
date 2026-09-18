
---

## Файл 4: `INTENTS.md` — список интентов

```markdown
# Интенты

## Минимальный набор

| Intent | Пример |
|---|---|
| ADD_FOOD | «Съел 500 г курицы и 200 г чечевицы» |
| ADD_ACTIVITY | «Бег 5 км», «Прошёл 12 тысяч шагов» |
| CREATE_TEMPLATE | «Запомни как стандартный ужин» |
| UPDATE_TEMPLATE | «В стандартном ужине курицы 300 г» |
| CREATE_RECIPE | «Приготовил 600 г курицы, 300 г чечевицы, 4 порции» |
| ADD_RECIPE_PORTION | «Съел полторы порции» |
| EDIT_LAST_RECORD | «Курицы было 300 грамм» (после кнопки Исправить) |
| EDIT_RECORD | «Исправь последнюю: убери майонез» |
| DELETE_LAST_RECORD | «Удали последнее» |
| REPEAT_LAST_MEAL | «Повтори последний приём пищи» |
| REPEAT_PREVIOUS_MEAL | «Съел то же, что вчера вечером» |
| UNDO_LAST_ACTION | «Отмени», /undo |
| GET_TODAY_SUMMARY | /today, «Сколько сегодня калорий?» |
| GET_ADVICE | /advice, «Что мне ещё поесть?» |
| UPDATE_SETTINGS | «Поставь цель 1800 калорий» |
| GET_SETTINGS | /settings, «Какие у меня цели?» |
| UNKNOWN | всё остальное |

## Масштабирование порций (не интент, а параметр)

Поддерживать: 50%, половина, треть, четверть, две трети, 70%,
1.5 порции, полторы порции, 2 порции.

Умножение — обычной математикой. Gemini для этого не нужен.

## Порядок обработки одного сообщения
Webhook принимает update

Проверка X-Telegram-Bot-Api-Secret-Token → 403 если нет

Проверка ALLOWED_TELEGRAM_USER_ID → 403 если нет

Проверка update_id в «Состояние» → 200 если уже обработан

Регистрация update_id как «обрабатывается»

Тип сообщения:

voice → Groq → transcript

photo → Gemini multimodal

text → как есть

Один общий text pipeline:
intent detection (Gemini structured output + Pydantic)

Domain logic:
template lookup → recipe lookup → history lookup
Gemini — только для неизвестного

Pydantic validation результата

Расчёт food_date через calculate_food_date

Запись в Sheets (через to_thread)

Только после успеха — ответ пользователю

Отметить update_id как обработанный

Inline buttons: Исправить / 50% / Удалить / В шаблон


## Что НЕ показывать пользователю

- JSON
- confidence
- internal intent
- Python exceptions
- API details