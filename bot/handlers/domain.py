from datetime import datetime, timezone
from typing import Optional, Any
import json
import uuid
import logging

from bot.models.intents import IntentType, ParsedIntent
from bot.models.food import FoodPayload
from bot.models.diary import DiaryRecord
from bot.services.sheets_service import SheetsService
from bot.services.nutrition_service import NutritionService
from bot.utils.dates import calculate_food_date

logger = logging.getLogger(__name__)


class DomainResult(str):
    record_id: Optional[str] = None

    def __new__(cls, content: str, record_id: Optional[str] = None):
        instance = super().__new__(cls, content)
        instance.record_id = record_id
        return instance


class DomainHandler:
    def __init__(
        self,
        sheets_service: SheetsService,
        nutrition_service: NutritionService,
    ):
        self.sheets_service = sheets_service
        self.nutrition_service = nutrition_service

    async def process_intent(
        self,
        intent: ParsedIntent,
        update_id: int,
        message_id: Optional[int] = None,
        source: str = "text",
    ) -> str:
        """
        Главная точка входа для обработки распознанного интента пользователя.
        """
        now = datetime.now(timezone.utc)
        settings = await self.sheets_service.get_settings()
        cutoff_hour = int(settings.get("DAY_CUTOFF_HOUR", 4))
        tz_name = settings.get("TIMEZONE", "Asia/Almaty")
        food_date = calculate_food_date(now, cutoff_hour=cutoff_hour, tz_name=tz_name)

        if intent.intent == IntentType.ADD_FOOD:
            return await self._handle_add_food(
                intent=intent,
                update_id=update_id,
                message_id=message_id,
                source=source,
                now=now,
                food_date=food_date,
            )

        elif intent.intent == IntentType.ADD_ACTIVITY:
            return await self._handle_add_activity(
                intent=intent,
                update_id=update_id,
                message_id=message_id,
                source=source,
                now=now,
                food_date=food_date,
            )

        elif intent.intent == IntentType.REPEAT:
            return await self._handle_repeat(
                intent=intent,
                update_id=update_id,
                message_id=message_id,
                now=now,
                food_date=food_date,
            )

        elif intent.intent == IntentType.UNDO:
            return await self._handle_undo()

        elif intent.intent == IntentType.TODAY:
            records = await self.sheets_service.get_diary_records_for_date(food_date)
            return self.nutrition_service.format_daily_summary(records, settings)

        elif intent.intent == IntentType.ADVICE:
            records = await self.sheets_service.get_diary_records_for_date(food_date)
            return self._generate_quick_advice(records, settings)

        elif intent.intent == IntentType.SETTINGS:
            updates = intent.details.get("settings_update")
            if updates and isinstance(updates, dict):
                before_json = json.dumps({k: settings.get(k) for k in updates if k in settings})
                new_settings = await self.sheets_service.update_settings(updates)
                await self.sheets_service.log_action(
                    action_type="UPDATE_SETTINGS",
                    entity_type="Settings",
                    entity_id="user_settings",
                    before_json=before_json,
                    after_json=json.dumps(updates),
                )
                return (
                    f"⚙️ <b>Цели обновлены:</b>\n"
                    f"🎯 Калории: {new_settings.get('TARGET_CALORIES', 2000):g} ккал\n"
                    f"🥩 Белки: {new_settings.get('TARGET_PROTEIN', 140):g} г\n"
                    f"🥑 Жиры: {new_settings.get('TARGET_FAT', 60):g} г\n"
                    f"🍞 Углеводы: {new_settings.get('TARGET_CARBS', 220):g} г\n"
                    f"⏰ Часовой пояс: {tz_name} (cutoff: {cutoff_hour}:00)"
                )
            return (
                f"⚙️ <b>Текущие настройки:</b>\n"
                f"🎯 Калории: {settings.get('TARGET_CALORIES', 2000):g} ккал\n"
                f"🥩 Белки: {settings.get('TARGET_PROTEIN', 140):g} г\n"
                f"🥑 Жиры: {settings.get('TARGET_FAT', 60):g} г\n"
                f"🍞 Углеводы: {settings.get('TARGET_CARBS', 220):g} г\n"
                f"⏰ Часовой пояс: {tz_name} (cutoff: {cutoff_hour}:00)"
            )

        else:
            return (
                "Не удалось точно понять запрос.\n"
                "Вы можете:\n"
                "• Написать, что съели (например: «300г курицы и 150г гречки»)\n"
                "• Отправить голосовое сообщение\n"
                "• Отправить фото еды\n"
                "• Записать тренировку («бег 30 минут»)\n"
                "• Запросить сводку командой /today"
            )

    async def _handle_add_food(
        self,
        intent: ParsedIntent,
        update_id: int,
        message_id: Optional[int],
        source: str,
        now: datetime,
        food_date: Any,
    ) -> str:
        if not intent.food_payload or not intent.food_payload.items:
            return "Не удалось определить блюда и КБЖУ. Пожалуйста, уточните или опишите подробнее."

        payload = intent.food_payload
        food_name = ", ".join(item.name for item in payload.effective_items)
        record = DiaryRecord(
            id=str(uuid.uuid4()),
            telegram_update_id=update_id,
            real_time=now,
            food_date=food_date,
            name=food_name,
            calories=payload.total_calories,
            protein=payload.total_protein,
            fat=payload.total_fat,
            carbs=payload.total_carbs,
            source=source,
            record_type="food",
            json_structure=payload.model_dump_json(),
            original_text=intent.raw_text,
            telegram_message_id=message_id,
        )
        await self.sheets_service.add_diary_record(record)
        await self.sheets_service.log_action(
            action_type="ADD_FOOD",
            entity_type="DiaryRecord",
            entity_id=record.id,
            after_json=record.json_structure,
        )
        today_records = await self.sheets_service.get_diary_records_for_date(food_date)
        today_cal = round(sum(r.calories for r in today_records if r.record_type == "food"), 1)
        settings = await self.sheets_service.get_settings()
        target_cal = settings.get("TARGET_CALORIES")

        summary = self.nutrition_service.format_food_summary(
            payload,
            today_calories=today_cal,
            target_calories=target_cal,
        )
        return DomainResult(summary, record_id=record.id)

    async def _handle_add_activity(
        self,
        intent: ParsedIntent,
        update_id: int,
        message_id: Optional[int],
        source: str,
        now: datetime,
        food_date: Any,
    ) -> str:
        if not intent.activity_item:
            return "Не удалось определить параметры активности. Укажите вид спорта и примерную длительность."

        activity = intent.activity_item
        record = DiaryRecord(
            id=str(uuid.uuid4()),
            telegram_update_id=update_id,
            real_time=now,
            food_date=food_date,
            name=activity.name,
            calories=activity.calories_burned,
            protein=0,
            fat=0,
            carbs=0,
            source=source,
            record_type="activity",
            json_structure=activity.model_dump_json(),
            original_text=intent.raw_text,
            telegram_message_id=message_id,
        )
        await self.sheets_service.add_diary_record(record)
        await self.sheets_service.log_action(
            action_type="ADD_ACTIVITY",
            entity_type="DiaryRecord",
            entity_id=record.id,
            after_json=record.json_structure,
        )
        dur = f" ({activity.duration_minutes:g} мин)" if activity.duration_minutes else ""
        return f"🏃 <b>Активность записана</b>:\n• {activity.name}{dur} — {activity.calories_burned:g} ккал"

    async def _handle_repeat(
        self,
        intent: ParsedIntent,
        update_id: int,
        message_id: Optional[int],
        now: datetime,
        food_date: Any,
    ) -> str:
        last_rec = await self.sheets_service.get_last_diary_record()
        if not last_rec or last_rec.record_type != "food":
            return "Нет предыдущих приемов пищи для повторения."

        try:
            data = json.loads(last_rec.json_structure)
            payload = FoodPayload.model_validate(data)
        except Exception:
            payload = FoodPayload(
                items=[],
                portion_multiplier=1.0,
            )

        multiplier = intent.details.get("portion_multiplier", 1.0)
        if multiplier != 1.0:
            payload = payload.scale(multiplier)

        new_record = DiaryRecord(
            id=str(uuid.uuid4()),
            telegram_update_id=update_id,
            real_time=now,
            food_date=food_date,
            name=last_rec.name,
            calories=payload.total_calories or last_rec.calories,
            protein=payload.total_protein or last_rec.protein,
            fat=payload.total_fat or last_rec.fat,
            carbs=payload.total_carbs or last_rec.carbs,
            source="repeat",
            record_type="food",
            json_structure=payload.model_dump_json(),
            original_text=intent.raw_text,
            telegram_message_id=message_id,
        )
        await self.sheets_service.add_diary_record(new_record)
        await self.sheets_service.log_action(
            action_type="REPEAT",
            entity_type="DiaryRecord",
            entity_id=new_record.id,
            after_json=new_record.json_structure,
        )
        today_records = await self.sheets_service.get_diary_records_for_date(food_date)
        today_cal = round(sum(r.calories for r in today_records if r.record_type == "food"), 1)
        settings = await self.sheets_service.get_settings()
        target_cal = settings.get("TARGET_CALORIES")

        summary = self.nutrition_service.format_food_summary(
            payload,
            today_calories=today_cal,
            target_calories=target_cal,
        )
        return DomainResult(
            summary.replace("Добавил 👍", "Повторен прием пищи 🔄"),
            record_id=new_record.id,
        )

    async def _handle_undo(self) -> str:
        action = await self.sheets_service.get_last_undoable_action()
        if not action:
            return "Нет действий для отмены."

        action_id = action["action_id"]
        action_type = action["action_type"]
        entity_id = action["entity_id"]
        before_json = action.get("before_json")

        if action_type in ("ADD_FOOD", "ADD_ACTIVITY", "REPEAT"):
            await self.sheets_service.delete_diary_record(entity_id)
            await self.sheets_service.mark_action_undone(action_id)
            return "↩️ <b>Действие отменено</b>: запись удалена из дневника."

        elif action_type == "DELETE":
            if before_json:
                restored_rec = DiaryRecord.model_validate_json(before_json)
                await self.sheets_service.add_diary_record(restored_rec)
                await self.sheets_service.mark_action_undone(action_id)
                return f"↩️ <b>Запись восстановлена</b>: {restored_rec.name} ({restored_rec.calories:g} ккал)"
            await self.sheets_service.mark_action_undone(action_id)
            return "↩️ Действие отменено."

        elif action_type == "SCALE_HALF":
            if before_json:
                restored_rec = DiaryRecord.model_validate_json(before_json)
                await self.sheets_service.update_diary_record(restored_rec)
                await self.sheets_service.mark_action_undone(action_id)
                return f"↩️ <b>Порция восстановлена</b>: {restored_rec.name} ({restored_rec.calories:g} ккал)"
            await self.sheets_service.mark_action_undone(action_id)
            return "↩️ Действие отменено."

        elif action_type == "UPDATE_SETTINGS":
            if before_json:
                prev_settings = json.loads(before_json)
                await self.sheets_service.update_settings(prev_settings)
                await self.sheets_service.mark_action_undone(action_id)
                return "↩️ <b>Настройки возвращены к предыдущим значениям.</b>"
            await self.sheets_service.mark_action_undone(action_id)
            return "↩️ Действие отменено."

        else:
            await self.sheets_service.mark_action_undone(action_id)
            return "↩️ Действие отменено."

    def _generate_quick_advice(self, records: list[DiaryRecord], targets: dict[str, Any]) -> str:
        food_recs = [r for r in records if r.record_type == "food"]
        tot_cal = sum(r.calories for r in food_recs)
        tot_p = sum(r.protein for r in food_recs)
        tgt_cal = targets.get("TARGET_CALORIES", 2000)
        tgt_p = targets.get("TARGET_PROTEIN", 140)

        rem_cal = tgt_cal - tot_cal
        rem_p = tgt_p - tot_p

        if rem_cal <= 0:
            return (
                f"⚠️ Лимит калорий на сегодня исчерпан ({tot_cal:g}/{tgt_cal:g} ккал). "
                f"Рекомендуется легкий травяной чай или вода."
            )
        elif rem_p > 30:
            return (
                f"💡 Осталось {rem_cal:g} ккал. Не хватает ещё {rem_p:g}г белка! "
                f"Отличный выбор на вечер: нежирный творог, куриная грудка или протеиновый коктейль."
            )
        else:
            return f"👍 Отличный баланс! Осталось {rem_cal:g} ккал и {max(0.0, rem_p):g}г белка."

    async def handle_callback_half(self, record_id: str) -> str:
        found = await self.sheets_service.get_diary_record_by_id(record_id)
        if not found:
            return "Запись не найдена в дневнике."
        _, rec = found
        try:
            data = json.loads(rec.json_structure)
            payload = FoodPayload.model_validate(data)
        except Exception:
            return "Не удалось прочитать состав порции для изменения."

        before_json = rec.model_dump_json()
        scaled = payload.scale(0.5)
        rec.calories = scaled.total_calories
        rec.protein = scaled.total_protein
        rec.fat = scaled.total_fat
        rec.carbs = scaled.total_carbs
        rec.json_structure = scaled.model_dump_json()

        await self.sheets_service.update_diary_record(rec)
        await self.sheets_service.log_action(
            action_type="SCALE_HALF",
            entity_type="DiaryRecord",
            entity_id=rec.id,
            before_json=before_json,
            after_json=rec.model_dump_json(),
        )

        settings = await self.sheets_service.get_settings()
        today_records = await self.sheets_service.get_diary_records_for_date(rec.food_date)
        today_cal = round(sum(r.calories for r in today_records if r.record_type == "food"), 1)
        target_cal = settings.get("TARGET_CALORIES")

        summary = self.nutrition_service.format_food_summary(
            scaled,
            today_calories=today_cal,
            target_calories=target_cal,
        )
        return summary.replace("Добавил 👍", "Порция уменьшена на 50% 🍽")

    async def handle_callback_delete(self, record_id: str) -> str:
        found = await self.sheets_service.get_diary_record_by_id(record_id)
        if not found:
            return "Запись не найдена или уже была удалена."
        _, rec = found
        before_json = rec.model_dump_json()
        await self.sheets_service.delete_diary_record(rec.id)
        await self.sheets_service.log_action(
            action_type="DELETE",
            entity_type="DiaryRecord",
            entity_id=rec.id,
            before_json=before_json,
        )
        return f"Запись удалена 🗑: {rec.name} ({rec.calories:g} ккал)"

    async def handle_callback_template(self, record_id: str) -> str:
        found = await self.sheets_service.get_diary_record_by_id(record_id)
        if not found:
            return "Запись не найдена."
        _, rec = found
        await self.sheets_service.add_template(
            name=rec.name,
            calories=rec.calories,
            protein=rec.protein,
            fat=rec.fat,
            carbs=rec.carbs,
            json_structure=rec.json_structure,
            notes=f"Сохранено из записи от {rec.food_date}",
        )
        await self.sheets_service.log_action(
            action_type="ADD_TEMPLATE",
            entity_type="Template",
            entity_id=rec.name,
            after_json=rec.json_structure,
        )
        return f"Блюдо «{rec.name}» сохранено в шаблоны ⭐ ({rec.calories:g} ккал)"

    async def handle_callback_edit(self, record_id: str) -> str:
        found = await self.sheets_service.get_diary_record_by_id(record_id)
        if not found:
            return "Запись не найдена."
        _, rec = found
        state = await self.sheets_service.get_state()
        state.pending_action = "EDIT_RECORD"
        state.target_record_id = rec.id
        state.updated_at = datetime.now(timezone.utc)
        await self.sheets_service.set_state(state)
        return (
            f"✏️ <b>Исправление записи:</b> «{rec.name}»\n"
            f"Напишите или надиктуйте голосом, что изменить (например: «курицы было 300 г»):"
        )
