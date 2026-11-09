from django.db import transaction
from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.shops.permissions import IsOwnerRole

from .models import Master, WorkSchedule
from .serializers import MasterSerializer, MasterUpdateSerializer, ScheduleSerializer


def _with_rating(qs):
    # Reyting: ustaning bronlariga yozilgan sharhlar bo'yicha
    return qs.select_related("user", "shop").annotate(
        avg_rating=Avg("bookings__review__rating"),
        reviews_count=Count("bookings__review"),
    )


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
