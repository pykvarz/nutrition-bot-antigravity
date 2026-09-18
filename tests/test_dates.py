from datetime import datetime, date
from zoneinfo import ZoneInfo
import pytest

from bot.utils.dates import calculate_food_date


def test_food_date_after_cutoff_same_day():
    # 2026-09-18 at 12:00 (after 04:00 cutoff) in Asia/Almaty
    tz = ZoneInfo("Asia/Almaty")
    dt = datetime(2026, 9, 18, 12, 0, 0, tzinfo=tz)
    res = calculate_food_date(dt, cutoff_hour=4)
    assert res == date(2026, 9, 18)


def test_food_date_before_cutoff_previous_day():
    # 2026-09-18 at 02:30 (before 04:00 cutoff) in Asia/Almaty -> belongs to 2026-09-17
    tz = ZoneInfo("Asia/Almaty")
    dt = datetime(2026, 9, 18, 2, 30, 0, tzinfo=tz)
    res = calculate_food_date(dt, cutoff_hour=4)
    assert res == date(2026, 9, 17)


def test_food_date_exact_cutoff():
    # 2026-09-18 at 04:00:00 -> exactly cutoff -> current day
    tz = ZoneInfo("Asia/Almaty")
    dt = datetime(2026, 9, 18, 4, 0, 0, tzinfo=tz)
    assert calculate_food_date(dt, cutoff_hour=4) == date(2026, 9, 18)


def test_food_date_just_before_cutoff():
    # 2026-09-18 at 03:59:59 -> previous day
    tz = ZoneInfo("Asia/Almaty")
    dt = datetime(2026, 9, 18, 3, 59, 59, tzinfo=tz)
    assert calculate_food_date(dt, cutoff_hour=4) == date(2026, 9, 17)


def test_food_date_utc_conversion():
    # 2026-09-18 at 22:30 UTC = 2026-09-19 03:30 in Asia/Almaty (UTC+5)
    # Since 03:30 < 04:00, food date in Almaty is 2026-09-18
    dt_utc = datetime(2026, 9, 18, 22, 30, 0, tzinfo=ZoneInfo("UTC"))
    res = calculate_food_date(dt_utc, cutoff_hour=4, tz_name="Asia/Almaty")
    assert res == date(2026, 9, 18)


def test_food_date_defaults():
    # Default cutoff_hour should be 4, default timezone Asia/Almaty
    # If dt is naive, it assumes the default timezone
    dt = datetime(2026, 9, 18, 10, 0, 0)
    assert calculate_food_date(dt) == date(2026, 9, 18)

    dt_night = datetime(2026, 9, 18, 1, 0, 0)
    assert calculate_food_date(dt_night) == date(2026, 9, 17)
