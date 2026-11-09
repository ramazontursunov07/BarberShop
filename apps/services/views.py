from rest_framework import generics, permissions
from rest_framework.exceptions import ValidationError

from apps.shops.permissions import IsOwnerRole

from .models import Service
from .serializers import ServiceSerializer, ServiceWriteSerializer


def _shop_param(request):
    value = request.query_params.get("shop")
    if value is None or value == "":
        return None
    if not value.isdigit():
        raise ValidationError({"shop": "Son bo'lishi kerak."})
    return int(value)


class ServiceListView(generics.ListAPIView):
    """Hamma uchun: tasdiqlangan va faol sartaroshxonalarning faol xizmatlari. ?shop=<id>"""

    serializer_class = ServiceSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = Service.objects.filter(
            is_active=True, shop__is_active=True, shop__is_approved=True
        ).select_related("shop")
        shop_id = _shop_param(self.request)
        if shop_id:
            qs = qs.filter(shop_id=shop_id)
        return qs


class MyServiceListCreateView(generics.ListCreateAPIView):
    """Egasi: o'z xizmatlari (nofaollari ham) va yangi xizmat qo'shish."""

    serializer_class = ServiceWriteSerializer
    permission_classes = [IsOwnerRole]

    def get_queryset(self):
        qs = Service.objects.filter(shop__owner=self.request.user)
        shop_id = _shop_param(self.request)
        if shop_id:
            qs = qs.filter(shop_id=shop_id)
        return qs


class MyServiceDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ServiceWriteSerializer
    permission_classes = [IsOwnerRole]

    def get_queryset(self):
        return Service.objects.filter(shop__owner=self.request.user)

    def perform_destroy(self, instance):
        # Haqiqiy o'chirmaymiz: xizmat eski bronlarda ishlatilgan (PROTECT), tarix saqlanadi
        instance.is_active = False
        instance.save(update_fields=["is_active"])
        