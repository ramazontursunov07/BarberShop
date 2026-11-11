from django.contrib import admin

from .models import PricingRule


@admin.register(PricingRule)
class PricingRuleAdmin(admin.ModelAdmin):
    list_display = ("shop", "label", "weekday", "start_time", "end_time", "percent", "is_active")
    list_filter = ("shop", "is_active")
    