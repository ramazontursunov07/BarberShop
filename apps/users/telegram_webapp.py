"""Telegram Mini App uchun autentifikatsiya.

POST /api/users/telegram/webapp/  {"init_data": "..."}
    initData imzosi to'g'ri va shu Telegram akkaunt oldin bog'langan bo'lsa JWT qaytaradi,
    bog'lanmagan bo'lsa 404 (Mini App oddiy kirish oynasini ko'rsatadi).
POST /api/users/telegram/link/    {"init_data": "..."}   (JWT bilan)
    Kirgan foydalanuvchiga Telegram akkauntni bog'laydi: keyingi safar Mini App o'zi kiradi.
"""
import os

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .webapp_auth import InitDataError, validate_init_data


def _telegram_user(request):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    return validate_init_data(str(request.data.get("init_data", "")), token)


class TelegramWebAppAuthView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            tg_user = _telegram_user(request)
        except InitDataError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)

        user = User.objects.filter(telegram_id=tg_user["id"]).first()
        if user is None:
            return Response({"detail": "Telegram hali bog'lanmagan"}, status=status.HTTP_404_NOT_FOUND)
        if not user.is_active:
            return Response({"detail": "Akkaunt faol emas"}, status=status.HTTP_403_FORBIDDEN)

        refresh = RefreshToken.for_user(user)
        return Response({"access": str(refresh.access_token), "refresh": str(refresh)})


class TelegramWebAppLinkView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            tg_user = _telegram_user(request)
        except InitDataError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)

        tg_id = tg_user["id"]
        if User.objects.filter(telegram_id=tg_id).exclude(pk=request.user.pk).exists():
            return Response({"detail": "Bu Telegram akkaunt boshqa raqamga ulangan"}, status=status.HTTP_409_CONFLICT)
        if request.user.telegram_id not in (None, tg_id):
            return Response({"detail": "Sizning akkauntingiz boshqa Telegramga ulangan"}, status=status.HTTP_409_CONFLICT)

        if request.user.telegram_id is None:
            request.user.telegram_id = tg_id
            request.user.save(update_fields=["telegram_id"])
        return Response({"linked": True})
