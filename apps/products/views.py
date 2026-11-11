from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.filters import SearchFilter
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.shops.permissions import IsOwnerRole

from . import services
from .models import Product, ProductReservation
from .serializers import (
    ProductOwnerSerializer,
    ProductPublicSerializer,
    ReservationCreateSerializer,
    ReservationSerializer,
    ReservationStatusSerializer,
)


def _related(qs):
    return qs.select_related("product__shop")


class ProductListView(generics.ListAPIView):
    """GET /api/products/?shop=<id>&category=...&search=...: hamma uchun."""

    serializer_class = ProductPublicSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [SearchFilter]
    search_fields = ["name", "description"]

    def get_queryset(self):
        qs = Product.objects.filter(is_active=True, shop__is_active=True, shop__is_approved=True)
        shop = self.request.query_params.get("shop")
        if shop:
            if not shop.isdigit():
                raise ValidationError({"shop": "Son bo'lishi kerak."})
            qs = qs.filter(shop_id=int(shop))
        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category__iexact=category)
        return qs


class MyProductListCreateView(generics.ListCreateAPIView):
    serializer_class = ProductOwnerSerializer
    permission_classes = [IsOwnerRole]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        return Product.objects.filter(shop__owner=self.request.user)


class MyProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProductOwnerSerializer
    permission_classes = [IsOwnerRole]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        return Product.objects.filter(shop__owner=self.request.user)

    def perform_destroy(self, instance):
        # Band qilishlari bo'lgan mahsulot (PROTECT) o'chmaydi: yashiramiz
        if instance.reservations.exists():
            instance.is_active = False
            instance.save(update_fields=["is_active"])
        else:
            instance.delete()


class ReservationListCreateView(APIView):
    """Mijoz: GET mening band qilishlarim, POST {"product": 1, "quantity": 2}."""

    def get(self, request):
        qs = _related(ProductReservation.objects.filter(client=request.user))
        return Response(ReservationSerializer(qs, many=True).data)

    def post(self, request):
        ser = ReservationCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            res = services.reserve(request.user, ser.validated_data["product"], ser.validated_data["quantity"])
        except services.ProductError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        res = _related(ProductReservation.objects.filter(pk=res.pk)).get()
        return Response(ReservationSerializer(res).data, status=status.HTTP_201_CREATED)


class ReservationCancelView(APIView):
    def post(self, request, pk):
        try:
            res = services.cancel_by_client(request.user, pk)
        except services.ProductError as exc:
            code = status.HTTP_404_NOT_FOUND if "topilmadi" in str(exc) else status.HTTP_400_BAD_REQUEST
            return Response({"detail": str(exc)}, status=code)
        return Response(ReservationSerializer(_related(ProductReservation.objects.filter(pk=res.pk)).get()).data)


class ShopReservationListView(generics.ListAPIView):
    """Egasi: o'z sartaroshxonalaridagi band qilishlar. ?status=reserved"""

    serializer_class = ReservationSerializer
    permission_classes = [IsOwnerRole]

    def get_queryset(self):
        qs = _related(ProductReservation.objects.filter(product__shop__owner=self.request.user))
        value = self.request.query_params.get("status")
        return qs.filter(status=value) if value else qs


class ReservationStatusView(APIView):
    """Egasi: {"status": "picked_up" | "cancelled"}."""

    permission_classes = [IsOwnerRole]

    def post(self, request, pk):
        ser = ReservationStatusSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            res = services.set_status_by_owner(request.user, pk, ser.validated_data["status"])
        except services.ProductError as exc:
            code = status.HTTP_404_NOT_FOUND if "topilmadi" in str(exc) else status.HTTP_400_BAD_REQUEST
            return Response({"detail": str(exc)}, status=code)
        return Response(ReservationSerializer(_related(ProductReservation.objects.filter(pk=res.pk)).get()).data)
    