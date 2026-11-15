from django.db import transaction
from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404
from datetime import date as date_cls

from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.shops.permissions import IsOwnerRole

from . import dayoff
from .models import Master, WorkSchedule
from .serializers import MasterSerializer, MasterUpdateSerializer, ScheduleSerializer, TeamMasterSerializer


def _with_rating(qs):
    # Reyting: ustaning bronlariga yozilgan sharhlar bo'yicha
    return qs.select_related("user", "shop").annotate(
        avg_rating=Avg("bookings__review__rating"),
        reviews_count=Count("bookings__review"),
    ).order_by("-created_at", "id")  # annotate Meta.ordering'ni yo'qotadi: sahifalash barqaror bo'lishi uchun


class MasterListView(generics.ListAPIView):
    """Hamma uchun: faol ustalar. ?shop=<id>"""

    serializer_class = MasterSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = _with_rating(
            Master.objects.filter(is_active=True, shop__is_active=True, shop__is_approved=True)
        )
        shop = self.request.query_params.get("shop")
        if shop:
            if not shop.isdigit():
                raise ValidationError({"shop": "Son bo'lishi kerak."})
            qs = qs.filter(shop_id=int(shop))
        return qs


class MyMasterListView(generics.ListAPIView):
    """Egasi: o'z sartaroshxonalaridagi ustalar."""

    serializer_class = MasterSerializer
    permission_classes = [IsOwnerRole]

    def get_queryset(self):
        return _with_rating(Master.objects.filter(shop__owner=self.request.user))


class MyMasterDetailView(generics.RetrieveUpdateAPIView):
    """Egasi: usta tavsifi va faolligini o'zgartiradi."""

    serializer_class = MasterUpdateSerializer
    permission_classes = [IsOwnerRole]

    def get_queryset(self):
        return Master.objects.filter(shop__owner=self.request.user)


class MyTeamView(APIView):
    """Egasi: o'z sartaroshxonasi jamoasi.

    GET  ?shop=<id> — barcha ustalar (faol bo'lmaganlari ham), telefon, komissiya va kelgusi bronlar soni bilan.
    POST {shop, phone, first_name, last_name, password?, bio?, commission_percent?} — yangi usta akkaunti.
    Faqat yangi raqamga akkaunt ochiladi: ro'yxatdan o'tgan odamning rolini egasi o'zgartira olmaydi (buni admin qiladi).
    """

    permission_classes = [IsOwnerRole]

    def _shop(self, request, raw):
        from apps.shops.models import Shop

        if not str(raw or "").isdigit():
            raise ValidationError({"shop": "shop majburiy"})
        return get_object_or_404(Shop, pk=int(raw), owner=request.user)

    def get(self, request):
        shop = self._shop(request, request.query_params.get("shop"))
        masters = shop.masters.select_related("user").order_by("id")
        return Response(TeamMasterSerializer(masters, many=True).data)

    def post(self, request):
        from apps.adminpanel import services as admin_services
        from apps.adminpanel.serializers import MasterCreateSerializer
        from apps.users.models import User

        shop = self._shop(request, request.data.get("shop"))
        ser = MasterCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = dict(ser.validated_data)
        try:
            phone = admin_services.normalize_phone(data["phone"])
            if User.objects.filter(phone=phone).exists():
                raise admin_services.AdminError(
                    "Bu raqam allaqachon ro'yxatdan o'tgan. Uni usta qilish uchun platforma administratoriga murojaat qiling")
            master, created, temp = admin_services.create_master(shop, data)
        except admin_services.AdminError as exc:
            raise ValidationError({"detail": str(exc)})
        return Response({"master": TeamMasterSerializer(master).data, "temp_password": temp},
                        status=status.HTTP_201_CREATED)


class MasterScheduleView(APIView):
    """Egasi: ustaning haftalik ish jadvali.

    GET -> joriy jadval
    PUT {"schedules": [{"weekday": 0, "start_time": "09:00", "end_time": "18:00"}, ...]}
        -> jadval to'liq almashtiriladi (ro'yxatda yo'q kun = dam olish kuni)
    """

    permission_classes = [IsOwnerRole]

    def _master(self, request, pk):
        return get_object_or_404(Master, pk=pk, shop__owner=request.user)

    def get(self, request, pk):
        master = self._master(request, pk)
        return Response(ScheduleSerializer(master.schedules.all(), many=True).data)

    def put(self, request, pk):
        master = self._master(request, pk)
        items = request.data.get("schedules") if hasattr(request.data, "get") else None
        if not isinstance(items, list):
            raise ValidationError({"schedules": "Ro'yxat bo'lishi kerak."})

        serializer = ScheduleSerializer(data=items, many=True)
        serializer.is_valid(raise_exception=True)
        weekdays = [row["weekday"] for row in serializer.validated_data]
        if len(weekdays) != len(set(weekdays)):
            raise ValidationError({"schedules": "Bir kun ikki marta kiritilgan."})

        with transaction.atomic():
            master.schedules.all().delete()
            WorkSchedule.objects.bulk_create(
                [WorkSchedule(master=master, **row) for row in serializer.validated_data]
            )
        return Response(ScheduleSerializer(master.schedules.all(), many=True).data)


class MasterDaysOffView(APIView):
    """Usta (yoki egasi): kasal/dam olish kuni.

    GET  -> kelgusi dam olish kunlari
    POST {"date": "2026-11-20", "reason": "kasal"} -> kun belgilanadi, shu kundagi bronlar bekor qilinadi,
         mijozlarga Telegram xabar ketadi
    """

    permission_classes = [permissions.IsAuthenticated]

    def _master(self, request, pk):
        master = get_object_or_404(Master.objects.select_related("shop", "user"), pk=pk)
        if not dayoff.can_manage(request.user, master):
            raise PermissionDenied("Bu ustaning jadvalini ko'rishga ruxsat yo'q")
        return master

    def get(self, request, pk):
        from django.utils import timezone

        master = self._master(request, pk)
        rows = master.days_off.filter(date__gte=timezone.localdate())
        return Response([{"date": r.date.isoformat(), "reason": r.reason} for r in rows])

    def post(self, request, pk):
        master = self._master(request, pk)
        try:
            day = date_cls.fromisoformat(str(request.data.get("date", "")))
        except ValueError:
            raise ValidationError({"date": "YYYY-MM-DD formatida kiriting"})
        try:
            result = dayoff.mark_day_off(request.user, master, day, str(request.data.get("reason", "")))
        except dayoff.DayOffError as exc:
            raise ValidationError({"detail": str(exc)})
        return Response(result, status=status.HTTP_201_CREATED)


class MasterDayOffDeleteView(MasterDaysOffView):
    def delete(self, request, pk, day):
        master = self._master(request, pk)
        try:
            day = date_cls.fromisoformat(day)
        except ValueError:
            raise ValidationError({"date": "YYYY-MM-DD formatida kiriting"})
        if not dayoff.remove_day_off(request.user, master, day):
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class IsMasterRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.role == "master"
                    and hasattr(request.user, "master_profile"))


class MeMasterView(APIView):
    """GET /api/masters/me/ — usta o'z profili: sartaroshxona, komissiya, ish jadvali, kelgusi dam olish kunlari."""

    permission_classes = [IsMasterRole]

    def get(self, request):
        from django.utils import timezone

        m = Master.objects.select_related("shop", "user").get(user=request.user)
        return Response({
            "id": m.id, "shop_id": m.shop_id, "shop_name": m.shop.name, "name": f"{m.user.first_name} {m.user.last_name}".strip(),
            "phone": m.user.phone, "bio": m.bio, "is_active": m.is_active, "commission_percent": m.commission_percent,
            "schedule": [{"weekday": s.weekday, "start_time": f"{s.start_time:%H:%M}", "end_time": f"{s.end_time:%H:%M}"}
                         for s in m.schedules.all()],
            "days_off": [{"date": d.date.isoformat(), "reason": d.reason}
                         for d in m.days_off.filter(date__gte=timezone.localdate()).order_by("date")],
        })


class MeMasterEarningsView(APIView):
    """GET /api/masters/me/earnings/?from=&to= — ustaning o'z daromadi va ulushi (standart: joriy oy)."""

    permission_classes = [IsMasterRole]

    def get(self, request):
        from datetime import date, datetime

        from apps.bookings.services import SHOP_TZ
        from apps.insights.payroll import master_earnings

        today = datetime.now(SHOP_TZ).date()
        try:
            start = date.fromisoformat(request.query_params.get("from") or today.replace(day=1).isoformat())
            end = date.fromisoformat(request.query_params.get("to") or today.isoformat())
        except ValueError:
            raise ValidationError({"detail": "Sana YYYY-MM-DD formatida bo'lishi kerak"})
        if end < start or (end - start).days > 366:
            raise ValidationError({"detail": "Oraliq noto'g'ri (eng ko'pi bilan 1 yil)"})
        return Response(master_earnings(request.user.master_profile, start, end))
