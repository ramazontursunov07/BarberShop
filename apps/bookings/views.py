from datetime import datetime, timedelta

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

# Bo'sh vaqt va bron yaratish mantig'i hozircha ai.services ichida (AI agent ham shuni ishlatadi)
from apps.ai import services as availability

from .models import Booking
from .permissions import IsOwnerOrMaster
from .serializers import (
    BookingCreateSerializer,
    BookingSerializer,
    BookingStatusSerializer,
    SlotQuerySerializer,
)
from .services import SHOP_TZ, BookingError, BookingForbidden, cancel_by_client, change_status


def _related(qs):
    return qs.select_related("master__user", "master__shop", "service")


def _filter_by_params(qs, params):
    """?status=confirmed&date=2026-11-10 filtrlari."""
    status_value = params.get("status")
    if status_value:
        qs = qs.filter(status=status_value)
    date_value = params.get("date")
    if date_value:
        try:
            day = datetime.strptime(date_value, "%Y-%m-%d").date()
        except ValueError:
            raise ValidationError({"date": "Sana 'YYYY-MM-DD' formatida bo'lishi kerak"})
        start = datetime.combine(day, datetime.min.time(), tzinfo=SHOP_TZ)
        qs = qs.filter(start_time__gte=start, start_time__lt=start + timedelta(days=1))
    return qs


class BookingListCreateView(generics.ListCreateAPIView):
    """GET: mening bronlarim. POST: yangi bron."""

    def get_serializer_class(self):
        return BookingCreateSerializer if self.request.method == "POST" else BookingSerializer

    def get_queryset(self):
        qs = _related(Booking.objects.filter(client=self.request.user))
        return _filter_by_params(qs, self.request.query_params)

    def create(self, request, *args, **kwargs):
        serializer = BookingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            result = availability.create_booking(
                request.user,
                master_id=data["master"],
                service_id=data["service"],
                date=data["date"].isoformat(),
                start_time=data["start_time"].strftime("%H:%M"),
            )
        except ObjectDoesNotExist:
            return Response({"detail": "Usta yoki xizmat topilmadi"}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if "error" in result:
            return Response({"detail": result["error"]}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result, status=status.HTTP_201_CREATED)


class SlotListView(APIView):
    """GET /api/bookings/slots/?master=1&service=2&date=2026-11-10"""

    def get(self, request):
        query = SlotQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        try:
            result = availability.get_available_slots(
                request.user,
                master_id=data["master"],
                service_id=data["service"],
                date=data["date"].isoformat(),
            )
        except ObjectDoesNotExist:
            return Response({"detail": "Usta yoki xizmat topilmadi"}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)


class BookingCancelView(APIView):
    """Mijoz o'z bronini bekor qiladi."""

    def post(self, request, pk):
        try:
            booking = cancel_by_client(request.user, pk)
        except BookingError as exc:
            code = status.HTTP_404_NOT_FOUND if str(exc) == "Bron topilmadi" else status.HTTP_400_BAD_REQUEST
            return Response({"detail": str(exc)}, status=code)
        return Response(booking)


class ShopBookingListView(generics.ListAPIView):
    """Egasi o'z sartaroshxonalaridagi, usta esa o'zining bronlarini ko'radi."""

    serializer_class = BookingSerializer
    permission_classes = [IsOwnerOrMaster]

    def get_queryset(self):
        user = self.request.user
        qs = _related(Booking.objects.filter(Q(master__shop__owner=user) | Q(master__user=user)))
        return _filter_by_params(qs, self.request.query_params).order_by("start_time")


class BookingStatusView(APIView):
    """Egasi/usta: pending -> confirmed -> completed / no_show, yoki cancelled."""

    permission_classes = [IsOwnerOrMaster]

    def post(self, request, pk):
        serializer = BookingStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            booking = change_status(request.user, pk, serializer.validated_data["status"])
        except BookingForbidden as exc:
            raise PermissionDenied(str(exc))
        except BookingError as exc:
            code = status.HTTP_404_NOT_FOUND if str(exc) == "Bron topilmadi" else status.HTTP_400_BAD_REQUEST
            return Response({"detail": str(exc)}, status=code)
        return Response(booking)
    