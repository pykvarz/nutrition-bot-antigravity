import pytest
from datetime import datetime, date, timezone, timedelta

from bot.models.diary import DiaryRecord
from bot.models.state import BotState
from bot.services.sheets_service import SheetsService


class MockWorksheet:
    def __init__(self, title: str, rows: list[list]):
        self.title = title
        self.rows = [list(r) for r in rows]

    def get_all_values(self):
        return [list(r) for r in self.rows]

    def append_row(self, row: list, **kwargs):
        self.rows.append(list(row))

    def update(self, values: list[list], range_name: str | None = None, **kwargs):
        self.rows = [list(r) for r in values]

    def delete_rows(self, row_index: int):
        if 1 <= row_index <= len(self.rows):
            self.rows.pop(row_index - 1)


class MockSpreadsheet:
    def __init__(self):
        self.sheets = {
            "Дневник": MockWorksheet("Дневник", [
                ["ID_записи", "Telegram_Update_ID", "Реальное_время", "Расчетная_дата",
                 "Что_съедено", "Ккал", "Б", "Ж", "У", "Источник", "Тип", "Структура_JSON",
                 "Оригинальный_текст", "Telegram_Message_ID", "Примечание"]
            ]),
            "Шаблоны": MockWorksheet("Шаблоны", [
                ["Название_блюда", "Калории", "Белки", "Жиры", "Углеводы", "Структура_JSON", "Примечание"]
            ]),
            "Рецепты": MockWorksheet("Рецепты", [
                ["ID_рецепта", "Название", "Дата_создания", "Количество_порций",
                 "Ккал_всего", "Белки_всего", "Жиры_всего", "Углеводы_всего",
                 "Ккал_на_порцию", "Белки_на_порцию", "Жиры_на_порцию", "Углеводы_на_порцию",
                 "Структура_JSON", "Примечание"]
            ]),
            "Настройки": MockWorksheet("Настройки", [
                ["Ключ", "Значение"],
                ["TARGET_CALORIES", "2000"],
                ["TARGET_PROTEIN", "150"],
                ["TARGET_FAT", "60"],
                ["TARGET_CARBS", "220"],
                ["TIMEZONE", "Asia/Almaty"],
                ["DAY_CUTOFF_HOUR", "4"],
            ]),
            "Состояние": MockWorksheet("Состояние", [
                ["Ключ", "Значение", "Updated_At"],
                ["pending_action", "", ""],
                ["target_record_id", "", ""],
                ["target_template_id", "", ""],
                ["target_recipe_id", "", ""],
                ["pending_payload", "", ""],
                ["last_processed_update_id", "100", "2026-09-18T10:00:00+00:00"],
            ]),
            "История_действий": MockWorksheet("История_действий", [
                ["ID_действия", "Время", "Тип_действия", "Entity_Type", "Entity_ID",
                 "Before_JSON", "After_JSON", "Undone"]
            ]),
        }

    def worksheet(self, title: str):
        if title not in self.sheets:
            raise ValueError(f"Sheet {title} not found")
        return self.sheets[title]


@pytest.fixture
def mock_sheets_service():
    mock_spreadsheet = MockSpreadsheet()
    service = SheetsService(spreadsheet=mock_spreadsheet)
    return service


@pytest.mark.asyncio
async def test_is_update_processed(mock_sheets_service):
    # Update 100 was recorded as last_processed_update_id
    assert await mock_sheets_service.is_update_processed(100) is True
    assert await mock_sheets_service.is_update_processed(101) is False


@pytest.mark.asyncio
async def test_add_and_get_diary_record(mock_sheets_service):
    record = DiaryRecord(
        id="rec-uuid-1",
        telegram_update_id=102,
        real_time=datetime(2026, 9, 18, 12, 0, 0),
        food_date=date(2026, 9, 18),
        name="Творог 200г",
        calories=240,
        protein=32,
        fat=10,
        carbs=6,
        source="text",
        record_type="food",
        json_structure="{}",
    )
    await mock_sheets_service.add_diary_record(record)

    last_record = await mock_sheets_service.get_last_diary_record()
    assert last_record is not None
    assert last_record.id == "rec-uuid-1"
    assert last_record.calories == 240
    assert last_record.name == "Творог 200г"


@pytest.mark.asyncio
async def test_get_diary_records_for_date(mock_sheets_service):
    rec1 = DiaryRecord(
        id="rec-1",
        telegram_update_id=103,
        real_time=datetime(2026, 9, 18, 10, 0),
        food_date=date(2026, 9, 18),
        name="Обед",
        calories=500,
        source="text",
        json_structure="{}",
    )
    rec2 = DiaryRecord(
        id="rec-2",
        telegram_update_id=104,
        real_time=datetime(2026, 9, 17, 20, 0),
        food_date=date(2026, 9, 17),
        name="Вчерашний ужин",
        calories=400,
        source="text",
        json_structure="{}",
    )
    await mock_sheets_service.add_diary_record(rec1)
    await mock_sheets_service.add_diary_record(rec2)

    records_today = await mock_sheets_service.get_diary_records_for_date(date(2026, 9, 18))
    assert len(records_today) == 1
    assert records_today[0].id == "rec-1"


@pytest.mark.asyncio
async def test_get_and_set_state(mock_sheets_service):
    state = BotState(
        pending_action="awaiting_correction",
        target_record_id="rec-1",
        updated_at=datetime.now(timezone.utc),
    )
    await mock_sheets_service.set_state(state)
    retrieved = await mock_sheets_service.get_state()
    assert retrieved.pending_action == "awaiting_correction"
    assert retrieved.target_record_id == "rec-1"


@pytest.mark.asyncio
async def test_delete_diary_record(mock_sheets_service):
    rec = DiaryRecord(
        id="to-delete-123",
        telegram_update_id=105,
        real_time=datetime(2026, 9, 18, 11, 0),
        food_date=date(2026, 9, 18),
        name="Банан",
        calories=90,
        source="text",
        json_structure="{}",
    )
    await mock_sheets_service.add_diary_record(rec)
    found = await mock_sheets_service.get_diary_record_by_id("to-delete-123")
    assert found is not None

    deleted = await mock_sheets_service.delete_diary_record("to-delete-123")
    assert deleted is True

    found_after = await mock_sheets_service.get_diary_record_by_id("to-delete-123")
    assert found_after is None


@pytest.mark.asyncio
async def test_log_action(mock_sheets_service):
    action_id = await mock_sheets_service.log_action(
        action_type="ADD_FOOD",
        entity_type="DiaryRecord",
        entity_id="rec-1",
        after_json='{"name": "Обед"}',
    )
    assert action_id is not None
    assert len(action_id) > 10


@pytest.mark.asyncio
async def test_get_settings(mock_sheets_service):
    settings = await mock_sheets_service.get_settings()
    assert settings["TARGET_CALORIES"] == 2000.0
    assert settings["TIMEZONE"] == "Asia/Almaty"
    assert settings["DAY_CUTOFF_HOUR"] == 4


@pytest.mark.asyncio
async def test_state_ttl_auto_clear(mock_sheets_service):
    old_time = datetime.now(timezone.utc) - timedelta(minutes=35)
    state = BotState(
        pending_action="EDIT_RECORD",
        target_record_id="rec-old-1",
        last_processed_update_id=555,
        updated_at=old_time,
    )
    await mock_sheets_service.set_state(state)

    active_state = await mock_sheets_service.get_state()
    assert active_state.pending_action is None
    assert active_state.target_record_id is None
    assert active_state.last_processed_update_id == 555


@pytest.mark.asyncio
async def test_clear_state_explicit(mock_sheets_service):
    state = BotState(
        pending_action="EDIT_RECORD",
        target_record_id="rec-1",
        last_processed_update_id=556,
        updated_at=datetime.now(timezone.utc),
    )
    await mock_sheets_service.set_state(state)
    await mock_sheets_service.clear_state()

    current_state = await mock_sheets_service.get_state()
    assert current_state.pending_action is None
    assert current_state.last_processed_update_id == 556


@pytest.mark.asyncio
async def test_update_settings_allowed_and_disallowed(mock_sheets_service):
    updated = await mock_sheets_service.update_settings({
        "TARGET_CALORIES": 1850.0,
        "TIMEZONE": "Europe/Moscow",
    })
    assert updated["TARGET_CALORIES"] == 1850.0
    assert updated["TIMEZONE"] == "Asia/Almaty"
