"""Kassa va usta ulushi hisoboti: bajarilgan bronlar bo'yicha tushum, to'lov usullari, usta komissiyasi."""
import csv
import io
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from apps.bookings.models import Booking
from apps.bookings.services import SHOP_TZ, master_name
from apps.masters.models import Master


def payroll_report(shop, start: date, end: date) -> dict:
    """start..end (ikkalasi ham kiradi). Usta ulushi = tushum * commission_percent / 100."""
    a = datetime.combine(start, time.min, tzinfo=SHOP_TZ)
    b = datetime.combine(end + timedelta(days=1), time.min, tzinfo=SHOP_TZ)
    rows = Booking.objects.filter(master__shop=shop, status=Booking.Status.COMPLETED, start_time__gte=a, start_time__lt=b)
    per = defaultdict(lambda: {"bookings": 0, "revenue": 0, "cash": 0, "card": 0, "transfer": 0, "unspecified": 0})
    for r in rows.only("master_id", "price", "payment_method"):
        d = per[r.master_id]
        d["bookings"] += 1
        d["revenue"] += int(r.price)
        d[r.payment_method or "unspecified"] += int(r.price)
    masters = []
    for m in Master.objects.filter(shop=shop).select_related("user"):
        d = per.get(m.id)
        if d is None:
            continue
        pay = round(d["revenue"] * m.commission_percent / 100)
        masters.append({"master_id": m.id, "master": master_name(m), "commission_percent": m.commission_percent,
                        **d, "master_share": pay, "shop_share": d["revenue"] - pay})
    total = {k: sum(x[k] for x in masters) for k in
             ("bookings", "revenue", "cash", "card", "transfer", "unspecified", "master_share", "shop_share")}
    return {"from": start.isoformat(), "to": end.isoformat(), "masters": masters, "total": total}


def to_csv(report: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["usta", "bronlar", "tushum", "naqd", "karta", "otkazma", "korsatilmagan", "komissiya_%", "usta_ulushi", "shop_ulushi"])
    for m in report["masters"]:
        w.writerow([m["master"], m["bookings"], m["revenue"], m["cash"], m["card"], m["transfer"],
                    m["unspecified"], m["commission_percent"], m["master_share"], m["shop_share"]])
    t = report["total"]
    w.writerow(["JAMI", t["bookings"], t["revenue"], t["cash"], t["card"], t["transfer"], t["unspecified"], "",
                t["master_share"], t["shop_share"]])
    return buf.getvalue()


def master_earnings(master, start: date, end: date) -> dict:
    """Bitta usta uchun: tushum, ulush (commission_percent), to'lov usullari va kunlar kesimi."""
    a = datetime.combine(start, time.min, tzinfo=SHOP_TZ)
    b = datetime.combine(end + timedelta(days=1), time.min, tzinfo=SHOP_TZ)
    rows = Booking.objects.filter(master=master, status=Booking.Status.COMPLETED, start_time__gte=a, start_time__lt=b)
    total = {"bookings": 0, "revenue": 0, "cash": 0, "card": 0, "transfer": 0, "unspecified": 0}
    days: dict[str, dict] = {}
    for r in rows.only("start_time", "price", "payment_method"):
        price = int(r.price)
        total["bookings"] += 1
        total["revenue"] += price
        total[r.payment_method or "unspecified"] += price
        day = r.start_time.astimezone(SHOP_TZ).date().isoformat()
        d = days.setdefault(day, {"date": day, "bookings": 0, "revenue": 0})
        d["bookings"] += 1
        d["revenue"] += price
    share = round(total["revenue"] * master.commission_percent / 100)
    for d in days.values():
        d["master_share"] = round(d["revenue"] * master.commission_percent / 100)
    return {"from": start.isoformat(), "to": end.isoformat(), "commission_percent": master.commission_percent,
            **total, "master_share": share, "days": sorted(days.values(), key=lambda x: x["date"], reverse=True)}
