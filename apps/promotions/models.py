import secrets

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # O/0, I/1 chalkashmasligi uchun olib tashlangan


def generate_certificate_code() -> str:
    part = lambda: "".join(secrets.choice(_ALPHABET) for _ in range(4))
    return f"GC-{part()}-{part()}"


class LoyaltyProgram(models.Model):
    """Sodiqlik tizimi: har N ta pullik tashrifdan keyingi bron uchun chegirma."""

    shop = models.OneToOneField("shops.Shop", on_delete=models.CASCADE, related_name="loyalty_program")
    every_n_visits = models.PositiveSmallIntegerField(
        default=5, validators=[MinValueValidator(2), MaxValueValidator(50)],
        help_text="Har nechta bajarilgan tashrifdan keyin chegirma beriladi",
    )
    discount_percent = models.PositiveSmallIntegerField(
        default=20, validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.shop.name}: har {self.every_n_visits}-tashrifdan keyin -{self.discount_percent}%"


class PromoCode(models.Model):
    """Promokod: foiz yoki qat'iy summa. Chegirmalar qo'shilmaydi, mijozga eng foydalisi qo'llanadi."""

    shop = models.ForeignKey("shops.Shop", on_delete=models.CASCADE, related_name="promo_codes")
    code = models.CharField(max_length=30)
    description = models.CharField(max_length=200, blank=True, help_text="Masalan: Birinchi marta kelganlarga 10%")
    percent = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    amount = models.PositiveIntegerField(null=True, blank=True, help_text="Qat'iy chegirma (so'm)")
    first_visit_only = models.BooleanField(default=False, help_text="Faqat shu sartaroshxonaga birinchi marta kelganlarga")
    once_per_user = models.BooleanField(default=True)
    max_uses = models.PositiveIntegerField(null=True, blank=True, help_text="Bo'sh = cheklanmagan")
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    is_public = models.BooleanField(default=False, help_text="Mijozlarga aksiya sifatida ko'rsatiladi")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["shop", "code"], name="unique_shop_promo_code")]

    def clean(self):
        if (self.percent is None) == (self.amount is None):
            raise ValidationError("Foiz yoki summadan faqat bittasini kiriting.")
        if self.valid_from and self.valid_until and self.valid_from >= self.valid_until:
            raise ValidationError("Boshlanish sanasi tugash sanasidan oldin bo'lishi kerak.")

    def save(self, *args, **kwargs):
        self.code = (self.code or "").strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        value = f"-{self.percent}%" if self.percent else f"-{self.amount} so'm"
        return f"{self.code} ({self.shop.name}) {value}"


class GiftCertificate(models.Model):
    """Sovg'a sertifikati: egasi sartaroshxonada sotadi/beradi, mijoz kod bilan bronda ishlatadi.

    Qoldiq saqlanmaydi, bronlardan hisoblanadi (bekor qilingan bron summani qaytaradi).
    """

    shop = models.ForeignKey("shops.Shop", on_delete=models.CASCADE, related_name="gift_certificates")
    code = models.CharField(max_length=20, unique=True, default=generate_certificate_code, editable=False)
    amount = models.PositiveIntegerField(validators=[MinValueValidator(1000)], help_text="Sertifikat summasi (so'm)")
    recipient_name = models.CharField(max_length=100, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.CheckConstraint(condition=Q(amount__gte=1000), name="certificate_min_amount")]

    def __str__(self):
        return f"{self.code} ({self.shop.name}, {self.amount} so'm)"
    