from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from .models import Shop, ShopPhoto

MAX_PHOTO_BYTES = 5 * 1024 * 1024  # 5 MB


class ShopPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShopPhoto
        fields = ('id', 'image')


class RatingMixin(serializers.Serializer):
    """avg_rating / reviews_count: querysetda annotate qilingan bo'lsa ishlatiladi (shops.views.with_rating)."""
    avg_rating = serializers.SerializerMethodField()
    reviews_count = serializers.SerializerMethodField()

    def get_avg_rating(self, obj):
        value = getattr(obj, 'avg_rating', None)
        return round(float(value), 1) if value is not None else None

    def get_reviews_count(self, obj):
        return getattr(obj, 'reviews_count', 0)


class ShopListSerializer(RatingMixin, serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = ('id', 'name', 'city', 'district', 'address', 'latitude', 'longitude', 'opens_at', 'closes_at',
                  'avg_rating', 'reviews_count')


class ShopDetailSerializer(RatingMixin, serializers.ModelSerializer):
    photos = ShopPhotoSerializer(many=True, read_only=True)

    class Meta:
        model = Shop
        fields = ('id', 'name', 'description', 'phone', 'city', 'district', 'address', 'latitude', 'longitude',
                  'opens_at',
                  'closes_at', 'photos', 'avg_rating', 'reviews_count')


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


class ShopPhotoCreateSerializer(serializers.ModelSerializer):
    """Sartaroshxonaga rasm yuklash. Egasi faqat O'Z sartaroshxonasiga yuklay oladi."""

    class Meta:
        model = ShopPhoto
        fields = ('id', 'shop', 'image')

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')
        if request is not None and request.user.is_authenticated:
            # Boshqa eganing sartaroshxonasi "mavjud emas" deb ko'rinadi (mavjudligi ham oshkor bo'lmaydi)
            fields['shop'].queryset = Shop.objects.filter(owner=request.user)
        else:
            fields['shop'].queryset = Shop.objects.none()
        return fields

    def validate_image(self, image):
        if image.size > MAX_PHOTO_BYTES:
            raise serializers.ValidationError("Rasm hajmi 5 MB dan oshmasligi kerak.")
        return image
