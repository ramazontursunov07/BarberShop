"""Bo'sh vaqtlarni hisoblash (sof Python, Django'ga bog'liq emas).

Shu sababli uni modellarsiz ham test qilish mumkin.
"""
from datetime import date, datetime, time, timedelta
from typing import Iterable, Optional


def _combine(day: date, t: time) -> datetime:
    return datetime.combine(day, t)


def compute_slots(
        day: date,
        work_start: time,
        work_end: time,
        busy: Iterable[tuple[time, time]],
        duration_minutes: int,
        step_minutes: int = 30,
        now: Optional[datetime] = None,
) -> list[str]:
    """Berilgan kunda xizmat sig'adigan boshlanish vaqtlarini qaytaradi.

    busy: band oraliqlar [(boshlanish, tugash), ...]
    now:  berilsa, o'tib ketgan vaqtlar tashlab yuboriladi.
    """
    if duration_minutes <= 0 or step_minutes <= 0:
        return []

    start = _combine(day, work_start)
    end = _combine(day, work_end)
    duration = timedelta(minutes=duration_minutes)
    step = timedelta(minutes=step_minutes)
    busy_dt = [(_combine(day, s), _combine(day, e)) for s, e in busy]

    result: list[str] = []
    cur = start
    while cur + duration <= end:
        slot_end = cur + duration
        overlaps = any(cur < b_end and slot_end > b_start for b_start, b_end in busy_dt)
        in_past = now is not None and cur <= now
        if not overlaps and not in_past:
            result.append(cur.strftime("%H:%M"))
        cur += step
    return result
