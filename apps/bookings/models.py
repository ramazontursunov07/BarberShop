from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from apps.masters.models import Master
from apps.services.models import Service


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Kutilmoqda'
        CONFIRMED = 'confirmed', 'Tasdiqlangan'
        COMPLETED = 'completed', 'Bajarilgan'
        NO_SHOW = 'no_show', 'Kelmadi'
        CANCELLED = 'cancelled', 'Bekor qilingan'

    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='bookings')
    master = models.ForeignKey(Master, on_delete=models.PROTECT, related_name='bookings')
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name='bookings')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    price = models.DecimalField(max_digits=10, decimal_places=0, validators=[MinValueValidator(0)])
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start_time']
        indexes = [
            models.Index(fields=['master', 'start_time']),
        ]

    def clean(self):
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError("Boshlanish vaqti tugash vaqtidan oldin bo'lishi kerak.")

    def __str__(self):
        return f"{self.client} - {self.master} ({self.start_time:%Y-%m-%d %H:%M})"
