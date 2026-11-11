from django.contrib import admin

from .models import Product, ProductReservation


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "shop", "category", "price", "stock", "is_active")
    list_filter = ("shop", "category", "is_active")
    search_fields = ("name", "description")


@admin.register(ProductReservation)
class ProductReservationAdmin(admin.ModelAdmin):
    list_display = ("client", "product", "quantity", "unit_price", "status", "created_at")
    list_filter = ("status", "product__shop")
    search_fields = ("client__phone", "product__name")
    