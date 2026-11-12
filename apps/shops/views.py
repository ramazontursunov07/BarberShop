from rest_framework.filters import SearchFilter
from rest_framework.parsers import FormParser, MultiPartParser

from .serializers import (
    ShopListSerializer, ShopDetailSerializer, ShopWriteSerializer, ShopPhotoCreateSerializer,
)

from django.db.models import Avg, Count
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Shop
from .permissions import IsOwnerRole, IsShopOwner


def with_rating(qs):
    """Sartaroshxona reytingi: ustalarining bronlariga yozilgan sharhlar bo'yicha."""
    return qs.annotate(
        avg_rating=Avg('masters__bookings__review__rating'),
        reviews_count=Count('masters__bookings__review'),
    )


class ShopListView(generics.ListAPIView):
    queryset = with_rating(Shop.objects.filter(is_approved=True, is_active=True))
    serializer_class = ShopListSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [SearchFilter]
    search_fields = ['name', 'address']

    def get_queryset(self):
        queryset = super().get_queryset()
        city = self.request.query_params.get('city')
        if city:
            queryset = queryset.filter(city__iexact=city)
        return queryset


class ShopDetailView(generics.RetrieveAPIView):
    queryset = with_rating(Shop.objects.filter(is_approved=True, is_active=True)).prefetch_related('photos')
    serializer_class = ShopDetailSerializer
    permission_classes = [permissions.AllowAny]


class MyShopListCreateView(generics.ListCreateAPIView):
    serializer_class = ShopWriteSerializer
    permission_classes = [IsOwnerRole]

    def get_queryset(self):
        return Shop.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class MyShopDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = ShopWriteSerializer
    permission_classes = [IsOwnerRole, IsShopOwner]

    def get_queryset(self):
        return Shop.objects.filter(owner=self.request.user)


class ShopPhotoCreateView(generics.CreateAPIView):
    """POST /api/shops/photos/  (multipart/form-data: shop=<id>, image=<fayl>)"""

    serializer_class = ShopPhotoCreateSerializer
    permission_classes = [IsOwnerRole]
    parser_classes = [MultiPartParser, FormParser]


class NearbyShopsView(APIView):
    """GET /api/shops/nearby/?lat=41.31&lng=69.24&radius_km=10&limit=5 — mijozga eng yaqin sartaroshxonalar."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        from rest_framework.exceptions import ValidationError

        from .nearby import nearby_shops

        try:
            lat = float(request.query_params["lat"])
            lng = float(request.query_params["lng"])
            radius = float(request.query_params.get("radius_km", 10))
            limit = int(request.query_params.get("limit", 5))
        except (KeyError, ValueError):
            raise ValidationError({"detail": "lat va lng (son) majburiy"})
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise ValidationError({"detail": "Koordinata noto'g'ri"})
        return Response(nearby_shops(lat, lng, min(max(radius, 0.1), 100), min(max(limit, 1), 20)))
