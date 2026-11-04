from django.db import models
from apps.shops.models import Shop
from django.core.validators import MinValueValidator


class Service(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='services')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=0,validators=[MinValueValidator(0)])
    duration_minutes = models.PositiveSmallIntegerField(validators=[MinValueValidator(5)])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} - {self.shop.name}"
