# Формат данных

## Google Sheets: листы и колонки

### Дневник
ID_записи | Telegram_Update_ID | Реальное_время | Расчетная_дата |
Что_съедено | Ккал | Б | Ж | У | Источник | Тип | Структура_JSON |
Оригинальный_текст | Telegram_Message_ID | Примечание

- ID_записи: UUID
- Расчетная_дата: рассчитывается через calculate_food_date
- Тип: `food` | `activity`
- Источник: `voice` | `text` | `photo` | `template` | `recipe` | `repeat` | `gemini`

### Шаблоны
Название_блюда | Калории | Белки | Жиры | Углеводы | Структура_JSON | Примечание

### Рецепты
ID_рецепта | Название | Дата_создания | Количество_порций |
Ккал_всего | Белки_всего | Жиры_всего | Углеводы_всего |
Ккал_на_порцию | Белки_на_порцию | Жиры_на_порцию | Углеводы_на_порцию |
Структура_JSON | Примечание

### Настройки
Ключ | Значение

Ключи: TARGET_CALORIES, TARGET_PROTEIN, TARGET_FAT, TARGET_CARBS,
TIMEZONE, DAY_CUTOFF_HOUR

### Состояние
Ключ | Значение | Updated_At

Ключи: pending_action, target_record_id, target_template_id,
target_recipe_id, pending_payload, last_processed_update_id

### История_действий
ID_действия | Время | Тип_действия | Entity_Type | Entity_ID |
Before_JSON | After_JSON | Undone

## Структура_JSON (пример)

```json
{
  "items": [
    {
      "id": "item_1",
      "name": "Куриная грудка",
      "amount": 500,
      "unit": "g",
      "calories": 825,
      "protein": 155,
      "fat": 18,
      "carbs": 0,
      "source": "gemini"
    }
  ],
  "portion_multiplier": 1.0,
  "repeated_from_record_id": null
}