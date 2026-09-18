import os
import pytest
from unittest.mock import MagicMock, AsyncMock

from bot.main import create_app
from bot.models.state import BotState


@pytest.fixture
def mock_dependencies():
    sheets = MagicMock()
    sheets.is_update_processed = AsyncMock(return_value=False)
    sheets.mark_update_processed = AsyncMock()
    sheets.get_state = AsyncMock(return_value=BotState())
    sheets.get_settings = AsyncMock(return_value={
        "TARGET_CALORIES": 2000,
        "TIMEZONE": "Asia/Almaty",
        "DAY_CUTOFF_HOUR": 4,
    })
    sheets.get_diary_records_for_date = AsyncMock(return_value=[])
    sheets.has_food_record_in_last_hours = AsyncMock(return_value=False)
    sheets.has_recent_action = AsyncMock(return_value=False)
    sheets.log_action = AsyncMock()

    gemini = MagicMock()
    gemini.parse_text = AsyncMock()

    groq = MagicMock()
    groq.transcribe_audio = AsyncMock()

    bot = MagicMock()
    bot.send_message = AsyncMock()

    return {
        "sheets": sheets,
        "gemini": gemini,
        "groq": groq,
        "bot": bot,
    }


@pytest.mark.asyncio
async def test_healthcheck(aiohttp_client, mock_dependencies):
    app = create_app(
        sheets_service=mock_dependencies["sheets"],
        gemini_service=mock_dependencies["gemini"],
        groq_service=mock_dependencies["groq"],
        bot=mock_dependencies["bot"],
        webhook_secret="test_secret_123",
        allowed_user_id=12345,
    )
    client = await aiohttp_client(app)
    resp = await client.get("/health")
    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_webhook_invalid_secret_token(aiohttp_client, mock_dependencies):
    app = create_app(
        sheets_service=mock_dependencies["sheets"],
        gemini_service=mock_dependencies["gemini"],
        groq_service=mock_dependencies["groq"],
        bot=mock_dependencies["bot"],
        webhook_secret="correct_secret",
        allowed_user_id=12345,
    )
    client = await aiohttp_client(app)
    # Sending wrong header
    resp = await client.post(
        "/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong_secret"},
        json={"update_id": 999},
    )
    assert resp.status == 403


@pytest.mark.asyncio
async def test_webhook_idempotency_skip(aiohttp_client, mock_dependencies):
    # If update_id already processed, return 200 OK immediately without dispatching
    mock_dependencies["sheets"].is_update_processed.return_value = True

    app = create_app(
        sheets_service=mock_dependencies["sheets"],
        gemini_service=mock_dependencies["gemini"],
        groq_service=mock_dependencies["groq"],
        bot=mock_dependencies["bot"],
        webhook_secret="secret123",
        allowed_user_id=12345,
    )
    client = await aiohttp_client(app)
    resp = await client.post(
        "/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret123"},
        json={"update_id": 1234},
    )
    assert resp.status == 200
    data = await resp.json()
    assert data.get("ok") is True


@pytest.mark.asyncio
async def test_scheduler_jobs_execution(aiohttp_client, mock_dependencies):
    app = create_app(
        sheets_service=mock_dependencies["sheets"],
        gemini_service=mock_dependencies["gemini"],
        groq_service=mock_dependencies["groq"],
        bot=mock_dependencies["bot"],
        webhook_secret="secret123",
        allowed_user_id=12345,
    )
    client = await aiohttp_client(app)

    headers = {}
    sched_token = os.getenv("SCHEDULER_SECRET")
    if sched_token:
        headers["X-Scheduler-Token"] = sched_token

    # 1. Reminder job
    resp_rem = await client.post("/jobs/reminder", headers=headers)
    assert resp_rem.status == 200
    data_rem = await resp_rem.json()
    assert data_rem["status"] == "reminder_executed"
    assert mock_dependencies["bot"].send_message.called

    # 2. Daily report job
    resp_rep = await client.post("/jobs/daily-report", headers=headers)
    assert resp_rep.status == 200
    data_rep = await resp_rep.json()
    assert data_rep["status"] == "daily_report_executed"


@pytest.mark.asyncio
async def test_scheduler_reminder_skipped_when_recent_food(aiohttp_client, mock_dependencies):
    mock_dependencies["sheets"].has_food_record_in_last_hours.return_value = True

    app = create_app(
        sheets_service=mock_dependencies["sheets"],
        gemini_service=mock_dependencies["gemini"],
        groq_service=mock_dependencies["groq"],
        bot=mock_dependencies["bot"],
        webhook_secret="secret123",
        allowed_user_id=12345,
    )
    client = await aiohttp_client(app)

    headers = {}
    sched_token = os.getenv("SCHEDULER_SECRET")
    if sched_token:
        headers["X-Scheduler-Token"] = sched_token

    resp = await client.post("/jobs/reminder", headers=headers)
    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "skipped"
    assert data["reason"] == "recent_food"
    assert not mock_dependencies["bot"].send_message.called
