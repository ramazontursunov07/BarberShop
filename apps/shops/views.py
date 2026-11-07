from rest_framework.filters import SearchFilter

from .serializers import ShopListSerializer, ShopDetailSerializer

from rest_framework import generics, permissions
from .models import Shop


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
