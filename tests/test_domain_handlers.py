import pytest
from datetime import datetime, date, timezone
from unittest.mock import MagicMock, AsyncMock

from bot.models.intents import IntentType, ParsedIntent
from bot.models.food import FoodPayload, FoodItem
from bot.models.activity import ActivityItem
from bot.models.diary import DiaryRecord
from bot.models.state import BotState
from bot.handlers.domain import DomainHandler
from bot.services.nutrition_service import NutritionService


@pytest.fixture
def mock_sheets():
    sheets = MagicMock()
    sheets.add_diary_record = AsyncMock()
    sheets.get_last_diary_record = AsyncMock()
    sheets.get_diary_records_for_date = AsyncMock(return_value=[])
    sheets.get_settings = AsyncMock(return_value={
        "TARGET_CALORIES": 2000.0,
        "TARGET_PROTEIN": 140.0,
        "TARGET_FAT": 60.0,
        "TARGET_CARBS": 220.0,
        "TIMEZONE": "Asia/Almaty",
        "DAY_CUTOFF_HOUR": 4,
    })
    sheets.get_state = AsyncMock(return_value=BotState())
    sheets.set_state = AsyncMock()
    sheets.delete_diary_record = AsyncMock(return_value=True)
    sheets.log_action = AsyncMock(return_value="action-id-1")
    return sheets


@pytest.mark.asyncio
async def test_handle_add_food(mock_sheets):
    nutrition_service = NutritionService()
    handler = DomainHandler(sheets_service=mock_sheets, nutrition_service=nutrition_service)

    intent = ParsedIntent(
        intent=IntentType.ADD_FOOD,
        food_payload=FoodPayload(
            items=[FoodItem(name="Овсянка", amount=100, unit="g", calories=360, protein=12, fat=6, carbs=65)]
        ),
        raw_text="съел 100г овсянки",
    )

    response_text = await handler.process_intent(intent, update_id=201, message_id=555)

    assert "Овсянка" in response_text
    assert "360" in response_text
    assert mock_sheets.add_diary_record.called
    added_rec: DiaryRecord = mock_sheets.add_diary_record.call_args[0][0]
    assert added_rec.name == "Овсянка"
    assert added_rec.calories == 360
    assert added_rec.telegram_update_id == 201


@pytest.mark.asyncio
async def test_handle_add_activity(mock_sheets):
    nutrition_service = NutritionService()
    handler = DomainHandler(sheets_service=mock_sheets, nutrition_service=nutrition_service)

    intent = ParsedIntent(
        intent=IntentType.ADD_ACTIVITY,
        activity_item=ActivityItem(name="Бег", duration_minutes=30, calories_burned=250),
        raw_text="бег 30 минут",
    )

    response_text = await handler.process_intent(intent, update_id=202)

    assert "Бег" in response_text
    assert "250" in response_text
    assert mock_sheets.add_diary_record.called
    added_rec: DiaryRecord = mock_sheets.add_diary_record.call_args[0][0]
    assert added_rec.record_type == "activity"
    assert added_rec.calories == 250


@pytest.mark.asyncio
async def test_handle_undo(mock_sheets):
    nutrition_service = NutritionService()
    last_rec = DiaryRecord(
        id="rec-to-undo",
        telegram_update_id=199,
        real_time=datetime.now(timezone.utc),
        food_date=date(2026, 9, 18),
        name="Пицца",
        calories=800,
        source="text",
        json_structure="{}",
    )
    mock_sheets.get_last_diary_record.return_value = last_rec

    handler = DomainHandler(sheets_service=mock_sheets, nutrition_service=nutrition_service)
    intent = ParsedIntent(intent=IntentType.UNDO, raw_text="отмени")

    response_text = await handler.process_intent(intent, update_id=203)

    assert "Пицца" in response_text
    assert mock_sheets.delete_diary_record.called
    assert mock_sheets.delete_diary_record.call_args[0][0] == "rec-to-undo"


@pytest.mark.asyncio
async def test_handle_today(mock_sheets):
    nutrition_service = NutritionService()
    today_rec = DiaryRecord(
        id="rec-1",
        telegram_update_id=198,
        real_time=datetime.now(timezone.utc),
        food_date=date(2026, 9, 18),
        name="Гречка с курицей",
        calories=450,
        protein=40,
        fat=10,
        carbs=50,
        source="text",
        json_structure="{}",
    )
    mock_sheets.get_diary_records_for_date.return_value = [today_rec]

    handler = DomainHandler(sheets_service=mock_sheets, nutrition_service=nutrition_service)
    intent = ParsedIntent(intent=IntentType.TODAY, raw_text="/today")

    response_text = await handler.process_intent(intent, update_id=204)

    assert "Сводка за день" in response_text
    assert "450" in response_text
    assert "1550" in response_text  # 2000 - 450 = 1550 remaining


@pytest.mark.asyncio
async def test_handle_repeat_half_portion(mock_sheets):
    nutrition_service = NutritionService()
    payload = FoodPayload(
        items=[FoodItem(name="Курица", amount=200, unit="g", calories=220, protein=44, fat=4, carbs=0)],
        portion_multiplier=1.0,
    )
    last_rec = DiaryRecord(
        id="rec-last",
        telegram_update_id=195,
        real_time=datetime.now(timezone.utc),
        food_date=date(2026, 9, 18),
        name="Курица",
        calories=220,
        source="text",
        json_structure=payload.model_dump_json(),
    )
    mock_sheets.get_last_diary_record.return_value = last_rec

    handler = DomainHandler(sheets_service=mock_sheets, nutrition_service=nutrition_service)
    intent = ParsedIntent(
        intent=IntentType.REPEAT,
        raw_text="повтори половину",
        details={"portion_multiplier": 0.5},
    )

    response_text = await handler.process_intent(intent, update_id=205)

    assert "Повторен прием пищи" in response_text
    assert "110" in response_text  # 220 * 0.5 = 110
    assert mock_sheets.add_diary_record.called
    added: DiaryRecord = mock_sheets.add_diary_record.call_args[0][0]
    assert added.calories == 110


@pytest.mark.asyncio
async def test_callback_actions(mock_sheets):
    nutrition_service = NutritionService()
    handler = DomainHandler(sheets_service=mock_sheets, nutrition_service=nutrition_service)

    payload = FoodPayload(
        items=[FoodItem(name="Овсянка", amount=100, unit="g", calories=360, protein=12, fat=6, carbs=65)],
        portion_multiplier=1.0,
    )
    rec = DiaryRecord(
        id="rec-buttons-1",
        telegram_update_id=206,
        real_time=datetime.now(timezone.utc),
        food_date=date(2026, 9, 18),
        name="Овсянка",
        calories=360,
        protein=12,
        fat=6,
        carbs=65,
        source="text",
        json_structure=payload.model_dump_json(),
    )
    mock_sheets.get_diary_record_by_id = AsyncMock(return_value=(2, rec))
    mock_sheets.update_diary_record = AsyncMock(return_value=True)
    mock_sheets.add_template = AsyncMock()
    mock_sheets.get_settings = AsyncMock(return_value={"TARGET_CALORIES": 2000})
    mock_sheets.get_diary_records_for_date = AsyncMock(return_value=[rec])
    mock_sheets.get_state = AsyncMock(return_value=BotState())
    mock_sheets.set_state = AsyncMock()

    # 1. Test 50% button callback
    res_half = await handler.handle_callback_half("rec-buttons-1")
    assert "50%" in res_half
    assert "180" in res_half  # 360 / 2 = 180
    assert mock_sheets.update_diary_record.called

    # 2. Test Delete button callback
    res_del = await handler.handle_callback_delete("rec-buttons-1")
    assert "удалена" in res_del.lower() or "отменена" in res_del.lower()
    assert mock_sheets.delete_diary_record.called

    # 3. Test Template button callback
    res_tmpl = await handler.handle_callback_template("rec-buttons-1")
    assert "шаблон" in res_tmpl.lower()
    assert mock_sheets.add_template.called

    # 4. Test Edit button callback
    mock_sheets.get_state.return_value = BotState()
    mock_sheets.set_state = AsyncMock()
    res_edit = await handler.handle_callback_edit("rec-buttons-1")
    assert "исправ" in res_edit.lower()
    assert mock_sheets.set_state.called
    saved_state = mock_sheets.set_state.call_args[0][0]
    assert saved_state.pending_action == "EDIT_RECORD"
    assert saved_state.target_record_id == "rec-buttons-1"
