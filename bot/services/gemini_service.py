import asyncio
import json
import logging
import os
from typing import Optional, Dict, Any, List

from bot.models.intents import IntentType, ParsedIntent
from bot.models.food import FoodItem, FoodPayload
from bot.models.activity import ActivityItem

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты персональный ассистент по питанию и учету КБЖУ.
Твоя задача — классифицировать намерение пользователя и извлечь структурированные данные.

Возможные интенты (intent):
- ADD_FOOD: запись съеденной еды/напитка (например: "съел 200г творога", "выпил латте", фото еды)
- ADD_ACTIVITY: запись физической активности (например: "пробежал 5км", "час силовой", "прошел 10000 шагов")
- REPEAT: повторить предыдущий прием пищи ("повтори обед", "то же самое", "съел то же что и вчера")
- UNDO: отмена последнего действия ("отмени", "удали последнюю запись", "ошибся")
- CREATE_TEMPLATE: сохранить шаблон/быстрое блюдо ("сохрани как шаблон: стандартный завтрак")
- USE_TEMPLATE: использовать шаблон ("съел стандартный завтрак")
- CREATE_RECIPE: создать новый сложный рецепт с ингредиентами
- ADD_RECIPE_PORTION: записать порцию готового рецепта ("съел 1 порцию плова")
- TODAY: запрос сводки за сегодня ("сколько калорий сегодня?", "/today", "что по белкам?")
- ADVICE: запрос совета ("что съесть на ужин?", "хватит ли белка?")
- CORRECTION: исправление предыдущей записи ("не 200г а 300г", "без масла")
- SETTINGS: изменение настроек или целей
- UNKNOWN: непонятный запрос

ОТВЕТ ДОЛЖЕН БЫТЬ СТРОГО В ФОРМАТЕ JSON:
{
  "intent": "ADD_FOOD",
  "confidence": 0.95,
  "items": [
    {
      "name": "Название продукта",
      "amount": 200.0,
      "unit": "g",
      "calories": 240.0,
      "protein": 32.0,
      "fat": 10.0,
      "carbs": 6.0
    }
  ],
  "portion_multiplier": 1.0,
  "activity": {
    "name": "Название активности",
    "duration_minutes": 45.0,
    "calories_burned": 300.0
  },
  "details": {}
}
Правила оценки КБЖУ:
- Если вес не указан явно, оценивай стандартную среднюю порцию
  (например, 1 яблоко ~ 150г, 1 яйцо ~ 55г, чашка кофе ~ 250мл).
- Если запрос не содержит еды (например, активность или сводка), items оставляй пустым списком [].
- Отвечай ТОЛЬКО чистым JSON без обратных кавычек и markdown.
"""


class GeminiService:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-3.5-flash-lite",
        fallback_models: Optional[List[str]] = None,
    ):
        self._api_key = api_key or os.getenv("GEMINI_API_KEY")
        self._model_name = model_name
        self._fallback_models = fallback_models or ["gemini-3.5-flash-lite", "gemini-3.5-flash"]
        self._client = None

    def _get_client(self):
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=self._api_key)
        return self._client

    async def _generate_content(
        self,
        prompt: str,
        image_bytes: Optional[bytes] = None,
        mime_type: Optional[str] = None,
    ) -> str:
        """
        Вызов API Gemini в отдельном потоке с fallback на резервные модели при 503/ошибках.
        """
        return await asyncio.to_thread(self._sync_generate_content, prompt, image_bytes, mime_type)

    def _sync_generate_content(
        self,
        prompt: str,
        image_bytes: Optional[bytes] = None,
        mime_type: Optional[str] = None,
    ) -> str:
        client = self._get_client()
        contents: List[Any] = []

        if image_bytes:
            from google.genai import types
            contents.append(
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=mime_type or "image/jpeg",
                )
            )

        contents.append(prompt)

        from google.genai import types
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.2,
            response_mime_type="application/json",
        )

        models_to_try = [self._model_name] + [m for m in self._fallback_models if m != self._model_name]
        last_exc = None
        for m in models_to_try:
            try:
                response = client.models.generate_content(
                    model=m,
                    contents=contents,
                    config=config,
                )
                return response.text or ""
            except Exception as e:
                logger.warning(f"Model {m} failed with error: {e}. Trying fallback...")
                last_exc = e

        if last_exc:
            raise last_exc
        return ""

    async def parse_text(
        self,
        user_text: str,
        context: Optional[Dict[str, Any]] = None,
        max_retries: int = 2,
    ) -> ParsedIntent:
        """
        Распознает намерение и извлекает данные из текста с авто-retry при поврежденном JSON.
        """
        prompt = f"Сообщение пользователя: {user_text}"
        if context:
            prompt += f"\nКонтекст сессии: {json.dumps(context, ensure_ascii=False)}"

        last_error = None
        for attempt in range(max_retries):
            try:
                raw_response = await self._generate_content(prompt)
                cleaned = raw_response.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                if cleaned.startswith("```"):
                    cleaned = cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                data = json.loads(cleaned.strip())
                return self._build_parsed_intent(data, raw_text=user_text)
            except Exception as e:
                logger.warning(f"Gemini parse attempt {attempt + 1} failed: {e}")
                last_error = e
                # Retry with an explicit correction request
                prompt = f"{prompt}\nВ прошлый раз ты вернул некорректный JSON. Верни строго валидный JSON."

        logger.error(f"Failed to parse text from Gemini after {max_retries} attempts: {last_error}")
        return ParsedIntent(
            intent=IntentType.UNKNOWN,
            raw_text=user_text,
            confidence=0.0,
            details={"error": str(last_error)},
        )

    async def parse_image(
        self,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        caption: Optional[str] = None,
        max_retries: int = 2,
    ) -> ParsedIntent:
        """
        Распознает еду на фото с опциональной подписью пользователя.
        """
        prompt = "Определи все продукты на этом фото, их примерный вес и КБЖУ."
        if caption:
            prompt += f"\nПодпись пользователя: {caption}"

        for attempt in range(max_retries):
            try:
                raw_response = await self._generate_content(prompt, image_bytes=image_bytes, mime_type=mime_type)
                cleaned = raw_response.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                if cleaned.startswith("```"):
                    cleaned = cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                data = json.loads(cleaned.strip())
                return self._build_parsed_intent(data, raw_text=caption or "[Фото]")
            except Exception as e:
                logger.warning(f"Gemini image parse attempt {attempt + 1} failed: {e}")

        return ParsedIntent(
            intent=IntentType.UNKNOWN,
            raw_text=caption or "[Фото]",
            confidence=0.0,
        )

    def _build_parsed_intent(self, data: Dict[str, Any], raw_text: str) -> ParsedIntent:
        raw_intent = data.get("intent", "UNKNOWN").upper()
        try:
            intent_type = IntentType(raw_intent)
        except ValueError:
            intent_type = IntentType.UNKNOWN

        food_payload = None
        if "items" in data and isinstance(data["items"], list) and len(data["items"]) > 0:
            items = []
            for it in data["items"]:
                items.append(
                    FoodItem(
                        name=it.get("name", "Продукт"),
                        amount=float(it.get("amount", 100)),
                        unit=it.get("unit", "g"),
                        calories=float(it.get("calories", 0)),
                        protein=float(it.get("protein", 0)),
                        fat=float(it.get("fat", 0)),
                        carbs=float(it.get("carbs", 0)),
                        source="gemini",
                    )
                )
            portion_multiplier = float(data.get("portion_multiplier", 1.0))
            food_payload = FoodPayload(items=items, portion_multiplier=portion_multiplier)

        activity_item = None
        if "activity" in data and isinstance(data["activity"], dict):
            act = data["activity"]
            activity_item = ActivityItem(
                name=act.get("name", "Активность"),
                duration_minutes=float(act.get("duration_minutes", 0)) if act.get("duration_minutes") else None,
                calories_burned=float(act.get("calories_burned", 0)),
            )

        return ParsedIntent(
            intent=intent_type,
            food_payload=food_payload,
            activity_item=activity_item,
            raw_text=raw_text,
            confidence=float(data.get("confidence", 1.0)),
            details=data.get("details", {}),
        )
