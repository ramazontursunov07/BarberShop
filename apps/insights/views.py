from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.shops.models import Shop
from apps.shops.permissions import IsOwnerRole

from .demand import demand_forecast
from .noshow import upcoming_risky


class _OwnerShopView(APIView):
    """Faqat sartaroshxona egasi, faqat o'z sartaroshxonasi (?shop=<id>)."""

    permission_classes = [IsOwnerRole]

    def get_shop(self, request) -> Shop:
        raw = request.query_params.get("shop")
        if not raw or not raw.isdigit():
            raise ValidationError({"shop": "?shop=<sartaroshxona id> majburiy"})
        return get_object_or_404(Shop, pk=int(raw), owner=request.user)


class DemandView(_OwnerShopView):
    def get(self, request):
        shop = self.get_shop(request)
        weeks = request.query_params.get("weeks", "8")
        return Response(demand_forecast(shop, weeks=int(weeks) if weeks.isdigit() else 8))


class RiskyBookingsView(_OwnerShopView):
    def get(self, request):
        return Response({"bookings": upcoming_risky(self.get_shop(request))})
    