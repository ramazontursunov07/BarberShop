from django.contrib import admin
from .models import Booking, WaitlistEntry


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("client", "master", "service", "start_time", "status", "price", "discount_amount")
    list_filter = ("status", "master__shop", "start_time")
    search_fields = ("client__phone", "master__user__phone")


@admin.register(WaitlistEntry)
class WaitlistEntryAdmin(admin.ModelAdmin):
    list_display = ("client", "service", "master", "date", "status", "created_at")
    list_filter = ("status", "service__shop", "date")
    search_fields = ("client__phone",)
