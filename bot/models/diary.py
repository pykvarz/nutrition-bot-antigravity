from datetime import datetime, date
from typing import Optional, List, Any
import uuid
from pydantic import BaseModel, Field


class DiaryRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    telegram_update_id: int
    real_time: datetime
    food_date: date
    name: str
    calories: float
    protein: float = 0.0
    fat: float = 0.0
    carbs: float = 0.0
    source: str
    record_type: str = "food"  # food | activity
    json_structure: str
    original_text: Optional[str] = None
    telegram_message_id: Optional[int] = None
    notes: Optional[str] = None

    def to_sheet_row(self) -> List[Any]:
        """
        Преобразует модель в строку для Google Sheets (лист Дневник).
        Порядок: ID_записи, Telegram_Update_ID, Реальное_время, Расчетная_дата,
        Что_съедено, Ккал, Б, Ж, У, Источник, Тип, Структура_JSON,
        Оригинальный_текст, Telegram_Message_ID, Примечание.
        """
        return [
            self.id,
            self.telegram_update_id,
            self.real_time.isoformat(),
            self.food_date.isoformat(),
            self.name,
            self.calories,
            self.protein,
            self.fat,
            self.carbs,
            self.source,
            self.record_type,
            self.json_structure,
            self.original_text or "",
            self.telegram_message_id if self.telegram_message_id is not None else "",
            self.notes or "",
        ]

    @classmethod
    def from_sheet_row(cls, row: List[Any]) -> "DiaryRecord":
        """
        Восстанавливает модель из строки Google Sheets.
        """
        def get_val(index: int, default: Any = ""):
            return row[index] if index < len(row) else default

        def parse_float(val: Any) -> float:
            if val is None or val == "":
                return 0.0
            if isinstance(val, (int, float)):
                return float(val)
            s = str(val).strip().replace(",", ".")
            try:
                return float(s)
            except ValueError:
                return 0.0

        real_time_val = get_val(2)
        if isinstance(real_time_val, str):
            real_time = datetime.fromisoformat(real_time_val)
        else:
            real_time = real_time_val

        food_date_val = get_val(3)
        if isinstance(food_date_val, str):
            food_date = date.fromisoformat(food_date_val)
        else:
            food_date = food_date_val

        msg_id_val = get_val(13)
        msg_id = int(msg_id_val) if msg_id_val != "" and msg_id_val is not None else None

        return cls(
            id=str(get_val(0)),
            telegram_update_id=int(get_val(1)),
            real_time=real_time,
            food_date=food_date,
            name=str(get_val(4)),
            calories=parse_float(get_val(5)),
            protein=parse_float(get_val(6)),
            fat=parse_float(get_val(7)),
            carbs=parse_float(get_val(8)),
            source=str(get_val(9)),
            record_type=str(get_val(10) or "food"),
            json_structure=str(get_val(11)),
            original_text=str(get_val(12)) if get_val(12) else None,
            telegram_message_id=msg_id,
            notes=str(get_val(14)) if get_val(14) else None,
        )
