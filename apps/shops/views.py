from rest_framework.filters import SearchFilter
from rest_framework.parsers import FormParser, MultiPartParser

from .serializers import (
    ShopListSerializer, ShopDetailSerializer, ShopWriteSerializer, ShopPhotoCreateSerializer,
)

from rest_framework import generics, permissions
from .models import Shop
from .permissions import IsOwnerRole, IsShopOwner


class ShopListView(generics.ListAPIView):
    queryset = Shop.objects.filter(is_approved=True, is_active=True)
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
    queryset = Shop.objects.filter(is_approved=True, is_active=True).prefetch_related('photos')
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
