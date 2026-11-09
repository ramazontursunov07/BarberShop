from rest_framework import serializers

from apps.bookings.services import master_name

from .models import Master, WorkSchedule


class MasterSerializer(serializers.ModelSerializer):
    """Ustaning ochiq profili. Telefon raqam ko'rsatilmaydi."""
    name = serializers.SerializerMethodField()
    shop_name = serializers.CharField(source="shop.name", read_only=True)
    avg_rating = serializers.SerializerMethodField()
    reviews_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Master
        fields = ("id", "shop", "shop_name", "name", "bio", "photo", "avg_rating", "reviews_count", "is_active")
        read_only_fields = fields

    def get_name(self, obj):
        return master_name(obj)

    def get_avg_rating(self, obj):
        value = getattr(obj, "avg_rating", None)
        return round(value, 1) if value is not None else None


class MasterUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Master
        fields = ("bio", "is_active")


class ScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkSchedule
        fields = ("weekday", "start_time", "end_time")

    def validate_weekday(self, value):
        if not 0 <= value <= 6:
            raise serializers.ValidationError("Hafta kuni 0 (dushanba) dan 6 (yakshanba) gacha.")
        return value

    def validate(self, attrs):
        if attrs["start_time"] >= attrs["end_time"]:
            raise serializers.ValidationError("Boshlanish vaqti tugash vaqtidan oldin bo'lishi kerak.")
        return attrs
