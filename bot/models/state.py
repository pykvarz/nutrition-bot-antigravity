from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import json
from pydantic import BaseModel, Field


class BotState(BaseModel):
    pending_action: Optional[str] = None
    target_record_id: Optional[str] = None
    target_template_id: Optional[str] = None
    target_recipe_id: Optional[str] = None
    pending_payload: Optional[Dict[str, Any]] = None
    last_processed_update_id: Optional[int] = None
    updated_at: Optional[datetime] = None

    def is_expired(self, ttl_minutes: int = 30) -> bool:
        """
        Проверяет, истек ли срок действия состояния (TTL 30 минут по умолчанию).
        """
        if not self.updated_at or not self.pending_action:
            return True
        now = datetime.now(timezone.utc)
        upd = self.updated_at
        if upd.tzinfo is None:
            upd = upd.replace(tzinfo=timezone.utc)
        return (now - upd) > timedelta(minutes=ttl_minutes)

    def to_kv_rows(self) -> list[list[Any]]:
        """
        Преобразует состояние в строки Ключ | Значение | Updated_At для листа 'Состояние'.
        """
        now_str = (self.updated_at or datetime.now(timezone.utc)).isoformat()
        payload_str = json.dumps(self.pending_payload) if self.pending_payload else ""
        return [
            ["pending_action", self.pending_action or "", now_str],
            ["target_record_id", self.target_record_id or "", now_str],
            ["target_template_id", self.target_template_id or "", now_str],
            ["target_recipe_id", self.target_recipe_id or "", now_str],
            ["pending_payload", payload_str, now_str],
            ["last_processed_update_id", str(self.last_processed_update_id or ""), now_str],
        ]

    @classmethod
    def from_kv_rows(cls, rows: list[list[Any]]) -> "BotState":
        """
        Восстанавливает BotState из строк листа 'Состояние'.
        """
        data: Dict[str, Any] = {}
        updated_at_dt: Optional[datetime] = None

        for row in rows:
            if not row or len(row) < 2:
                continue
            k = str(row[0]).strip()
            v = row[1]
            if len(row) >= 3 and row[2]:
                try:
                    updated_at_dt = datetime.fromisoformat(str(row[2]))
                except (ValueError, TypeError):
                    pass

            if k == "pending_payload" and v:
                try:
                    data[k] = json.loads(str(v))
                except json.JSONDecodeError:
                    data[k] = None
            elif k == "last_processed_update_id" and v:
                try:
                    data[k] = int(v)
                except (ValueError, TypeError):
                    data[k] = None
            else:
                data[k] = str(v) if v else None

        if updated_at_dt:
            data["updated_at"] = updated_at_dt

        return cls(**data)
