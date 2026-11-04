from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import UniqueConstraint

from apps.shops.models import Shop


class Master(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='master_profile')
    shop = models.ForeignKey(Shop, on_delete=models.PROTECT, related_name='masters')
    bio = models.TextField(blank=True)
    photo = models.ImageField(upload_to='masters/', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.user.phone


class WorkSchedule(models.Model):
    WEEK_CHOICES = [
        (0, 'Dushanba'),
        (1, 'Seshanba'),
        (2, 'Chorshanba'),
        (3, 'Payshanba'),
        (4, 'Juma'),
        (5, 'Shanba'),
        (6, 'Yakshanba')
    ]
    master = models.ForeignKey(Master, on_delete=models.CASCADE, related_name='schedules')
    weekday = models.PositiveSmallIntegerField(choices=WEEK_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        constraints = [UniqueConstraint(fields=['master', 'weekday'], name='unique_master_weekday')]
        ordering = ['weekday', 'start_time']

    def clean(self):
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError("Boshlanish vaqti tugash vaqtidan oldin bo'lishi kerak.")

    def __str__(self):
        return f"{self.master} - {self.get_weekday_display()}"


class DayOff(models.Model):
    master = models.ForeignKey(Master, on_delete=models.CASCADE, related_name='days_off')
    date = models.DateField()
    reason = models.CharField(max_length=100, blank=True)

    class Meta:
        constraints = [UniqueConstraint(fields=['master', 'date'], name='unique_master_date')]
        ordering = ['date']

    def __str__(self):
        return f"{self.master} - {self.date}"
