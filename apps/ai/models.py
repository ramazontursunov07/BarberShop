from django.conf import settings
from django.db import models
from django.db.models import Q


class KnowledgeDocument(models.Model):
    """Sartaroshxona egasi yozadigan qoidalar va ma'lumotlar (RAG manbasi)."""

    shop = models.ForeignKey("shops.Shop", on_delete=models.CASCADE, related_name="knowledge_docs")
    title = models.CharField(max_length=200)
    content = models.TextField(help_text="Qoida, aksiya yoki mijozlar tez-tez so'raydigan savolga javob")
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["shop_id", "title"]

    def __str__(self):
        return f"{self.shop.name}: {self.title}"


class Notification(models.Model):
    """Mijozga yuborilgan avtomatik xabarlar jurnali (takror yubormaslik uchun)."""

    class Kind(models.TextChoices):
        REMINDER = "reminder", "Bron eslatmasi"
        WINBACK = "winback", "Mijozni qaytarish"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    booking = models.ForeignKey("bookings.Booking", null=True, blank=True, on_delete=models.CASCADE,
                                related_name="notifications")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # Bitta bronga bitta turdagi xabar faqat bir marta
            models.UniqueConstraint(
                fields=["booking", "kind"], condition=Q(booking__isnull=False), name="unique_booking_notification"
            ),
        ]

    def __str__(self):
        return f"{self.kind} -> {self.user_id}"
    