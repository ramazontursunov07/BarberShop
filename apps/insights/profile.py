"""Mijoz profili va shaxsiy tavsiya: tarixiga qarab usta va xizmat ("O'tgan safar fade qildirgansiz...")."""
from collections import Counter
from datetime import timedelta

from django.utils import timezone

from apps.bookings.models import Booking
from apps.bookings.services import SHOP_TZ, master_name


def client_profile(user, now=None) -> dict:
    now = now or timezone.now()
    done = list(
        Booking.objects.filter(client=user, status=Booking.Status.COMPLETED)
        .select_related("master__user", "master__shop", "service")
        .order_by("-start_time")[:30]
    )
    if not done:
        return {"visits": 0, "message": "Mijozning bajarilgan bronlari yo'q: tavsiya uchun tarix yo'q"}

    last = done[0]
    masters = Counter(b.master_id for b in done)
    services = Counter(b.service_id for b in done)
    fav_master_id, fav_master_n = masters.most_common(1)[0]
    fav_service_id, fav_service_n = services.most_common(1)[0]
    fav_master = next(b.master for b in done if b.master_id == fav_master_id)
    fav_service = next(b.service for b in done if b.service_id == fav_service_id)

    starts = sorted(b.start_time for b in done)
    gaps = [(b - a).days for a, b in zip(starts, starts[1:])]
    typical = sorted(gaps)[len(gaps) // 2] if gaps else None
    days_since = (now - last.start_time).days

    profile = {
        "visits": len(done),
        "last_visit": {
            "date": last.start_time.astimezone(SHOP_TZ).strftime("%Y-%m-%d"),
            "days_ago": days_since,
            "shop_id": last.master.shop_id,
            "service_id": last.service_id,
            "service": last.service.name,
            "master_id": last.master_id,
            "master": master_name(last.master),
        },
        "favorite_master": {"id": fav_master.id, "name": master_name(fav_master), "visits": fav_master_n},
        "favorite_service": {"id": fav_service.id, "name": fav_service.name, "visits": fav_service_n},
        "typical_interval_days": typical,
        "due_for_visit": bool(typical and days_since >= typical),
    }
    profile["suggestion"] = (
        f"O'tgan safar ({days_since} kun oldin) {last.service.name} qildirgansiz, "
        f"usta: {master_name(last.master)}. Shu ustaga yana yozilamizmi?"
    )
    return profile
