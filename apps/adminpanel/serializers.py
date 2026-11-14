from rest_framework import serializers

from apps.masters.models import Master
from apps.shops.models import Shop
from apps.users.models import User

SHOP_FIELDS = ("name", "description", "phone", "city", "district", "address", "latitude", "longitude",
               "opens_at", "closes_at")


class ShopWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = SHOP_FIELDS

    def validate(self, attrs):
        opens = attrs.get("opens_at", getattr(self.instance, "opens_at", None))
        closes = attrs.get("closes_at", getattr(self.instance, "closes_at", None))
        if opens and closes and opens >= closes:
            raise serializers.ValidationError("Ochilish vaqti yopilish vaqtidan oldin bo'lishi kerak.")
        return attrs


class OwnerInputSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32)
    first_name = serializers.CharField(required=False, allow_blank=True, default="")
    last_name = serializers.CharField(required=False, allow_blank=True, default="")
    password = serializers.CharField(required=False, allow_blank=True, default="", write_only=True)


class ShopCreateSerializer(serializers.Serializer):
    shop = ShopWriteSerializer()
    owner = OwnerInputSerializer()


class ShopAdminSerializer(serializers.ModelSerializer):
    owner_name = serializers.SerializerMethodField()
    owner_phone = serializers.CharField(source="owner.phone", read_only=True)
    masters_count = serializers.IntegerField(read_only=True)
    services_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Shop
        fields = ("id", "name", "description", "phone", "city", "district", "address", "latitude", "longitude",
                  "opens_at", "closes_at", "is_approved", "is_active", "created_at", "owner_name", "owner_phone",
                  "masters_count", "services_count")

    def get_owner_name(self, obj):
        return f"{obj.owner.first_name} {obj.owner.last_name}".strip()


class ShopStateSerializer(serializers.Serializer):
    is_approved = serializers.BooleanField(required=False)
    is_active = serializers.BooleanField(required=False)


class MasterAdminSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    phone = serializers.CharField(source="user.phone", read_only=True)
    user_active = serializers.BooleanField(source="user.is_active", read_only=True)

    class Meta:
        model = Master
        fields = ("id", "name", "phone", "bio", "is_active", "commission_percent", "user_active")

    def get_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip()


class MasterCreateSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32)
    first_name = serializers.CharField(required=False, allow_blank=True, default="")
    last_name = serializers.CharField(required=False, allow_blank=True, default="")
    password = serializers.CharField(required=False, allow_blank=True, default="", write_only=True)
    bio = serializers.CharField(required=False, allow_blank=True, default="")
    commission_percent = serializers.IntegerField(required=False, min_value=0, max_value=100, default=50)


class MasterPatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Master
        fields = ("bio", "is_active", "commission_percent")


class UserAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "phone", "first_name", "last_name", "role", "is_active", "telegram_blocked",
                  "no_show_count", "date_joined")
        