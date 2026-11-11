from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class PricingRule(models.Model):
    """Egasi belgilaydigan chegirma: bo'sh soatlarni to'ldirish uchun (masalan, ish kunlari 10:00-13:00 -20%).

    Bir vaqtga bir nechta qoida to'g'ri kelsa, eng kattasi qo'llanadi (chegirmalar qo'shilmaydi).
    """

    shop = models.ForeignKey("shops.Shop", on_delete=models.CASCADE, related_name="pricing_rules")
    label = models.CharField(max_length=100, blank=True, help_text="Masalan: Ertalabki chegirma")
    weekday = models.PositiveSmallIntegerField(
        null=True, blank=True, choices=[(0, "Dushanba"), (1, "Seshanba"), (2, "Chorshanba"), (3, "Payshanba"),
                                        (4, "Juma"), (5, "Shanba"), (6, "Yakshanba")],
        help_text="Bo'sh = hamma kunlar",
    )
    start_time = models.TimeField()
    end_time = models.TimeField()
    percent = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(70)])
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["shop_id", "weekday", "start_time"]

    def __str__(self):
        day = self.get_weekday_display() if self.weekday is not None else "har kuni"
        return f"{self.shop.name}: {day} {self.start_time:%H:%M}-{self.end_time:%H:%M} -{self.percent}%"
    