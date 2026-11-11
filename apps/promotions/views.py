from datetime import datetime

from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookings.services import SHOP_TZ
from apps.services.models import Service
from apps.shops.models import Shop
from apps.shops.permissions import IsOwnerRole

from . import services
from .models import GiftCertificate, LoyaltyProgram, PromoCode
from .serializers import (
    GiftCertificateSerializer,
    LoyaltyProgramSerializer,
    PublicPromoSerializer,
    QuoteRequestSerializer,
)
from .serializers import PromoCodeSerializer


def _shop_param(request) -> int:
    value = request.query_params.get("shop", "")
    if not value.isdigit():
        raise ValidationError({"shop": "Sartaroshxona ID si kerak (son)."})
    return int(value)


# ------------------------------------------------------------------ mijoz

class LoyaltyStatusView(APIView):
    """GET /api/promotions/loyalty/?shop=<id>: mening sodiqlik holatim."""

    def get(self, request):
        data = services.loyalty_status(request.user, _shop_param(request))
        if data is None:
            return Response({"detail": "Bu sartaroshxonada sodiqlik tizimi yo'q"}, status=status.HTTP_404_NOT_FOUND)
        return Response(data)


class PublicPromoListView(generics.ListAPIView):
    """GET /api/promotions/offers/?shop=<id>: ochiq aksiyalar (is_public)."""

    permission_classes = [permissions.AllowAny]
    serializer_class = PublicPromoSerializer
    pagination_class = None

    def get_queryset(self):
        from django.db.models import Q
        from django.utils import timezone

        now = timezone.now()
        return PromoCode.objects.filter(
            shop_id=_shop_param(self.request), is_active=True, is_public=True,
            shop__is_active=True, shop__is_approved=True,
        ).filter(Q(valid_until__isnull=True) | Q(valid_until__gte=now)).filter(
            Q(valid_from__isnull=True) | Q(valid_from__lte=now))


class CertificateCheckView(APIView):
    """GET /api/promotions/certificates/check/?code=GC-XXXX-XXXX"""

    def get(self, request):
        try:
            return Response(services.check_certificate(request.query_params.get("code", "")))
        except services.PromotionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)


class QuoteView(APIView):
    """POST /api/promotions/quote/: bron yaratmasdan narxni oldindan hisoblash."""

    def post(self, request):
        ser = QuoteRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        service = get_object_or_404(Service, pk=data["service"], is_active=True)
        start = datetime.combine(data["date"], data["start_time"], tzinfo=SHOP_TZ)
        try:
            result = services.quote(request.user, service, start, data["promo_code"], data["certificate_code"])
        except services.PromotionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result.as_dict())


# ------------------------------------------------------------------ egasi

class MyPromoCodeListCreateView(generics.ListCreateAPIView):
    serializer_class = PromoCodeSerializer
    permission_classes = [IsOwnerRole]

    def get_queryset(self):
        return PromoCode.objects.filter(shop__owner=self.request.user)


class MyPromoCodeDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PromoCodeSerializer
    permission_classes = [IsOwnerRole]

    def get_queryset(self):
        return PromoCode.objects.filter(shop__owner=self.request.user)


class MyCertificateListCreateView(generics.ListCreateAPIView):
    """Egasi sertifikat beradi (kod avtomatik yaratiladi). O'chirish yo'q: is_active=false qiling."""

    serializer_class = GiftCertificateSerializer
    permission_classes = [IsOwnerRole]

    def get_queryset(self):
        return GiftCertificate.objects.filter(shop__owner=self.request.user)


class MyCertificateDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = GiftCertificateSerializer
    permission_classes = [IsOwnerRole]

    def get_queryset(self):
        return GiftCertificate.objects.filter(shop__owner=self.request.user)


class MyLoyaltyView(APIView):
    """GET ?shop=<id> va PUT: sodiqlik dasturini ko'rish / yaratish / yangilash."""

    permission_classes = [IsOwnerRole]

    def get(self, request):
        shop = get_object_or_404(Shop, pk=_shop_param(request), owner=request.user)
        program = LoyaltyProgram.objects.filter(shop=shop).first()
        if program is None:
            return Response({"detail": "Sodiqlik dasturi yo'q"}, status=status.HTTP_404_NOT_FOUND)
        return Response(LoyaltyProgramSerializer(program, context={"request": request}).data)

    def put(self, request):
        ser = LoyaltyProgramSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        data = dict(ser.validated_data)
        shop = data.pop("shop")
        program, created = LoyaltyProgram.objects.update_or_create(shop=shop, defaults=data)
        out = LoyaltyProgramSerializer(program, context={"request": request}).data
        return Response(out, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
    