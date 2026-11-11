"""Talab prognozi: o'tgan haftalardagi bronlarga qarab qaysi kun/soatda nechta usta kerakligini aytadi.

compute_demand sof Python (DB kerak emas), demand_forecast esa uni ORM ma'lumoti bilan to'ldiradi.
Mantiq: har bir bron o'zi egallagan soatlarga (daqiqa hisobida) yoziladi; kun-soat bo'yicha haftalik o'rtacha
'band ustalar soni' chiqadi. Kerakli ustalar = ceil(band / TARGET_UTILIZATION).
"""
from collections import defaultdict
from datetime import datetime, timedelta
from math import ceil

from django.utils import timezone

from apps.bookings.models import Booking
from apps.bookings.services import SHOP_TZ
from apps.masters.models import WorkSchedule

TARGET_UTILIZATION = 0.8  # ustalarni 80% dan ortiq yuklamaslik
QUIET_UTILIZATION = 0.3  # shundan past bo'lsa, soat "bo'sh" hisoblanadi
MIN_BOOKINGS = 20  # bundan kam ma'lumot bilan prognoz ishonchsiz
WEEKDAYS = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]
SUGGESTED_DISCOUNT = 15


def compute_demand(intervals, masters_by_weekday, weeks: int) -> dict:
    """intervals: [(start_local, end_local)] naive/aware mahalliy vaqt; masters_by_weekday: {weekday: {hour: ustalar_soni}}."""
    busy = defaultdict(float)  # (weekday, hour) -> jami band daqiqalar
    for start, end in intervals:
        cur = start
        while cur < end:
            nxt = min(end, cur.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
            busy[(cur.weekday(), cur.hour)] += (nxt - cur).total_seconds() / 60
            cur = nxt

    days = []
    for wd in range(7):
        hours = masters_by_weekday.get(wd, {})
        if not hours:
            continue
        rows = []
        for hour in sorted(hours):
            avg_busy = busy[(wd, hour)] / 60 / weeks  # o'rtacha band ustalar soni shu soatda
            avail = hours[hour]
            rows.append({
                "hour": hour,
                "avg_busy_masters": round(avg_busy, 2),
                "available_masters": avail,
                "needed_masters": ceil(avg_busy / TARGET_UTILIZATION - 1e-9) if avg_busy > 0 else 0,
                "utilization": round(avg_busy / avail, 2) if avail else 0,
            })
        peak = max(rows, key=lambda r: r["avg_busy_masters"])
        days.append({
            "weekday": wd,
            "name": WEEKDAYS[wd],
            "hours": rows,
            "peak_hour": peak["hour"],
            "max_needed": max(r["needed_masters"] for r in rows),
            "max_available": max(r["available_masters"] for r in rows),
        })
    return {"days": days}


def _ranges(hours: list[int]) -> list[tuple[int, int]]:
    out, start, prev = [], None, None
    for h in sorted(hours):
        if start is None:
            start = prev = h
        elif h == prev + 1:
            prev = h
        else:
            out.append((start, prev + 1))
            start = prev = h
    if start is not None:
        out.append((start, prev + 1))
    return out


def recommendations(report: dict) -> dict:
    """Hisobdan egasiga tushunarli tavsiyalar: yetishmayotgan ustalar va chegirma uchun bo'sh soatlar."""
    staffing, discounts = [], []
    for d in report["days"]:
        short = [r["hour"] for r in d["hours"] if r["needed_masters"] > r["available_masters"]]
        for lo, hi in _ranges(short):
            need = max(r["needed_masters"] for r in d["hours"] if lo <= r["hour"] < hi)
            have = min(r["available_masters"] for r in d["hours"] if lo <= r["hour"] < hi)
            staffing.append(f"{d['name']} kuni {lo:02d}:00-{hi:02d}:00 da {need} ta usta kerak (hozir {have} ta)")
        quiet = [r["hour"] for r in d["hours"] if r["utilization"] < QUIET_UTILIZATION]
        for lo, hi in _ranges(quiet):
            discounts.append({
                "weekday": d["weekday"],
                "text": f"{d['name']} kuni {lo:02d}:00-{hi:02d}:00 bo'sh: {SUGGESTED_DISCOUNT}% chegirma taklif qiling",
                "start": f"{lo:02d}:00", "end": f"{hi:02d}:00", "percent": SUGGESTED_DISCOUNT,
            })
    return {"staffing": staffing, "discount_suggestions": discounts}


def demand_forecast(shop, weeks: int = 8, now=None) -> dict:
    weeks = max(1, min(int(weeks), 26))
    now = now or timezone.now()
    since = now - timedelta(weeks=weeks)
    bookings = Booking.objects.filter(
        master__shop=shop, start_time__gte=since, start_time__lt=now,
    ).exclude(status=Booking.Status.CANCELLED)
    intervals = [
        (b.start_time.astimezone(SHOP_TZ).replace(tzinfo=None), b.end_time.astimezone(SHOP_TZ).replace(tzinfo=None))
        for b in bookings.only("start_time", "end_time")
    ]

    masters_by_wd: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for sch in WorkSchedule.objects.filter(master__shop=shop, master__is_active=True):
        start = max(sch.start_time, shop.opens_at)
        end = min(sch.end_time, shop.closes_at)
        for h in range(start.hour, end.hour + (1 if end.minute else 0)):
            masters_by_wd[sch.weekday][h] += 1

    report = compute_demand(intervals, {k: dict(v) for k, v in masters_by_wd.items()}, weeks)
    report.update(recommendations(report))
    report.update({
        "shop": shop.name,
        "weeks": weeks,
        "bookings_used": len(intervals),
        "reliable": len(intervals) >= MIN_BOOKINGS,
    })
    if not report["reliable"]:
        report["note"] = f"Ma'lumot kam ({len(intervals)} ta bron): prognoz taxminiy. Kamida {MIN_BOOKINGS} ta bron kerak."
    return report
