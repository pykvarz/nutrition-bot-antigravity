import pytest
from unittest.mock import MagicMock

from bot.handlers.router import create_bot_router, get_food_actions_keyboard
from bot.handlers.domain import DomainHandler
from bot.services.gemini_service import GeminiService
from bot.services.groq_service import GroqService


def test_food_actions_keyboard():
    kb = get_food_actions_keyboard("rec-test-123")
    assert len(kb.inline_keyboard) == 2
    row1 = kb.inline_keyboard[0]
    row2 = kb.inline_keyboard[1]

    assert len(row1) == 2
    assert row1[0].text == "✏️ Исправить"
    assert row1[0].callback_data == "edit:rec-test-123"
    assert row1[1].text == "🍽 50%"
    assert row1[1].callback_data == "half:rec-test-123"

    assert len(row2) == 2
    assert row2[0].text == "🗑 Удалить"
    assert row2[0].callback_data == "del:rec-test-123"
    assert row2[1].text == "⭐ В шаблон"
    assert row2[1].callback_data == "tmpl:rec-test-123"


@pytest.mark.asyncio
async def test_router_creation():
    domain_handler = MagicMock(spec=DomainHandler)
    gemini_service = MagicMock(spec=GeminiService)
    groq_service = MagicMock(spec=GroqService)

    router = create_bot_router(
        domain_handler=domain_handler,
        gemini_service=gemini_service,
        groq_service=groq_service,
        allowed_user_id=12345,
    )
    assert router is not None
