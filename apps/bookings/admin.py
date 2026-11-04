from django.contrib import admin
from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("client", "master", "service", "start_time", "status", "price")
    list_filter = ("status", "master__shop", "start_time")
    search_fields = ("client__phone", "master__user__phone")
