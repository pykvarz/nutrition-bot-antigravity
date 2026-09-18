from typing import List, Optional
import uuid
from pydantic import BaseModel, Field


class FoodItem(BaseModel):
    id: str = Field(default_factory=lambda: f"item_{uuid.uuid4().hex[:6]}")
    name: str
    amount: float
    unit: str = "g"
    calories: float
    protein: float
    fat: float
    carbs: float
    source: str = "gemini"


class FoodPayload(BaseModel):
    items: List[FoodItem] = Field(default_factory=list)
    portion_multiplier: float = 1.0
    repeated_from_record_id: Optional[str] = None

    @property
    def total_calories(self) -> float:
        return round(sum(item.calories for item in self.items) * self.portion_multiplier, 2)

    @property
    def total_protein(self) -> float:
        return round(sum(item.protein for item in self.items) * self.portion_multiplier, 2)

    @property
    def total_fat(self) -> float:
        return round(sum(item.fat for item in self.items) * self.portion_multiplier, 2)

    @property
    def total_carbs(self) -> float:
        return round(sum(item.carbs for item in self.items) * self.portion_multiplier, 2)

    @property
    def effective_items(self) -> List[FoodItem]:
        """
        Возвращает список элементов с весом и КБЖУ, умноженными на portion_multiplier.
        """
        return [
            FoodItem(
                id=item.id,
                name=item.name,
                amount=round(item.amount * self.portion_multiplier, 2),
                unit=item.unit,
                calories=round(item.calories * self.portion_multiplier, 2),
                protein=round(item.protein * self.portion_multiplier, 2),
                fat=round(item.fat * self.portion_multiplier, 2),
                carbs=round(item.carbs * self.portion_multiplier, 2),
                source=item.source,
            )
            for item in self.items
        ]

    def scale(self, multiplier: float) -> "FoodPayload":
        """
        Возвращает копию payload с обновленным portion_multiplier.
        """
        return FoodPayload(
            items=[item.model_copy() for item in self.items],
            portion_multiplier=round(self.portion_multiplier * multiplier, 4),
            repeated_from_record_id=self.repeated_from_record_id,
        )
