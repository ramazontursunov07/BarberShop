from rest_framework import serializers

from apps.bookings.models import Booking
from apps.bookings.services import master_name

from .models import Review


class ReviewCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ("id", "booking", "rating", "comment")
        # OneToOne uchun DRF inglizcha xabar beradi: takrorni o'zimiz tekshiramiz
        extra_kwargs = {"booking": {"validators": []}}

    def validate_comment(self, value):
        value = (value or "").strip()
        if len(value) > 1000:
            raise serializers.ValidationError("Sharh 1000 belgidan oshmasligi kerak.")
        return value

    def validate_booking(self, booking):
        user = self.context["request"].user
        if booking.client_id != user.id:
            raise serializers.ValidationError("Faqat o'z broningizga sharh yozishingiz mumkin.")
        if booking.status != Booking.Status.COMPLETED:
            raise serializers.ValidationError("Faqat bajarilgan bronga sharh yozish mumkin.")
        if Review.objects.filter(booking=booking).exists():
            raise serializers.ValidationError("Bu bronga sharh allaqachon yozilgan.")
        return booking


class ReviewSerializer(serializers.ModelSerializer):
    """Ochiq ko'rinish: mijozning faqat ismi chiqadi, telefon raqami hech qachon."""
    client_name = serializers.CharField(source="client.first_name", read_only=True)
    service = serializers.CharField(source="booking.service.name", read_only=True)
    shop = serializers.CharField(source="booking.master.shop.name", read_only=True)
    master = serializers.IntegerField(source="booking.master_id", read_only=True)
    master_name = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ("id", "rating", "comment", "client_name", "service", "shop", "master", "master_name", "created_at")
        read_only_fields = fields

    def get_master_name(self, obj):
        return master_name(obj.booking.master)
