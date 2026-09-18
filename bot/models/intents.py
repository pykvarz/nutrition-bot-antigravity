from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from bot.models.food import FoodPayload
from bot.models.activity import ActivityItem


class IntentType(str, Enum):
    ADD_FOOD = "ADD_FOOD"
    ADD_ACTIVITY = "ADD_ACTIVITY"
    REPEAT = "REPEAT"
    UNDO = "UNDO"
    CREATE_TEMPLATE = "CREATE_TEMPLATE"
    USE_TEMPLATE = "USE_TEMPLATE"
    CREATE_RECIPE = "CREATE_RECIPE"
    ADD_RECIPE_PORTION = "ADD_RECIPE_PORTION"
    TODAY = "TODAY"
    ADVICE = "ADVICE"
    CORRECTION = "CORRECTION"
    SETTINGS = "SETTINGS"
    UNKNOWN = "UNKNOWN"


class ParsedIntent(BaseModel):
    intent: IntentType
    food_payload: Optional[FoodPayload] = None
    activity_item: Optional[ActivityItem] = None
    raw_text: str = ""
    confidence: float = 1.0
    details: Dict[str, Any] = Field(default_factory=dict)
