"""Egasi uchun mijozlar bazasi: tashrif tarixi, afzal usta va xizmat, kelmaganlar."""
from collections import Counter

from apps.bookings.models import Booking
from apps.bookings.services import SHOP_TZ, master_name

ORDERINGS = {
    "last_visit": lambda c: c["last_visit"] or "",
    "visits": lambda c: c["visits"],
    "spent": lambda c: c["total_spent"],
    "no_shows": lambda c: c["no_shows"],
}


def _full_name(user) -> str:
    return f"{user.first_name} {user.last_name}".strip()


def _top(counter: Counter):
    if not counter:
        return None
    # teng bo'lsa nomi bo'yicha barqaror tartib
    name, n = sorted(counter.items(), key=lambda x: (-x[1], x[0]))[0]
    return {"name": name, "visits": n}


def _summarize(user, bookings) -> dict:
    done = [b for b in bookings if b.status == Booking.Status.COMPLETED]
    last = max(done, key=lambda b: b.start_time) if done else None
    first = min(done, key=lambda b: b.start_time) if done else None
    return {
        "id": user.id,
        "name": _full_name(user),
        "phone": user.phone,
        "visits": len(done),
        "no_shows": sum(b.status == Booking.Status.NO_SHOW for b in bookings),
        "cancelled": sum(b.status == Booking.Status.CANCELLED for b in bookings),
        "upcoming": sum(b.status in (Booking.Status.PENDING, Booking.Status.CONFIRMED) for b in bookings),
        "total_spent": sum(int(b.price) for b in done),
        "first_visit": first.start_time.astimezone(SHOP_TZ).strftime("%Y-%m-%d") if first else None,
        "last_visit": last.start_time.astimezone(SHOP_TZ).strftime("%Y-%m-%d") if last else None,
        "favorite_master": _top(Counter(master_name(b.master) for b in done)),
        "favorite_service": _top(Counter(b.service.name for b in done)),
    }


def _shop_bookings(shop):
    return (
        Booking.objects.filter(master__shop=shop)
        .select_related("client", "master__user", "service")
        .order_by("start_time")
    )


def shop_clients(shop, search: str = "", ordering: str = "last_visit") -> list[dict]:
    """Sartaroshxonaga kamida bitta bron qilgan barcha mijozlar."""
    grouped: dict[int, list] = {}
    users = {}
    for b in _shop_bookings(shop):
        grouped.setdefault(b.client_id, []).append(b)
        users[b.client_id] = b.client

    clients = [_summarize(users[uid], bs) for uid, bs in grouped.items()]

    search = (search or "").strip().lower()
    if search:
        clients = [c for c in clients if search in c["name"].lower() or search in c["phone"]]

    key = ORDERINGS.get(ordering, ORDERINGS["last_visit"])
    clients.sort(key=key, reverse=True)
    return clients


def client_detail(shop, client_id: int):
    """Bitta mijoz: xulosa va shu sartaroshxonadagi to'liq bron tarixi. Mijoz topilmasa None."""
    bookings = [b for b in _shop_bookings(shop) if b.client_id == client_id]
    if not bookings:
        return None
    data = _summarize(bookings[0].client, bookings)
    data["history"] = [
        {
            "id": b.id,
            "date": b.start_time.astimezone(SHOP_TZ).strftime("%Y-%m-%d %H:%M"),
            "service": b.service.name,
            "master": master_name(b.master),
            "price": int(b.price),
            "status": b.status,
        }
        for b in sorted(bookings, key=lambda b: b.start_time, reverse=True)
    ]
    return data
