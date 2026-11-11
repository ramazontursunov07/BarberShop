from rest_framework import serializers

from apps.shops.models import Shop

from .models import Product, ProductReservation

MAX_IMAGE_BYTES = 5 * 1024 * 1024


class ProductPublicSerializer(serializers.ModelSerializer):
    in_stock = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ("id", "shop", "name", "description", "category", "price", "image", "in_stock")

    def get_in_stock(self, obj):
        return obj.stock > 0


class ProductOwnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ("id", "shop", "name", "description", "category", "price", "stock", "image", "is_active")

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        fields["shop"].queryset = (
            Shop.objects.filter(owner=request.user) if request and request.user.is_authenticated
            else Shop.objects.none()
        )
        return fields

    def validate_image(self, image):
        if image and image.size > MAX_IMAGE_BYTES:
            raise serializers.ValidationError("Rasm hajmi 5 MB dan oshmasligi kerak.")
        return image


class ReservationCreateSerializer(serializers.Serializer):
    product = serializers.IntegerField()
    quantity = serializers.IntegerField(default=1)


class ReservationSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    shop = serializers.CharField(source="product.shop.name", read_only=True)
    total = serializers.IntegerField(read_only=True)

    class Meta:
        model = ProductReservation
        fields = ("id", "product", "product_name", "shop", "quantity", "unit_price", "total", "status", "created_at")
        read_only_fields = fields


class ReservationStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["picked_up", "cancelled"])
    