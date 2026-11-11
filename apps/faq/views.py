from rest_framework import generics, permissions
from rest_framework.exceptions import ValidationError

from apps.shops.permissions import IsOwnerRole

from .models import FAQItem
from .serializers import FAQOwnerSerializer, FAQPublicSerializer


class FAQListView(generics.ListAPIView):
    """GET /api/faq/?shop=<id>: hamma uchun."""

    serializer_class = FAQPublicSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None

    def get_queryset(self):
        shop = self.request.query_params.get("shop", "")
        if not shop.isdigit():
            raise ValidationError({"shop": "Sartaroshxona ID si kerak (son)."})
        return FAQItem.objects.filter(shop_id=int(shop), is_active=True, shop__is_active=True, shop__is_approved=True)


class MyFAQListCreateView(generics.ListCreateAPIView):
    serializer_class = FAQOwnerSerializer
    permission_classes = [IsOwnerRole]

    def get_queryset(self):
        return FAQItem.objects.filter(shop__owner=self.request.user)


class MyFAQDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = FAQOwnerSerializer
    permission_classes = [IsOwnerRole]

    def get_queryset(self):
        return FAQItem.objects.filter(shop__owner=self.request.user)
    