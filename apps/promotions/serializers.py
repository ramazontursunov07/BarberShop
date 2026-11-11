from rest_framework import serializers

from apps.shops.models import Shop

from .models import GiftCertificate, LoyaltyProgram, PromoCode
from .services import certificate_balance


class OwnShopMixin:
    """`shop` maydoni faqat so'rov yuborgan egasining sartaroshxonalaridan tanlanadi."""

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        owned = Shop.objects.filter(owner=request.user) if request and request.user.is_authenticated \
            else Shop.objects.none()
        fields["shop"].queryset = owned
        return fields


class PromoCodeSerializer(OwnShopMixin, serializers.ModelSerializer):
    uses = serializers.SerializerMethodField()

    class Meta:
        model = PromoCode
        fields = ("id", "shop", "code", "description", "percent", "amount", "first_visit_only", "once_per_user",
                  "max_uses", "valid_from", "valid_until", "is_public", "is_active", "uses")
        read_only_fields = ("uses",)

    def get_uses(self, obj):
        return obj.bookings.exclude(status="cancelled").count()

    def validate_code(self, value):
        return value.strip().upper()

    def validate(self, attrs):
        get = lambda k: attrs.get(k, getattr(self.instance, k, None))
        if (get("percent") is None) == (get("amount") is None):
            raise serializers.ValidationError("Foiz yoki summadan faqat bittasini kiriting.")
        if get("valid_from") and get("valid_until") and get("valid_from") >= get("valid_until"):
            raise serializers.ValidationError("Boshlanish sanasi tugash sanasidan oldin bo'lishi kerak.")
        shop, code = get("shop"), get("code")
        dup = PromoCode.objects.filter(shop=shop, code=code)
        if self.instance:
            dup = dup.exclude(pk=self.instance.pk)
        if dup.exists():
            raise serializers.ValidationError({"code": "Bu kod allaqachon mavjud."})
        return attrs


class PublicPromoSerializer(serializers.ModelSerializer):
    class Meta:
        model = PromoCode
        fields = ("code", "description", "percent", "amount", "first_visit_only", "valid_until")


class GiftCertificateSerializer(OwnShopMixin, serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()

    class Meta:
        model = GiftCertificate
        fields = ("id", "shop", "code", "amount", "balance", "recipient_name", "expires_at", "is_active",
                  "created_at")
        read_only_fields = ("code", "balance", "created_at")

    def get_balance(self, obj):
        return certificate_balance(obj)


class LoyaltyProgramSerializer(OwnShopMixin, serializers.ModelSerializer):
    class Meta:
        model = LoyaltyProgram
        fields = ("shop", "every_n_visits", "discount_percent", "is_active")
        extra_kwargs = {"shop": {"validators": []}}  # unique tekshiruvi o'rniga upsert qilamiz


class QuoteRequestSerializer(serializers.Serializer):
    service = serializers.IntegerField()
    date = serializers.DateField()
    start_time = serializers.TimeField(format="%H:%M", input_formats=["%H:%M"])
    promo_code = serializers.CharField(required=False, allow_blank=True, default="")
    certificate_code = serializers.CharField(required=False, allow_blank=True, default="")
    