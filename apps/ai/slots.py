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


# Kun bo'laklari: [boshi, oxiri). Mijoz "kechqurun" desa -> evening
PARTS_OF_DAY = {
    "morning": (time(5, 0), time(12, 0)),
    "afternoon": (time(12, 0), time(17, 0)),
    "evening": (time(17, 0), time(23, 59)),
}


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def rank_slots(
        candidates: Iterable[tuple[date, int, str]],
        window: Optional[tuple[time, time]] = None,
        preferred: Optional[time] = None,
        limit: int = 5,
) -> list[tuple[date, int, str]]:
    """Nomzod vaqtlarni saralab, eng mosini qaytaradi (sof Python, DB kerak emas).

    candidates: [(sana, usta_id, 'HH:MM'), ...]
    window:     (boshi, oxiri): faqat shu oraliqdagi boshlanish vaqtlari qoladi
    preferred:  istalgan vaqt; berilsa, unga eng yaqinlari birinchi chiqadi
    Tartib: avval eng yaqin sana, keyin istalgan vaqtga yaqinlik, keyin vaqt va usta.
    """
    lo = window[0].hour * 60 + window[0].minute if window else None
    hi = window[1].hour * 60 + window[1].minute if window else None
    pref = preferred.hour * 60 + preferred.minute if preferred else None

    def keep(item) -> bool:
        if window is None:
            return True
        m = _minutes(item[2])
        return lo <= m < hi

    def key(item):
        day, master_id, hhmm = item
        distance = abs(_minutes(hhmm) - pref) if pref is not None else 0
        return day, distance, _minutes(hhmm), master_id

    return sorted((c for c in candidates if keep(c)), key=key)[:max(limit, 0)]
