from django.contrib import admin
from .models import Service


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "shop", "price", "duration_minutes", "is_active")
    list_filter = ("shop", "is_active")
    search_fields = ("name", "shop__name")
