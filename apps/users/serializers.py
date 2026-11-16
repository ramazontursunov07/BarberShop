from rest_framework import serializers
from .models import User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ('id', 'phone', 'first_name', 'last_name', 'password')

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserSerializer(serializers.ModelSerializer):
    has_password = serializers.SerializerMethodField()
    # Telefon (kirish raqami) o'zgarganda, parol o'rnatilgan akkauntda joriy parol so'raladi
    current_password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ('id', 'phone', 'first_name', 'last_name', 'role', 'is_phone_verified', 'has_password',
                  'current_password')
        read_only_fields = ('id', 'role', 'is_phone_verified', 'has_password')

    def get_has_password(self, obj):
        return obj.has_usable_password()

    def validate_first_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Ism bo'sh bo'lmasligi kerak.")
        return value

    def validate_last_name(self, value):
        return value.strip()

    def validate(self, attrs):
        user = self.instance
        phone_changed = user is not None and "phone" in attrs and attrs["phone"] != user.phone
        if phone_changed and user.has_usable_password():
            if not user.check_password(attrs.get("current_password", "")):
                raise serializers.ValidationError({"current_password": "Telefonni o'zgartirish uchun joriy parolni kiriting."})
        return attrs

    def update(self, instance, validated_data):
        validated_data.pop("current_password", None)
        if "phone" in validated_data and validated_data["phone"] != instance.phone:
            instance.is_phone_verified = False  # yangi raqamni Telegram orqali qayta tasdiqlash kerak
        return super().update(instance, validated_data)
    