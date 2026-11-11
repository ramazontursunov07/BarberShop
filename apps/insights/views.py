import logging

from django.http import Http404
from django.shortcuts import get_object_or_404
from openai import OpenAIError, RateLimitError
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.shops.models import Shop
from apps.shops.permissions import IsOwnerRole

from .clients import client_detail, shop_clients
from .demand import demand_forecast
from .hairstyle import MAX_UPLOAD_BYTES, InvalidImage, NoFaceDetected, recommend_from_selfie
from .noshow import upcoming_risky
from .stats import shop_stats


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


class StatsView(_OwnerShopView):
    """GET /api/insights/stats/?shop=<id>&days=30: daromad, eng ko'p so'ralgan xizmat, band soatlar."""

    def get(self, request):
        shop = self.get_shop(request)
        days = request.query_params.get("days", "30")
        return Response(shop_stats(shop, days=int(days) if days.isdigit() else 30))


class ClientsView(_OwnerShopView):
    """GET /api/insights/clients/?shop=<id>&search=<ism yoki telefon>&ordering=last_visit|visits|spent|no_shows"""

    def get(self, request):
        shop = self.get_shop(request)
        clients = shop_clients(
            shop,
            search=request.query_params.get("search", ""),
            ordering=request.query_params.get("ordering", "last_visit"),
        )
        return Response({"count": len(clients), "clients": clients})


class ClientDetailView(_OwnerShopView):
    """GET /api/insights/clients/<id>/?shop=<id>: mijozning tashrif tarixi."""

    def get(self, request, client_id: int):
        data = client_detail(self.get_shop(request), client_id)
        if data is None:
            raise Http404
        return Response(data)


logger = logging.getLogger(__name__)


class HairstyleThrottle(UserRateThrottle):
    scope = "ai_hairstyle"
    rate = "6/min"  # vision so'rovi qimmat


class HairstyleView(APIView):
    """Selfi bo'yicha yuz shakli va mos soch turmaklari: POST multipart, maydon `photo`. Rasm saqlanmaydi."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [HairstyleThrottle]
    parser_classes = [MultiPartParser]

    def post(self, request):
        photo = request.FILES.get("photo")
        if photo is None or photo.size == 0:
            return Response({"detail": "photo fayli majburiy"}, status=status.HTTP_400_BAD_REQUEST)
        if photo.size > MAX_UPLOAD_BYTES:
            return Response({"detail": "Rasm juda katta"}, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        try:
            return Response(recommend_from_selfie(photo.read()))
        except InvalidImage as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except NoFaceDetected as exc:
            return Response({"detail": f"{exc}. Yuzingiz aniq ko'ringan selfi yuboring."},
                            status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except RateLimitError:
            logger.warning("Vision limiti tugadi")
            return Response({"detail": "AI limiti tugadi, keyinroq urinib ko'ring"},
                            status=status.HTTP_429_TOO_MANY_REQUESTS)
        except OpenAIError as exc:
            logger.error("Vision provayderi xatosi: %s", getattr(exc, "message", exc))
            return Response({"detail": "Rasmni tahlil qilib bo'lmadi"}, status=status.HTTP_502_BAD_GATEWAY)
