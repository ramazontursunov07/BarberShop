from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Product(models.Model):
    """Sartaroshxona do'konidagi mahsulot (soch uchun vosita, yog' va h.k.)."""

    shop = models.ForeignKey("shops.Shop", on_delete=models.CASCADE, related_name="products")
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=50, blank=True, help_text="Masalan: Soch uchun, Soqol yog'i")
    price = models.PositiveIntegerField(validators=[MinValueValidator(1)], help_text="So'm")
    stock = models.PositiveIntegerField(default=0, help_text="Omborda nechta bor")
    image = models.ImageField(upload_to="products/", null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["category", "name"]

    def __str__(self):
        return f"{self.name} ({self.shop.name})"


class ProductReservation(models.Model):
    """Mijoz mahsulotni oldindan band qiladi va sartaroshxonadan olib ketadi (onlayn to'lov yo'q)."""

    class Status(models.TextChoices):
        RESERVED = "reserved", "Band qilingan"
        PICKED_UP = "picked_up", "Olib ketilgan"
        CANCELLED = "cancelled", "Bekor qilingan"

    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="product_reservations")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="reservations")
    quantity = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.PositiveIntegerField(help_text="Band qilingan paytdagi narx")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.RESERVED)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def total(self) -> int:
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.client} -> {self.product.name} x{self.quantity}"
    