from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.bookings.models import Booking


class Review(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='review')
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def clean(self):
        if self.booking_id:
            if self.booking.status != Booking.Status.COMPLETED:
                raise ValidationError("Faqat bajarilgan bronga sharh yozish mumkin.")
            if self.client_id and self.booking.client_id != self.client_id:
                raise ValidationError("Faqat o'z broningizga sharh yozishingiz mumkin.")

    def __str__(self):
        return f"{self.booking} - {self.rating}/5"
