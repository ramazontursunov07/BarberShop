from datetime import timedelta

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookings.models import Booking
from apps.masters.models import Master
from apps.shops.models import Shop
from apps.users.models import User

from . import services
from .permissions import IsPlatformAdmin
from .serializers import (MasterAdminSerializer, MasterCreateSerializer, MasterPatchSerializer, ShopAdminSerializer,
                          ShopCreateSerializer, ShopStateSerializer, ShopWriteSerializer, UserAdminSerializer)


def _shops():
    return (Shop.objects.select_related("owner")
            .annotate(masters_count=Count("masters", distinct=True), services_count=Count("services", distinct=True))
            .order_by("-created_at", "id"))


def _fail(exc):
    if isinstance(exc, DjangoValidationError):
        raise ValidationError(exc.message_dict if hasattr(exc, "error_dict") else {"detail": exc.messages})
    raise ValidationError({"detail": str(exc)})


class AdminStatsView(APIView):
    """Platforma bo'yicha umumiy ko'rsatkichlar."""

    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        since = timezone.now() - timedelta(days=30)
        return Response({
            "shops_total": Shop.objects.count(),
            "shops_pending": Shop.objects.filter(is_approved=False, is_active=True).count(),
            "shops_active": Shop.objects.filter(is_approved=True, is_active=True).count(),
            "masters": Master.objects.filter(is_active=True).count(),
            "clients": User.objects.filter(role="client").count(),
            "bookings_30d": Booking.objects.filter(created_at__gte=since).count(),
            "completed_30d": Booking.objects.filter(status=Booking.Status.COMPLETED, start_time__gte=since).count(),
        })


class AdminShopListCreateView(generics.ListAPIView):
    """GET ?q=&state=pending|approved|inactive — hamma sartaroshxonalar.
    POST {"shop": {...}, "owner": {"phone","first_name","last_name","password?"}} — yangi sartaroshxona + egasi."""

    permission_classes = [IsPlatformAdmin]
    serializer_class = ShopAdminSerializer

    def get_queryset(self):
        qs = _shops()
        q = self.request.query_params.get("q", "").strip()
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(city__icontains=q) | Q(address__icontains=q)
                           | Q(owner__phone__icontains=q))
        state = self.request.query_params.get("state")
        if state == "pending":
            qs = qs.filter(is_approved=False, is_active=True)
        elif state == "approved":
            qs = qs.filter(is_approved=True, is_active=True)
        elif state == "inactive":
            qs = qs.filter(is_active=False)
        return qs

    def post(self, request):
        ser = ShopCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            shop, created, temp = services.create_shop(dict(ser.validated_data["shop"]), dict(ser.validated_data["owner"]))
        except (services.AdminError, DjangoValidationError) as exc:
            _fail(exc)
        data = ShopAdminSerializer(_shops().get(pk=shop.pk)).data
        return Response({"shop": data, "owner_created": created, "temp_password": temp}, status=status.HTTP_201_CREATED)


class AdminShopDetailView(APIView):
    """GET/PATCH bitta sartaroshxona. PATCH: maydonlar va is_approved / is_active."""

    permission_classes = [IsPlatformAdmin]

    def get(self, request, pk):
        return Response(ShopAdminSerializer(get_object_or_404(_shops(), pk=pk)).data)

    def patch(self, request, pk):
        shop = get_object_or_404(Shop, pk=pk)
        state = ShopStateSerializer(data=request.data)
        state.is_valid(raise_exception=True)
        ser = ShopWriteSerializer(shop, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        for field, value in state.validated_data.items():
            setattr(shop, field, value)
        shop.save()
        return Response(ShopAdminSerializer(get_object_or_404(_shops(), pk=pk)).data)


class AdminShopMastersView(APIView):
    """GET — sartaroshxona ustalari. POST — yangi usta (yangi akkaunt yoki mavjud mijozni usta qiladi)."""

    permission_classes = [IsPlatformAdmin]

    def get(self, request, pk):
        shop = get_object_or_404(Shop, pk=pk)
        masters = shop.masters.select_related("user").order_by("id")
        return Response(MasterAdminSerializer(masters, many=True).data)

    def post(self, request, pk):
        shop = get_object_or_404(Shop, pk=pk)
        ser = MasterCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            master, created, temp = services.create_master(shop, dict(ser.validated_data))
        except services.AdminError as exc:
            _fail(exc)
        return Response({"master": MasterAdminSerializer(master).data, "user_created": created,
                         "temp_password": temp}, status=status.HTTP_201_CREATED)


class AdminMasterDetailView(generics.UpdateAPIView):
    permission_classes = [IsPlatformAdmin]
    serializer_class = MasterPatchSerializer
    queryset = Master.objects.all()
    http_method_names = ["patch"]


class AdminUserListView(generics.ListAPIView):
    """GET ?q=&role= — foydalanuvchilar (telefon/ism bo'yicha qidirish)."""

    permission_classes = [IsPlatformAdmin]
    serializer_class = UserAdminSerializer

    def get_queryset(self):
        qs = User.objects.order_by("-date_joined", "id")
        q = self.request.query_params.get("q", "").strip()
        if q:
            qs = qs.filter(Q(phone__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q))
        role = self.request.query_params.get("role")
        if role:
            qs = qs.filter(role=role)
        return qs


class AdminUserDetailView(APIView):
    """PATCH {"is_active": false} — akkauntni bloklash/qaytarish (adminlarni va o'zingizni bloklab bo'lmaydi)."""

    permission_classes = [IsPlatformAdmin]

    def patch(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        if user.id == request.user.id or user.role == "admin" or user.is_superuser:
            raise ValidationError({"detail": "Administrator akkauntini o'zgartirib bo'lmaydi"})
        if "is_active" not in request.data:
            raise ValidationError({"is_active": "Majburiy"})
        user.is_active = bool(request.data["is_active"])
        user.save(update_fields=["is_active"])
        return Response(UserAdminSerializer(user).data)
    