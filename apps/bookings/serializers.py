from rest_framework import serializers

from .models import Booking, WaitlistEntry
from .services import SHOP_TZ, master_name, services_label


class BookingSerializer(serializers.ModelSerializer):
    shop = serializers.CharField(source="master.shop.name", read_only=True)
    master_name = serializers.SerializerMethodField()
    service_name = serializers.SerializerMethodField()
    start_time = serializers.SerializerMethodField()
    end_time = serializers.SerializerMethodField()
    client_name = serializers.SerializerMethodField()
    client_phone = serializers.CharField(source="client.phone", read_only=True)

    class Meta:
        model = Booking
        fields = ("id", "shop", "client_name", "client_phone", "master", "master_name", "service", "service_name",
                  "start_time", "end_time", "price", "discount_amount", "loyalty_applied",
                  "certificate_amount", "payment_method", "status", "client_confirmed_at", "late_minutes", "created_at")
        read_only_fields = fields

    def get_service_name(self, obj):
        return services_label(obj)

    def get_master_name(self, obj):
        return master_name(obj.master)

    def get_client_name(self, obj):
        return f"{obj.client.first_name} {obj.client.last_name}".strip()

    # Vaqtlarni sartaroshxona vaqt mintaqasida (Asia/Tashkent) qaytaramiz
    def get_start_time(self, obj):
        return obj.start_time.astimezone(SHOP_TZ).isoformat()

    def get_end_time(self, obj):
        return obj.end_time.astimezone(SHOP_TZ).isoformat()


class BookingCreateSerializer(serializers.Serializer):
    master = serializers.IntegerField()
    service = serializers.IntegerField()
    date = serializers.DateField()
    start_time = serializers.TimeField(format="%H:%M", input_formats=["%H:%M"])
    promo_code = serializers.CharField(required=False, allow_blank=True, default="")
    certificate_code = serializers.CharField(required=False, allow_blank=True, default="")
    extra_services = serializers.ListField(child=serializers.IntegerField(), required=False, default=list,
                                           max_length=3)


class RespondSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["confirm", "late"])
    minutes = serializers.ChoiceField(choices=[10, 20, 30], required=False, default=10)


class RescheduleSerializer(serializers.Serializer):
    date = serializers.DateField()
    start_time = serializers.TimeField(format="%H:%M", input_formats=["%H:%M"])
    master = serializers.IntegerField(required=False)


class WaitlistCreateSerializer(serializers.Serializer):
    service = serializers.IntegerField()
    master = serializers.IntegerField(required=False, allow_null=True, default=None)
    date = serializers.DateField()
    from_time = serializers.TimeField(format="%H:%M", input_formats=["%H:%M"], required=False, allow_null=True)
    to_time = serializers.TimeField(format="%H:%M", input_formats=["%H:%M"], required=False, allow_null=True)


class WaitlistEntrySerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source="service.name", read_only=True)
    shop = serializers.CharField(source="service.shop.name", read_only=True)

    class Meta:
        model = WaitlistEntry
        fields = ("id", "service", "service_name", "shop", "master", "date", "from_time", "to_time",
                  "status", "created_at")
        read_only_fields = fields


class BookingStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Booking.Status.choices)
    payment_method = serializers.ChoiceField(choices=Booking.PaymentMethod.choices, required=False, default="")


class SlotQuerySerializer(serializers.Serializer):
    master = serializers.IntegerField()
    service = serializers.IntegerField()
    date = serializers.DateField()
