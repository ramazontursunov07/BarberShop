from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from .models import Shop, ShopPhoto


class ShopPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShopPhoto
        fields = ('id', 'image')


class ShopListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = ('id', 'name', 'city', 'district', 'address', 'latitude', 'longitude', 'opens_at', 'closes_at')


class ShopDetailSerializer(serializers.ModelSerializer):
    photos = ShopPhotoSerializer(many=True, read_only=True)

    class Meta:
        model = Shop
        fields = ('id', 'name', 'description', 'phone', 'city', 'district', 'address', 'latitude', 'longitude',
                  'opens_at',
                  'closes_at', 'photos')


class ShopWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = ('id', 'name', 'description', 'phone', 'city', 'district', 'address', 'latitude', 'longitude',
                  'opens_at',
                  'closes_at')

    def validate(self, attrs):
        opens_at = attrs.get('opens_at', getattr(self.instance, 'opens_at', None))
        closes_at = attrs.get('closes_at', getattr(self.instance, 'closes_at', None))

        if opens_at and closes_at and opens_at >= closes_at:
            raise serializers.ValidationError("Ochilish vaqti yopilish vaqtidan oldin bo'lishi kerak.")

        return attrs
