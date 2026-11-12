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

    class PaymentMethod(models.TextChoices):
        CASH = 'cash', 'Naqd'
        CARD = 'card', 'Karta'
        TRANSFER = 'transfer', "O'tkazma"

    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='bookings')
    master = models.ForeignKey(Master, on_delete=models.PROTECT, related_name='bookings')
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name='bookings')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    price = models.DecimalField(max_digits=10, decimal_places=0, validators=[MinValueValidator(0)])
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    # Chegirmalar (apps.promotions): price = mijoz to'laydigan yakuniy summa
    discount_amount = models.PositiveIntegerField(default=0, help_text="Chegirma summasi (so'm)")
    promo_code = models.ForeignKey("promotions.PromoCode", null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="bookings")
    loyalty_applied = models.BooleanField(default=False, help_text="Sodiqlik chegirmasi ishlatilgan")
    certificate = models.ForeignKey("promotions.GiftCertificate", null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="bookings")
    certificate_amount = models.PositiveIntegerField(default=0, help_text="Sertifikatdan yechilgan summa (so'm)")
    # Bir tashrifda bir nechta xizmat (soch + soqol): asosiy xizmat `service`, qo'shimchalari shu yerda.
    # start_time..end_time umumiy davomiylikni, price umumiy narxni bildiradi.
    extra_services = models.ManyToManyField(Service, blank=True, related_name="extra_in_bookings")
    payment_method = models.CharField(max_length=10, choices=PaymentMethod.choices, blank=True, default="",
                                      help_text="Bajarilgandan keyin: naqd, karta yoki o'tkazma")
    # Mijoz eslatmadagi tugma orqali javob bergan: "kelaman" va "N daqiqa kechikaman"
    client_confirmed_at = models.DateTimeField(null=True, blank=True, help_text="Mijoz kelishini tasdiqlagan vaqt")
    late_minutes = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Mijoz kechikishini aytgan (daqiqa)")
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


class WaitlistEntry(models.Model):
    """Kutish ro'yxati: kerakli vaqt band bo'lsa, bo'sh joy chiqqanda mijozga xabar beriladi."""

    class Status(models.TextChoices):
        WAITING = 'waiting', 'Kutmoqda'
        NOTIFIED = 'notified', 'Xabar yuborilgan'
        BOOKED = 'booked', 'Bron qilingan'
        CANCELLED = 'cancelled', 'Bekor qilingan'

    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='waitlist_entries')
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='waitlist_entries')
    master = models.ForeignKey(Master, null=True, blank=True, on_delete=models.CASCADE,
                               related_name='waitlist_entries', help_text="Bo'sh = istalgan usta")
    date = models.DateField()
    from_time = models.TimeField(null=True, blank=True, help_text="Bo'sh = kun bo'yi")
    to_time = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.WAITING)
    created_at = models.DateTimeField(auto_now_add=True)
    notified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at']
        indexes = [models.Index(fields=['service', 'date', 'status'])]

    def clean(self):
        if self.from_time and self.to_time and self.from_time >= self.to_time:
            raise ValidationError("Boshlanish vaqti tugash vaqtidan oldin bo'lishi kerak.")

    def __str__(self):
        return f"{self.client} kutmoqda: {self.service.name} {self.date}"


class QueueTicket(models.Model):
    """Jonli navbat (walk-in): mijoz "hoziroq kelaman" deb navbatga turadi, taxminiy kutish vaqtini ko'radi."""

    class Status(models.TextChoices):
        WAITING = 'waiting', 'Navbatda'
        SERVING = 'serving', 'Xizmat ko\'rsatilmoqda'
        DONE = 'done', 'Bajarildi'
        CANCELLED = 'cancelled', 'Bekor qilindi'

    shop = models.ForeignKey("shops.Shop", on_delete=models.CASCADE, related_name='queue_tickets')
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='queue_tickets')
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='queue_tickets')
    master = models.ForeignKey(Master, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name='queue_tickets', help_text="Bo'sh = istalgan usta")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.WAITING)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    booking = models.OneToOneField(Booking, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name='queue_ticket', help_text="Bajarilgach hisobot uchun yaratiladi")

    class Meta:
        ordering = ['created_at']
        indexes = [models.Index(fields=['shop', 'status'])]

    def __str__(self):
        return f"#{self.pk} {self.client} ({self.status})"


class RecurringBooking(models.Model):
    """Doimiy bron: "har 3 haftada shu usta, shu soat". Hafta kuni start_date dan olinadi."""

    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='recurring_bookings')
    master = models.ForeignKey(Master, on_delete=models.CASCADE, related_name='recurring_bookings')
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='recurring_bookings')
    start_date = models.DateField(help_text="Birinchi uchrashuv sanasi (hafta kuni shundan olinadi)")
    start_time = models.TimeField()
    every_weeks = models.PositiveSmallIntegerField(default=2, validators=[MinValueValidator(1)])
    end_date = models.DateField(null=True, blank=True)
    last_booked_date = models.DateField(null=True, blank=True, help_text="Oxirgi ishlangan uchrashuv sanasi")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.client} / {self.service} har {self.every_weeks} hafta"
