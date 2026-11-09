from rest_framework import serializers

from .models import Service


class ServiceSerializer(serializers.ModelSerializer):
    """Hamma ko'radigan ro'yxat uchun."""
    shop_name = serializers.CharField(source="shop.name", read_only=True)

    class Meta:
        model = Service
        fields = ("id", "shop", "shop_name", "name", "description", "price", "duration_minutes")
        read_only_fields = fields


class ServiceWriteSerializer(serializers.ModelSerializer):
    """Sartaroshxona egasi uchun: yaratish va tahrirlash."""

    class Meta:
        model = Service
        fields = ("id", "shop", "name", "description", "price", "duration_minutes", "is_active")

    def validate_shop(self, shop):
        user = self.context["request"].user
        if shop.owner_id != user.id:
            raise serializers.ValidationError("Bu sartaroshxona sizniki emas.")
        if self.instance and shop.pk != self.instance.shop_id:
            # Xizmat boshqa sartaroshxonaga ko'chsa, eski bronlardagi ustalar mos kelmay qoladi
            raise serializers.ValidationError("Xizmatning sartaroshxonasini o'zgartirib bo'lmaydi.")
        return shop
