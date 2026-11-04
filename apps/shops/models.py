from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.core.exceptions import ValidationError


class Shop(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='shops')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    phone = models.CharField(max_length=13, validators=[
        RegexValidator(regex=r"^\+998\d{9}$", message="Telefon raqamni +998901234567 formatida kiriting.")])
    city = models.CharField(max_length=50)
    district = models.CharField(max_length=50, blank=True)
    address = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    opens_at = models.TimeField()
    closes_at = models.TimeField()
    is_approved = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def clean(self):
        if self.opens_at and self.closes_at and self.opens_at >= self.closes_at:
            raise ValidationError("Ochilish vaqti yopilish vaqtidan oldin bo'lishi kerak.")


class ShopPhoto(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField(upload_to='shops/')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.shop.name} rasmi"
