from typing import Optional
from pydantic import BaseModel


class ActivityItem(BaseModel):
    name: str
    duration_minutes: Optional[float] = None
    calories_burned: float
