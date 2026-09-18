from datetime import datetime, date, timezone, timedelta

from bot.models.food import FoodItem, FoodPayload
from bot.models.diary import DiaryRecord
from bot.models.intents import IntentType, ParsedIntent
from bot.models.state import BotState


def test_food_item_creation():
    item = FoodItem(
        name="Куриное филе",
        amount=200,
        unit="g",
        calories=220,
        protein=46,
        fat=2.4,
        carbs=0,
    )
    assert item.name == "Куриное филе"
    assert item.calories == 220
    assert item.protein == 46


def test_food_payload_totals_and_scaling():
    item1 = FoodItem(name="Курица", amount=200, unit="g", calories=220, protein=46, fat=2.4, carbs=0)
    item2 = FoodItem(name="Рис", amount=100, unit="g", calories=130, protein=2.7, fat=0.3, carbs=28)

    payload = FoodPayload(items=[item1, item2], portion_multiplier=1.0)
    assert payload.total_calories == 350
    assert payload.total_protein == 48.7
    assert payload.total_fat == 2.7
    assert payload.total_carbs == 28

    # Scaling portion by half (0.5)
    scaled = payload.scale(0.5)
    assert scaled.portion_multiplier == 0.5
    assert scaled.total_calories == 175
    assert scaled.total_protein == 24.35
    assert scaled.effective_items[0].amount == 100


def test_diary_record_to_sheet_row():
    payload = FoodPayload(
        items=[FoodItem(name="Яблоко", amount=150, unit="g", calories=78, protein=0.4, fat=0.2, carbs=19)]
    )
    record = DiaryRecord(
        id="test-uuid-1234",
        telegram_update_id=987654,
        real_time=datetime(2026, 9, 18, 14, 0, 0),
        food_date=date(2026, 9, 18),
        name="Яблоко",
        calories=78,
        protein=0.4,
        fat=0.2,
        carbs=19,
        source="text",
        record_type="food",
        json_structure=payload.model_dump_json(),
        telegram_message_id=111,
    )

    row = record.to_sheet_row()
    # Check columns according to docs/data.md:
    # ID_записи | Telegram_Update_ID | Реальное_время | Расчетная_дата |
    # Что_съедено | Ккал | Б | Ж | У | Источник | Тип | Структура_JSON |
    # Оригинальный_текст | Telegram_Message_ID | Примечание
    assert len(row) == 15
    assert row[0] == "test-uuid-1234"
    assert row[1] == 987654
    assert row[4] == "Яблоко"
    assert row[5] == 78


def test_diary_record_from_sheet_row_with_commas():
    # Google Sheets with Russian/European locale returns decimals with commas like '3,6'
    row = [
        "rec-123", "1", "2026-09-18T10:00:00", "2026-09-18",
        "Творог", "240,5", "36,2", "10,1", "3,6", "text", "food",
        "{}", "съел творог", "1", ""
    ]
    record = DiaryRecord.from_sheet_row(row)
    assert record.calories == 240.5
    assert record.protein == 36.2
    assert record.fat == 10.1
    assert record.carbs == 3.6


def test_bot_state_ttl():
    now = datetime.now(timezone.utc)
    fresh_state = BotState(
        pending_action="awaiting_confirmation",
        updated_at=now,
    )
    assert fresh_state.is_expired(ttl_minutes=30) is False

    old_state = BotState(
        pending_action="awaiting_confirmation",
        updated_at=now - timedelta(minutes=31),
    )
    assert old_state.is_expired(ttl_minutes=30) is True


def test_parsed_intent_model():
    intent = ParsedIntent(
        intent=IntentType.ADD_FOOD,
        raw_text="съел 200г творога",
        confidence=0.95,
    )
    assert intent.intent == IntentType.ADD_FOOD
    assert intent.confidence == 0.95
