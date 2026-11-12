"""Chegirmalar: sodiqlik, promokod, sovg'a sertifikati.

Narx hisoblash bitta joyda: REST API ham, AI agent ham `quote()` orqali ishlaydi, shuning uchun
mijozga aytilgan narx bilan yozilgan narx bir xil bo'ladi.

Qoidalar:
  * Foizli/summali chegirmalar (dinamik narx, sodiqlik, promokod) QO'SHILMAYDI: mijozga eng foydalisi qo'llanadi.
  * Sovg'a sertifikati chegirmadan keyingi summadan yechiladi (u pul hisoblanadi, shuning uchun qo'shiladi).
  * Qoldiq, promokod ishlatilishi va sodiqlik hisobi bronlardan hisoblanadi: bron bekor qilinsa hammasi o'z-o'zidan qaytadi.
"""
from dataclasses import dataclass, field

from django.db.models import Sum
from django.utils import timezone

from apps.bookings.models import Booking
from apps.insights import pricing

from .models import GiftCertificate, LoyaltyProgram, PromoCode

# Faqat BEKOR QILINGAN bron chegirma/qoldiqni qaytaradi ("kelmadi" qaytarmaydi)
RELEASED = [Booking.Status.CANCELLED]


class PromotionError(ValueError):
    """Mijozga ko'rsatiladigan xato (AI tool ham ValueError sifatida o'qiydi)."""


@dataclass
class Quote:
    base_price: int
    price_before_certificate: int
    final_price: int
    discount_amount: int = 0
    discount_kind: str = ""  # "", "dynamic", "loyalty", "promo"
    promo: PromoCode | None = None
    loyalty_applied: bool = False
    certificate: GiftCertificate | None = None
    certificate_amount: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def discount_percent(self) -> int:
        return round(self.discount_amount * 100 / self.base_price) if self.base_price else 0

    def as_dict(self) -> dict:
        return {
            "base_price": self.base_price,
            "discount_amount": self.discount_amount,
            "discount_percent": self.discount_percent,
            "discount_kind": self.discount_kind,
            "promo_code": self.promo.code if self.promo else None,
            "loyalty_applied": self.loyalty_applied,
            "certificate_amount": self.certificate_amount,
            "price": self.final_price,
            "notes": self.notes,
        }


# ------------------------------------------------------------------ sodiqlik

def paid_visits(user, shop_id: int) -> int:
    """Sodiqlik hisobiga kiradigan tashrif: bajarilgan va chegirma-sovg'a bo'lmagan bronlar."""
    return Booking.objects.filter(
        client=user, master__shop_id=shop_id, status=Booking.Status.COMPLETED, loyalty_applied=False
    ).count()


def loyalty_status(user, shop_id: int) -> dict | None:
    program = LoyaltyProgram.objects.filter(shop_id=shop_id, is_active=True).first()
    if program is None:
        return None
    n = program.every_n_visits
    visits = paid_visits(user, shop_id)
    used = (
        Booking.objects.filter(client=user, master__shop_id=shop_id, loyalty_applied=True)
        .exclude(status__in=RELEASED)
        .count()
    )
    earned = visits // n
    return {
        "every_n_visits": n,
        "discount_percent": program.discount_percent,
        "paid_visits": visits,
        "visits_to_next_reward": n - visits % n,
        "reward_available": earned - used > 0,
    }


# ------------------------------------------------------------------ promokod

def _check_promo(user, shop_id: int, code: str, lock: bool) -> PromoCode:
    qs = PromoCode.objects.filter(shop_id=shop_id, code=code.strip().upper(), is_active=True)
    if lock:
        qs = qs.select_for_update()
    promo = qs.first()
    if promo is None:
        raise PromotionError("Promokod topilmadi yoki faol emas")
    now = timezone.now()
    if promo.valid_from and now < promo.valid_from:
        raise PromotionError("Promokod hali kuchga kirmagan")
    if promo.valid_until and now > promo.valid_until:
        raise PromotionError("Promokod muddati tugagan")

    uses = promo.bookings.exclude(status__in=RELEASED)
    if promo.max_uses is not None and uses.count() >= promo.max_uses:
        raise PromotionError("Promokod limiti tugagan")
    if promo.once_per_user and uses.filter(client=user).exists():
        raise PromotionError("Siz bu promokoddan allaqachon foydalangansiz")
    if promo.first_visit_only:
        has_history = (
            Booking.objects.filter(client=user, master__shop_id=shop_id)
            .exclude(status__in=[Booking.Status.CANCELLED, Booking.Status.NO_SHOW])
            .exists()
        )
        if has_history:
            raise PromotionError("Bu promokod faqat birinchi marta kelganlar uchun")
    return promo


def _promo_price(promo: PromoCode, base: int) -> int:
    if promo.percent:
        return pricing.apply_discount(base, promo.percent)
    return max(base - promo.amount, 0)


# ------------------------------------------------------------------ sertifikat

def certificate_balance(cert: GiftCertificate) -> int:
    used = cert.bookings.exclude(status__in=RELEASED).aggregate(s=Sum("certificate_amount"))["s"] or 0
    return max(cert.amount - used, 0)


def _check_certificate(shop_id: int, code: str, lock: bool) -> GiftCertificate:
    qs = GiftCertificate.objects.filter(code=code.strip().upper(), is_active=True)
    if lock:
        qs = qs.select_for_update()
    cert = qs.first()
    if cert is None:
        raise PromotionError("Sertifikat topilmadi")
    if cert.shop_id != shop_id:
        raise PromotionError("Bu sertifikat boshqa sartaroshxona uchun")
    if cert.expires_at and cert.expires_at < timezone.now():
        raise PromotionError("Sertifikat muddati tugagan")
    if certificate_balance(cert) <= 0:
        raise PromotionError("Sertifikat qoldig'i yo'q")
    return cert


def check_certificate(code: str) -> dict:
    cert = GiftCertificate.objects.filter(code=code.strip().upper(), is_active=True).select_related("shop").first()
    if cert is None:
        raise PromotionError("Sertifikat topilmadi")
    expired = bool(cert.expires_at and cert.expires_at < timezone.now())
    return {
        "code": cert.code,
        "shop": cert.shop.name,
        "shop_id": cert.shop_id,
        "balance": 0 if expired else certificate_balance(cert),
        "expired": expired,
        "expires_at": cert.expires_at.isoformat() if cert.expires_at else None,
    }


# ------------------------------------------------------------------ asosiy hisob

def quote(user, service, start_local, promo_code: str = "", certificate_code: str = "",
          lock: bool = False, extra_price: int = 0) -> Quote:
    """Bron narxini hisoblaydi. lock=True: bron yaratish tranzaksiyasi ichida promokod/sertifikat qatorlarini qulflaydi."""
    shop_id = service.shop_id
    base = int(service.price) + int(extra_price)  # extra_price: bir tashrifdagi qo'shimcha xizmatlar narxi

    # nomzodlar: (tur, yangi narx, promo, sodiqlik)
    candidates: list[tuple[str, int, PromoCode | None, bool]] = []
    dyn_percent = pricing.discount_percent(shop_id, start_local)
    if dyn_percent:
        candidates.append(("dynamic", pricing.apply_discount(base, dyn_percent), None, False))

    status = loyalty_status(user, shop_id)
    if status and status["reward_available"]:
        candidates.append(("loyalty", pricing.apply_discount(base, status["discount_percent"]), None, True))

    promo = _check_promo(user, shop_id, promo_code, lock) if promo_code and promo_code.strip() else None
    if promo:
        candidates.append(("promo", _promo_price(promo, base), promo, False))

    notes: list[str] = []
    kind, price, used_promo, loyalty = "", base, None, False
    if candidates:
        kind, price, used_promo, loyalty = min(candidates, key=lambda c: c[1])
        if price >= base:  # foydasiz nomzod
            kind, price, used_promo, loyalty = "", base, None, False
    if promo and used_promo is None:
        notes.append("Promokod qo'llanmadi: boshqa chegirma foydaliroq (chegirmalar qo'shilmaydi)")

    cert, cert_amount = None, 0
    after_discount = price
    if certificate_code and certificate_code.strip():
        cert = _check_certificate(shop_id, certificate_code, lock)
        cert_amount = min(certificate_balance(cert), after_discount)
        price -= cert_amount

    return Quote(
        base_price=base,
        price_before_certificate=after_discount,
        final_price=price,
        discount_amount=base - after_discount,
        discount_kind=kind,
        promo=used_promo,
        loyalty_applied=loyalty,
        certificate=cert,
        certificate_amount=cert_amount,
        notes=notes,
    )


def issue_certificate(shop, amount: int, recipient_name: str = "", expires_at=None) -> GiftCertificate:
    return GiftCertificate.objects.create(
        shop=shop, amount=amount, recipient_name=recipient_name, expires_at=expires_at
    )
