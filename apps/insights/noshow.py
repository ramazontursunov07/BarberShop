"""No-show (kelmaslik) ehtimoli.

Hozircha tushunarli statistik model (ma'lumot kam bo'lganda ham ishlaydi, har bir omilni ko'rsatib bera oladi):
  1. Mijozning o'z tarixi: (kelmaganlar + k * umumiy_ulush) / (tugagan bronlar + k)   [Bayes silliqlash]
  2. Bron vaqtigacha qolgan muddat: uzoq oldin olingan bronlar ko'proq esdan chiqadi
  3. Soat/kun bo'yicha umumiy kelmaslik ulushi (kechqurun, dam olish kuni va h.k.)
Omillar odds (ehtimol nisbati) sifatida ko'paytiriladi. Ma'lumot to'planganda shu funksiya o'rniga
sklearn GradientBoosting qo'yish mumkin: kirish/chiqish shakli shu.
"""
from datetime import timedelta

from django.utils import timezone

from apps.bookings.models import Booking

PRIOR_RATE = 0.10  # umumiy ma'lumot yetarli bo'lmaganda taxminiy kelmaslik ulushi
MIN_GLOBAL_SAMPLES = 30
CLIENT_PRIOR_WEIGHT = 3  # mijozda necha bron bo'lgandan keyin o'z tarixiga ko'proq ishonamiz
LOW, HIGH = 0.20, 0.40

_DONE = [Booking.Status.COMPLETED, Booking.Status.NO_SHOW]


def _odds(p: float) -> float:
    p = min(max(p, 0.01), 0.99)
    return p / (1 - p)


def _prob(odds: float) -> float:
    return odds / (1 + odds)


def smoothed_rate(bad: int, total: int, prior: float, weight: float = CLIENT_PRIOR_WEIGHT) -> float:
    return (bad + weight * prior) / (total + weight)


def lead_factor(lead: timedelta) -> float:
    hours = lead.total_seconds() / 3600
    if hours < 3:
        return 0.7
    if hours < 24:
        return 0.9
    if hours < 72:
        return 1.0
    return 1.3


def build_context(shop_id) -> dict:
    """Shu sartaroshxona bo'yicha umumiy statistikani BIR marta yig'adi (ko'p bronni baholashda qayta ishlatiladi)."""
    from apps.bookings.services import SHOP_TZ

    qs = Booking.objects.filter(status__in=_DONE, master__shop_id=shop_id)
    rows = [(b.start_time.astimezone(SHOP_TZ), b.status) for b in qs.only("start_time", "status")[:5000]]
    total = len(rows)
    if total < MIN_GLOBAL_SAMPLES:
        base = PRIOR_RATE
    else:
        base = sum(s == Booking.Status.NO_SHOW for _, s in rows) / total
    return {"base": base, "samples": total, "rows": rows}


def _slot_factor(ctx: dict, start_local) -> float:
    """Shu soat-bo'lagi (4 soatlik) va kun turi (ish kuni/dam olish) bo'yicha nisbiy xavf."""
    lo = (start_local.hour // 4) * 4
    weekend = start_local.weekday() >= 5
    same = [s for t, s in ctx["rows"] if lo <= t.hour < lo + 4 and (t.weekday() >= 5) == weekend]
    if len(same) < 10:
        return 1.0
    base = ctx["base"]
    rate = smoothed_rate(sum(s == Booking.Status.NO_SHOW for s in same), len(same), base, weight=10)
    return min(max(_odds(rate) / _odds(base), 0.6), 1.8)


def risk_score(client, shop_id, start_time, now=None, ctx=None) -> dict:
    """{'probability': 0..1, 'level': low|medium|high, 'factors': {...}} (start_time: aware datetime)."""
    from apps.bookings.services import SHOP_TZ

    now = now or timezone.now()
    ctx = ctx or build_context(shop_id)
    base = ctx["base"]

    hist = Booking.objects.filter(client=client, status__in=_DONE)
    total = hist.count()
    bad = hist.filter(status=Booking.Status.NO_SHOW).count()
    client_rate = smoothed_rate(bad, total, base)

    lead = lead_factor(start_time - now)
    slot = _slot_factor(ctx, start_time.astimezone(SHOP_TZ))
    prob = _prob(_odds(client_rate) * lead * slot)
    level = "low" if prob < LOW else "medium" if prob < HIGH else "high"
    return {
        "probability": round(prob, 3),
        "level": level,
        "factors": {
            "client_rate": round(client_rate, 3),
            "client_history": {"completed_or_missed": total, "no_show": bad},
            "lead_factor": lead,
            "slot_factor": round(slot, 2),
            "base_rate": round(base, 3),
            "base_samples": ctx["samples"],
        },
    }


def upcoming_risky(shop, limit: int = 30, now=None) -> list[dict]:
    """Egasi uchun: kelgusi bronlar xavf bo'yicha tartiblangan."""
    from apps.bookings.services import SHOP_TZ, master_name

    now = now or timezone.now()
    ctx = build_context(shop.id)
    qs = (
        Booking.objects.filter(master__shop=shop, start_time__gt=now,
                               status__in=[Booking.Status.PENDING, Booking.Status.CONFIRMED])
        .select_related("client", "master__user", "service")
        .order_by("start_time")[:200]
    )
    out = []
    for b in qs:
        r = risk_score(b.client, shop.id, b.start_time, now=b.created_at, ctx=ctx)
        out.append({
            "booking_id": b.id,
            "client": b.client.first_name,
            "master": master_name(b.master),
            "service": b.service.name,
            "start": b.start_time.astimezone(SHOP_TZ).strftime("%Y-%m-%d %H:%M"),
            "risk": r["probability"],
            "level": r["level"],
        })
    out.sort(key=lambda x: -x["risk"])
    return out[:limit]
