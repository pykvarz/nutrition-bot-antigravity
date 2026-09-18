from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "Asia/Almaty"
DEFAULT_CUTOFF_HOUR = 4


def calculate_food_date(
    dt: datetime | None = None,
    cutoff_hour: int = DEFAULT_CUTOFF_HOUR,
    tz_name: str = DEFAULT_TIMEZONE,
) -> date:
    """
    Рассчитывает расчетную дату питания (food_date) с учетом cutoff_hour и часового пояса.
    
    Если время меньше cutoff_hour (по умолчанию 04:00), запись относится
    к предыдущему календарному дню.
    """
    tz = ZoneInfo(tz_name)
    if dt is None:
        dt = datetime.now(tz)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    else:
        dt = dt.astimezone(tz)

    if dt.hour < cutoff_hour:
        return (dt - timedelta(days=1)).date()
    return dt.date()
