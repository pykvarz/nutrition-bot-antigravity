from typing import List, Dict, Optional
from bot.models.food import FoodItem, FoodPayload
from bot.models.diary import DiaryRecord


class NutritionService:
    def scale_item_by_amount(self, item: FoodItem, new_amount: float) -> FoodItem:
        """
        Пропорционально пересчитывает КБЖУ продукта при изменении веса/объема.
        """
        if item.amount <= 0:
            return item.model_copy(update={"amount": new_amount})

        ratio = new_amount / item.amount
        return FoodItem(
            id=item.id,
            name=item.name,
            amount=round(new_amount, 2),
            unit=item.unit,
            calories=round(item.calories * ratio, 2),
            protein=round(item.protein * ratio, 2),
            fat=round(item.fat * ratio, 2),
            carbs=round(item.carbs * ratio, 2),
            source=item.source,
        )

    def format_food_summary(self, payload: FoodPayload) -> str:
        """
        Форматирует структурированный прием пищи в красивое текстовое сообщение.
        """
        lines = []
        for item in payload.effective_items:
            lines.append(
                f"• {item.name} ({item.amount:g}{item.unit}) — {item.calories:g} ккал "
                f"(Б: {item.protein:g}, Ж: {item.fat:g}, У: {item.carbs:g})"
            )

        summary = "\n".join(lines)
        if len(payload.items) > 1 or payload.portion_multiplier != 1.0:
            summary += (
                f"\n\n<b>Итого</b>: {payload.total_calories:g} ккал "
                f"(Б: {payload.total_protein:g}, Ж: {payload.total_fat:g}, У: {payload.total_carbs:g})"
            )
            if payload.portion_multiplier != 1.0:
                summary += f" [порция: {payload.portion_multiplier:g}x]"

        return summary

    def format_daily_summary(
        self,
        records: List[DiaryRecord],
        targets: Optional[Dict[str, float]] = None,
    ) -> str:
        """
        Формирует сводку за день: съеденные калории, КБЖУ, цели и сожженную активность.
        Инвариант: калории активности НЕ вычитаются автоматически из съеденных, а показываются отдельно.
        """
        food_records = [r for r in records if r.record_type == "food"]
        activity_records = [r for r in records if r.record_type == "activity"]

        total_cal = round(sum(r.calories for r in food_records), 1)
        total_p = round(sum(r.protein for r in food_records), 1)
        total_f = round(sum(r.fat for r in food_records), 1)
        total_c = round(sum(r.carbs for r in food_records), 1)

        activity_cal = round(sum(r.calories for r in activity_records), 1)

        lines = ["📊 <b>Сводка за день</b>\n"]
        lines.append(f"🍽 <b>Съедено</b>: {total_cal:g} ккал (Б: {total_p:g}, Ж: {total_f:g}, У: {total_c:g})")

        if targets:
            tgt_cal = targets.get("TARGET_CALORIES", 0)
            tgt_p = targets.get("TARGET_PROTEIN", 0)
            tgt_f = targets.get("TARGET_FAT", 0)
            tgt_c = targets.get("TARGET_CARBS", 0)

            if tgt_cal > 0:
                rem_cal = round(tgt_cal - total_cal, 1)
                pct = round((total_cal / tgt_cal) * 100, 1)
                lines.append(f"🎯 <b>Цель</b>: {tgt_cal:g} ккал (прогресс: {pct}%, осталось: {rem_cal:g} ккал)")
                if tgt_p > 0 or tgt_f > 0 or tgt_c > 0:
                    lines.append(
                        f"🎯 <b>Цели КБЖУ</b>: Б: {tgt_p:g} (ост. {round(tgt_p - total_p, 1):g}), "
                        f"Ж: {tgt_f:g} (ост. {round(tgt_f - total_f, 1):g}), "
                        f"У: {tgt_c:g} (ост. {round(tgt_c - total_c, 1):g})"
                    )

        if activity_cal > 0 or activity_records:
            lines.append(f"\n🏃 <b>Активность</b> (сожжено): {activity_cal:g} ккал")
            for act in activity_records:
                lines.append(f"  • {act.name}: {act.calories:g} ккал")

        return "\n".join(lines)
