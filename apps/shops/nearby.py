"""Eng yaqin sartaroshxonalar (koordinata bo'yicha, Haversine)."""
from math import asin, cos, radians, sin, sqrt

from .models import Shop


def distance_km(lat1, lng1, lat2, lng2) -> float:
    lat1, lng1, lat2, lng2 = map(radians, (float(lat1), float(lng1), float(lat2), float(lng2)))
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lng2 - lng1) / 2) ** 2
    return 6371 * 2 * asin(sqrt(h))


def nearby_shops(lat: float, lng: float, radius_km: float = 10, limit: int = 5) -> list[dict]:
    from django.db.models import Avg

    shops = (Shop.objects.filter(is_active=True, is_approved=True, latitude__isnull=False, longitude__isnull=False)
             .annotate(avg_rating=Avg("masters__bookings__review__rating")))
    out = []
    for s in shops:
        d = distance_km(lat, lng, s.latitude, s.longitude)
        if d <= radius_km:
            out.append({"id": s.id, "name": s.name, "address": s.address, "city": s.city, "phone": s.phone,
                        "distance_km": round(d, 1), "opens_at": f"{s.opens_at:%H:%M}", "closes_at": f"{s.closes_at:%H:%M}",
                        "rating": round(s.avg_rating, 1) if s.avg_rating else None,
                        "latitude": float(s.latitude), "longitude": float(s.longitude)})
    out.sort(key=lambda x: x["distance_km"])
    return out[:limit]
