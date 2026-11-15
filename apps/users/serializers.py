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

    class Meta:
        model = User
        fields = ('id', 'phone', 'first_name', 'last_name', 'role', 'is_phone_verified', 'has_password')
        read_only_fields = ('id', 'phone', 'role', 'is_phone_verified', 'has_password')

    def get_has_password(self, obj):
        return obj.has_usable_password()
