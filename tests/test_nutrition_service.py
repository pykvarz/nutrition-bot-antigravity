from datetime import datetime, date

from bot.models.food import FoodItem, FoodPayload
from bot.models.diary import DiaryRecord
from bot.services.nutrition_service import NutritionService


def test_scale_item_by_amount():
    service = NutritionService()
    item = FoodItem(
        name="Творог 5%",
        amount=200,
        unit="g",
        calories=242,
        protein=32,
        fat=10,
        carbs=6,
    )
    # Scaled from 200g to 300g (1.5x)
    scaled = service.scale_item_by_amount(item, 300)
    assert scaled.amount == 300
    assert scaled.calories == 363
    assert scaled.protein == 48
    assert scaled.fat == 15
    assert scaled.carbs == 9


def test_format_food_summary():
    service = NutritionService()
    payload = FoodPayload(
        items=[
            FoodItem(name="Куриное филе", amount=200, unit="g", calories=220, protein=46, fat=2.4, carbs=0),
            FoodItem(name="Гречка вареная", amount=150, unit="g", calories=150, protein=5.5, fat=1.5, carbs=30),
        ],
        portion_multiplier=1.0,
    )
    summary = service.format_food_summary(payload)
    assert "Куриное филе" in summary
    assert "Гречка вареная" in summary
    assert "370" in summary  # 220 + 150
    assert "51.5" in summary  # 46 + 5.5


def test_format_daily_summary():
    service = NutritionService()
    records = [
        DiaryRecord(
            id="1",
            telegram_update_id=1,
            real_time=datetime(2026, 9, 18, 10, 0),
            food_date=date(2026, 9, 18),
            name="Завтрак: Овсянка",
            calories=350,
            protein=12,
            fat=6,
            carbs=60,
            source="text",
            record_type="food",
            json_structure="{}",
        ),
        DiaryRecord(
            id="2",
            telegram_update_id=2,
            real_time=datetime(2026, 9, 18, 18, 0),
            food_date=date(2026, 9, 18),
            name="Бег 5 км",
            calories=300,
            source="text",
            record_type="activity",
            json_structure="{}",
        ),
    ]
    targets = {
        "TARGET_CALORIES": 2000,
        "TARGET_PROTEIN": 140,
        "TARGET_FAT": 60,
        "TARGET_CARBS": 220,
    }
    summary = service.format_daily_summary(records, targets)
    # Verify food calories: 350
    assert "350" in summary
    # Verify activity calories shown separately: 300
    assert "300" in summary
    assert "Активность" in summary or "активность" in summary.lower()
    # Verify remaining calories: 2000 - 350 = 1650
    assert "1650" in summary
