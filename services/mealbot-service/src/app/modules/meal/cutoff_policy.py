from __future__ import annotations

from datetime import date, datetime, time, timezone, timedelta

CST = timezone(timedelta(hours=8))

MEAL_CUTOFF: dict[str, time] = {
    "lunch": time(9, 30, tzinfo=CST),
    "dinner": time(15, 30, tzinfo=CST),
    "extra": time(16, 30, tzinfo=CST),
}


class CutoffError(ValueError):
    def __init__(self, meal_type: str, cutoff_at: time):
        self.meal_type = meal_type
        self.cutoff_at = cutoff_at
        self.code = "MEAL_CUTOFF_EXPIRED"
        super().__init__(f"meal cutoff expired for {meal_type}")


def check_meal_cutoff(meal_type: str, meal_date: date, *, now: datetime | None = None) -> None:
    if meal_type not in MEAL_CUTOFF:
        raise ValueError(f"INVALID_MEAL_TYPE: {meal_type}")

    cutoff_time = MEAL_CUTOFF[meal_type]
    now = now or datetime.now(CST)
    today = now.date()

    if meal_date < today:
        raise CutoffError(meal_type, cutoff_time)

    if meal_date == today:
        current_time = now.time().replace(tzinfo=CST)
        if current_time > cutoff_time:
            raise CutoffError(meal_type, cutoff_time)


def get_cutoff_time(meal_type: str) -> str:
    t = MEAL_CUTOFF.get(meal_type)
    if not t:
        return "unknown"
    return t.strftime("%H:%M")
