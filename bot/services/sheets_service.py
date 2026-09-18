import asyncio
from datetime import datetime, date, timezone
from typing import Optional, List, Dict, Any, Tuple
import json
import uuid
import os

from bot.models.diary import DiaryRecord
from bot.models.state import BotState


def _safe_float(val: Any, default: float = 0.0) -> float:
    if val is None or val == "":
        return default
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return default


class SheetsService:
    def __init__(
        self,
        spreadsheet: Any = None,
        credentials_json: Optional[str] = None,
        credentials_file: Optional[str] = None,
        spreadsheet_id: Optional[str] = None,
    ):
        self._spreadsheet = spreadsheet
        self._credentials_json = credentials_json
        self._credentials_file = credentials_file
        self._spreadsheet_id = spreadsheet_id

    def _get_spreadsheet(self):
        if self._spreadsheet is not None:
            return self._spreadsheet

        # Lazy initialization for gspread
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]

        cred_file = self._credentials_file or os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
        cred_json_str = self._credentials_json or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

        if cred_file and os.path.exists(cred_file):
            creds = Credentials.from_service_account_file(cred_file, scopes=scopes)
        elif cred_json_str:
            cred_dict = json.loads(cred_json_str)
            creds = Credentials.from_service_account_info(cred_dict, scopes=scopes)
        else:
            raise ValueError(
                "Google Service Account credentials not provided! "
                "Set GOOGLE_SERVICE_ACCOUNT_FILE or GOOGLE_SERVICE_ACCOUNT_JSON."
            )

        client = gspread.authorize(creds)
        sheet_id = self._spreadsheet_id or os.getenv("SPREADSHEET_ID")
        if not sheet_id:
            raise ValueError("SPREADSHEET_ID is not set in environment or constructor.")

        self._spreadsheet = client.open_by_key(sheet_id)
        return self._spreadsheet

    # -------------------------------------------------------------
    # 1. State & Idempotency ("Состояние")
    # -------------------------------------------------------------
    async def get_state(self) -> BotState:
        return await asyncio.to_thread(self._sync_get_state)

    def _sync_get_state(self) -> BotState:
        ws = self._get_spreadsheet().worksheet("Состояние")
        rows = ws.get_all_values()
        return BotState.from_kv_rows(rows[1:] if len(rows) > 1 else [])

    async def set_state(self, state: BotState) -> None:
        await asyncio.to_thread(self._sync_set_state, state)

    def _sync_set_state(self, state: BotState) -> None:
        ws = self._get_spreadsheet().worksheet("Состояние")
        rows = [["Ключ", "Значение", "Updated_At"]] + state.to_kv_rows()
        ws.update(rows)

    async def is_update_processed(self, update_id: int) -> bool:
        """
        Проверяет, был ли данный update_id уже обработан (защита от дубликатов).
        """
        return await asyncio.to_thread(self._sync_is_update_processed, update_id)

    def _sync_is_update_processed(self, update_id: int) -> bool:
        # Проверяем last_processed_update_id в Состоянии
        state = self._sync_get_state()
        if state.last_processed_update_id == update_id:
            return True

        # Также проверяем колонку Telegram_Update_ID в Дневнике (колонка index 1)
        ws_diary = self._get_spreadsheet().worksheet("Дневник")
        diary_rows = ws_diary.get_all_values()
        for row in reversed(diary_rows[1:]):
            if len(row) > 1 and row[1] == str(update_id):
                return True
        return False

    async def mark_update_processed(self, update_id: int) -> None:
        await asyncio.to_thread(self._sync_mark_update_processed, update_id)

    def _sync_mark_update_processed(self, update_id: int) -> None:
        state = self._sync_get_state()
        state.last_processed_update_id = update_id
        state.updated_at = datetime.now(timezone.utc)
        self._sync_set_state(state)

    # -------------------------------------------------------------
    # 2. Дневник (Diary)
    # -------------------------------------------------------------
    async def add_diary_record(self, record: DiaryRecord) -> None:
        await asyncio.to_thread(self._sync_add_diary_record, record)

    def _sync_add_diary_record(self, record: DiaryRecord) -> None:
        ws = self._get_spreadsheet().worksheet("Дневник")
        ws.append_row(record.to_sheet_row())

    async def get_last_diary_record(self) -> Optional[DiaryRecord]:
        return await asyncio.to_thread(self._sync_get_last_diary_record)

    def _sync_get_last_diary_record(self) -> Optional[DiaryRecord]:
        ws = self._get_spreadsheet().worksheet("Дневник")
        rows = ws.get_all_values()
        if len(rows) <= 1:
            return None
        last_row = rows[-1]
        return DiaryRecord.from_sheet_row(last_row)

    async def get_diary_record_by_id(self, record_id: str) -> Optional[Tuple[int, DiaryRecord]]:
        """
        Возвращает кортеж (номер_строки_1_based, DiaryRecord) или None.
        """
        return await asyncio.to_thread(self._sync_get_diary_record_by_id, record_id)

    def _sync_get_diary_record_by_id(self, record_id: str) -> Optional[Tuple[int, DiaryRecord]]:
        ws = self._get_spreadsheet().worksheet("Дневник")
        rows = ws.get_all_values()
        for idx, row in enumerate(rows[1:], start=2):
            if row and row[0] == record_id:
                return idx, DiaryRecord.from_sheet_row(row)
        return None

    async def get_diary_records_for_date(self, target_date: date) -> List[DiaryRecord]:
        return await asyncio.to_thread(self._sync_get_diary_records_for_date, target_date)

    def _sync_get_diary_records_for_date(self, target_date: date) -> List[DiaryRecord]:
        ws = self._get_spreadsheet().worksheet("Дневник")
        rows = ws.get_all_values()
        target_str = target_date.isoformat()
        records = []
        for row in rows[1:]:
            if len(row) > 3 and row[3] == target_str:
                records.append(DiaryRecord.from_sheet_row(row))
        return records

    async def delete_diary_record(self, record_id: str) -> bool:
        return await asyncio.to_thread(self._sync_delete_diary_record, record_id)

    def _sync_delete_diary_record(self, record_id: str) -> bool:
        found = self._sync_get_diary_record_by_id(record_id)
        if not found:
            return False
        row_idx, _ = found
        ws = self._get_spreadsheet().worksheet("Дневник")
        ws.delete_rows(row_idx)
        return True

    async def update_diary_record(self, record: DiaryRecord) -> bool:
        return await asyncio.to_thread(self._sync_update_diary_record, record)

    def _sync_update_diary_record(self, record: DiaryRecord) -> bool:
        found = self._sync_get_diary_record_by_id(record.id)
        if not found:
            return False
        row_idx, _ = found
        ws = self._get_spreadsheet().worksheet("Дневник")
        ws.update([record.to_sheet_row()], f"A{row_idx}:O{row_idx}")
        return True

    # -------------------------------------------------------------
    # 3. Настройки (Settings)
    # -------------------------------------------------------------
    async def get_settings(self) -> Dict[str, Any]:
        return await asyncio.to_thread(self._sync_get_settings)

    def _sync_get_settings(self) -> Dict[str, Any]:
        ws = self._get_spreadsheet().worksheet("Настройки")
        rows = ws.get_all_values()
        settings: Dict[str, Any] = {
            "TARGET_CALORIES": 2000.0,
            "TARGET_PROTEIN": 140.0,
            "TARGET_FAT": 60.0,
            "TARGET_CARBS": 220.0,
            "TIMEZONE": "Asia/Almaty",
            "DAY_CUTOFF_HOUR": 4,
        }
        for row in rows[1:]:
            if len(row) >= 2 and row[0]:
                k = row[0].strip()
                v = str(row[1]).strip().replace(",", ".")
                if k in ("TARGET_CALORIES", "TARGET_PROTEIN", "TARGET_FAT", "TARGET_CARBS"):
                    try:
                        settings[k] = float(v)
                    except ValueError:
                        pass
                elif k == "DAY_CUTOFF_HOUR":
                    try:
                        settings[k] = int(float(v))
                    except ValueError:
                        pass
                elif k == "TIMEZONE":
                    settings[k] = v
        return settings

    # -------------------------------------------------------------
    # 4. Шаблоны и Рецепты
    # -------------------------------------------------------------
    async def get_templates(self) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self._sync_get_templates)

    def _sync_get_templates(self) -> List[Dict[str, Any]]:
        ws = self._get_spreadsheet().worksheet("Шаблоны")
        rows = ws.get_all_values()
        # Columns: Название_блюда | Калории | Белки | Жиры | Углеводы | Структура_JSON | Примечание
        templates = []
        for row in rows[1:]:
            if row and row[0]:
                templates.append({
                    "name": row[0],
                    "calories": _safe_float(row[1] if len(row) > 1 else 0),
                    "protein": _safe_float(row[2] if len(row) > 2 else 0),
                    "fat": _safe_float(row[3] if len(row) > 3 else 0),
                    "carbs": _safe_float(row[4] if len(row) > 4 else 0),
                    "json_structure": row[5] if len(row) > 5 else "{}",
                    "notes": row[6] if len(row) > 6 else "",
                })
        return templates

    async def add_template(
        self,
        name: str,
        calories: float,
        protein: float,
        fat: float,
        carbs: float,
        json_structure: str,
        notes: str = "",
    ) -> None:
        await asyncio.to_thread(
            self._sync_add_template, name, calories, protein, fat, carbs, json_structure, notes
        )

    def _sync_add_template(
        self,
        name: str,
        calories: float,
        protein: float,
        fat: float,
        carbs: float,
        json_structure: str,
        notes: str = "",
    ) -> None:
        ws = self._get_spreadsheet().worksheet("Шаблоны")
        ws.append_row([name, calories, protein, fat, carbs, json_structure, notes])

    async def get_recipes(self) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self._sync_get_recipes)

    def _sync_get_recipes(self) -> List[Dict[str, Any]]:
        ws = self._get_spreadsheet().worksheet("Рецепты")
        rows = ws.get_all_values()
        # ID_рецепта | Название | Дата_создания | Количество_порций | Ккал_всего | Белки_всего | ...
        recipes = []
        for row in rows[1:]:
            if row and row[0]:
                recipes.append({
                    "id": row[0],
                    "name": row[1] if len(row) > 1 else "",
                    "created_at": row[2] if len(row) > 2 else "",
                    "portions": _safe_float(row[3] if len(row) > 3 else 1, default=1.0),
                    "calories_total": _safe_float(row[4] if len(row) > 4 else 0),
                    "calories_per_portion": _safe_float(row[8] if len(row) > 8 else 0),
                    "protein_per_portion": _safe_float(row[9] if len(row) > 9 else 0),
                    "fat_per_portion": _safe_float(row[10] if len(row) > 10 else 0),
                    "carbs_per_portion": _safe_float(row[11] if len(row) > 11 else 0),
                    "json_structure": row[12] if len(row) > 12 else "{}",
                })
        return recipes

    # -------------------------------------------------------------
    # 5. История действий & Undo
    # -------------------------------------------------------------
    async def log_action(
        self,
        action_type: str,
        entity_type: str,
        entity_id: str,
        before_json: Optional[str] = None,
        after_json: Optional[str] = None,
    ) -> str:
        return await asyncio.to_thread(
            self._sync_log_action, action_type, entity_type, entity_id, before_json, after_json
        )

    def _sync_log_action(
        self,
        action_type: str,
        entity_type: str,
        entity_id: str,
        before_json: Optional[str] = None,
        after_json: Optional[str] = None,
    ) -> str:
        ws = self._get_spreadsheet().worksheet("История_действий")
        action_id = str(uuid.uuid4())
        now_str = datetime.now(timezone.utc).isoformat()
        ws.append_row([
            action_id,
            now_str,
            action_type,
            entity_type,
            entity_id,
            before_json or "",
            after_json or "",
            "False",
        ])
        return action_id
