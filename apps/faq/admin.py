from django.contrib import admin

from .models import FAQItem


@admin.register(FAQItem)
class FAQItemAdmin(admin.ModelAdmin):
    list_display = ("question", "shop", "position", "is_active")
    list_filter = ("shop", "is_active")
    search_fields = ("question", "answer")
    