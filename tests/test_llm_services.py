import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from bot.models.intents import IntentType, ParsedIntent
from bot.models.food import FoodPayload, FoodItem
from bot.services.gemini_service import GeminiService
from bot.services.groq_service import GroqService


@pytest.fixture
def mock_gemini_client():
    client = MagicMock()
    return client


@pytest.mark.asyncio
async def test_gemini_parse_text_food_intent():
    # Mocking Gemini client response returning structured JSON
    fake_json = """{
        "intent": "ADD_FOOD",
        "confidence": 0.98,
        "items": [
            {
                "name": "Куриная грудка",
                "amount": 300,
                "unit": "g",
                "calories": 495,
                "protein": 93,
                "fat": 10.8,
                "carbs": 0
            }
        ],
        "portion_multiplier": 1.0
    }"""
    mock_response = MagicMock()
    mock_response.text = fake_json

    service = GeminiService(api_key="test-api-key")
    with patch.object(service, "_generate_content", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = fake_json
        parsed = await service.parse_text("Съел 300г куриной грудки")

    assert parsed.intent == IntentType.ADD_FOOD
    assert parsed.food_payload is not None
    assert len(parsed.food_payload.items) == 1
    assert parsed.food_payload.items[0].name == "Куриная грудка"
    assert parsed.food_payload.items[0].calories == 495


@pytest.mark.asyncio
async def test_gemini_parse_text_activity_intent():
    fake_json = """{
        "intent": "ADD_ACTIVITY",
        "confidence": 0.95,
        "activity": {
            "name": "Силовая тренировка",
            "duration_minutes": 60,
            "calories_burned": 450
        }
    }"""
    service = GeminiService(api_key="test-api-key")
    with patch.object(service, "_generate_content", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = fake_json
        parsed = await service.parse_text("Час силовой тренировки")

    assert parsed.intent == IntentType.ADD_ACTIVITY
    assert parsed.activity_item is not None
    assert parsed.activity_item.name == "Силовая тренировка"
    assert parsed.activity_item.calories_burned == 450


@pytest.mark.asyncio
async def test_gemini_retry_on_malformed_json():
    # First call returns invalid JSON, second call returns valid JSON
    valid_json = """{
        "intent": "TODAY",
        "confidence": 1.0
    }"""
    service = GeminiService(api_key="test-api-key")
    with patch.object(service, "_generate_content", new_callable=AsyncMock) as mock_gen:
        mock_gen.side_effect = ["Invalid json string", valid_json]
        parsed = await service.parse_text("Сколько сегодня съел?")

    assert parsed.intent == IntentType.TODAY
    assert mock_gen.call_count == 2


@pytest.mark.asyncio
async def test_groq_transcribe_audio():
    service = GroqService(api_key="test-groq-key")
    with patch.object(service, "_sync_transcribe", return_value="Съел банан и яблоко") as mock_sync:
        text = await service.transcribe_audio(b"fake_audio_bytes")
        assert text == "Съел банан и яблоко"
