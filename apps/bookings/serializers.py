from rest_framework import serializers

from .models import Booking
from .services import SHOP_TZ, master_name


class BookingSerializer(serializers.ModelSerializer):
    shop = serializers.CharField(source="master.shop.name", read_only=True)
    master_name = serializers.SerializerMethodField()
    service_name = serializers.CharField(source="service.name", read_only=True)
    start_time = serializers.SerializerMethodField()
    end_time = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = ("id", "shop", "master", "master_name", "service", "service_name",
                  "start_time", "end_time", "price", "status", "created_at")
        read_only_fields = fields

    def get_master_name(self, obj):
        return master_name(obj.master)

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


class BookingStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Booking.Status.choices)


class SlotQuerySerializer(serializers.Serializer):
    master = serializers.IntegerField()
    service = serializers.IntegerField()
    date = serializers.DateField()
    