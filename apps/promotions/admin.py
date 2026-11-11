from django.contrib import admin

from .models import GiftCertificate, LoyaltyProgram, PromoCode


@admin.register(LoyaltyProgram)
class LoyaltyProgramAdmin(admin.ModelAdmin):
    list_display = ("shop", "every_n_visits", "discount_percent", "is_active")


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "shop", "percent", "amount", "first_visit_only", "max_uses", "valid_until", "is_public",
                    "is_active")
    list_filter = ("shop", "is_active", "is_public")
    search_fields = ("code", "description")


@admin.register(GiftCertificate)
class GiftCertificateAdmin(admin.ModelAdmin):
    list_display = ("code", "shop", "amount", "recipient_name", "expires_at", "is_active")
    list_filter = ("shop", "is_active")
    search_fields = ("code", "recipient_name")
    readonly_fields = ("code",)
