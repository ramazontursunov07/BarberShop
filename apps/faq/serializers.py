from rest_framework import serializers

from apps.shops.models import Shop

from .models import FAQItem


class FAQPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQItem
        fields = ("id", "question", "answer")


class FAQOwnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQItem
        fields = ("id", "shop", "question", "answer", "position", "is_active")

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        fields["shop"].queryset = (
            Shop.objects.filter(owner=request.user) if request and request.user.is_authenticated
            else Shop.objects.none()
        )
        return fields
    