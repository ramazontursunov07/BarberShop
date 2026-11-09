"""Telegram bot uchun server-server autentifikatsiya.

Bot foydalanuvchi nomidan API'ni chaqirishi uchun JWT oladi. Endpoint faqat bot biladigan
maxfiy kalit (X-Bot-Secret) bilan ishlaydi. Telefon raqamni Telegram o'zi tasdiqlaydi:
bot faqat foydalanuvchi O'ZINING kontaktini yuborgan holatdagina raqamni uzatadi.
"""
import hmac
import re

from django.conf import settings
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User

PHONE_RE = re.compile(r"^\+998\d{9}$")


def normalize_phone(raw: str) -> str | None:
    """'998 90 123-45-67' / '+998901234567' -> '+998901234567'. Yaroqsiz bo'lsa None."""
    digits = re.sub(r"\D", "", raw or "")
    phone = f"+{digits}" if digits else ""
    return phone if PHONE_RE.match(phone) else None


class TelegramAuthSerializer(serializers.Serializer):
    telegram_id = serializers.IntegerField(min_value=1)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=32)
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=100)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=100)


def _secret_ok(request) -> bool:
    expected = getattr(settings, "TELEGRAM_BOT_SECRET", "") or ""
    given = request.headers.get("X-Bot-Secret", "")
    return bool(expected) and hmac.compare_digest(given.encode(), expected.encode())


def _token_response(user) -> Response:
    return Response({
        "access": str(RefreshToken.for_user(user).access_token),
        "user": {"id": user.id, "first_name": user.first_name, "role": user.role},
    })


class TelegramAuthView(APIView):
    """POST /api/users/telegram/auth/

    {telegram_id}                  -> shu Telegram bog'langan bo'lsa token, bo'lmasa 404
    {telegram_id, phone, ...}      -> raqam bo'yicha foydalanuvchini topadi yoki yaratadi,
                                      Telegram'ni bog'laydi va token qaytaradi
    """

    authentication_classes = []  # JWT ham, CSRF ham kerak emas: faqat maxfiy kalit
    permission_classes = [AllowAny]

    def post(self, request):
        if not _secret_ok(request):
            return Response({"detail": "Ruxsat yo'q"}, status=status.HTTP_403_FORBIDDEN)

        serializer = TelegramAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        tg_id = data["telegram_id"]

        by_telegram = User.objects.filter(telegram_id=tg_id).first()

        if not data.get("phone"):
            if by_telegram is None:
                return Response({"detail": "Telegram hali bog'lanmagan"}, status=status.HTTP_404_NOT_FOUND)
            return self._issue(by_telegram)

        phone = normalize_phone(data["phone"])
        if phone is None:
            return Response(
                {"detail": "Faqat O'zbekiston raqamlari (+998...) qabul qilinadi"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.filter(phone=phone).first()
        if by_telegram and (user is None or by_telegram.pk != user.pk):
            return Response(
                {"detail": "Bu Telegram akkaunt boshqa raqamga ulangan"},
                status=status.HTTP_409_CONFLICT,
            )
        if user and user.telegram_id not in (None, tg_id):
            return Response(
                {"detail": "Bu raqam boshqa Telegram akkauntga ulangan"},
                status=status.HTTP_409_CONFLICT,
            )

        if user is None:
            user = User.objects.create_user(
                phone=phone,  # parol berilmaydi -> kirish faqat Telegram orqali
                first_name=(data.get("first_name") or "Mijoz")[:20],
                last_name=(data.get("last_name") or "")[:20],
                role="client",
                is_phone_verified=True,
                telegram_id=tg_id,
            )
        elif user.telegram_id is None:
            user.telegram_id = tg_id
            user.is_phone_verified = True  # raqamni Telegram tasdiqlagan
            user.save(update_fields=["telegram_id", "is_phone_verified"])

        return self._issue(user)

    @staticmethod
    def _issue(user):
        if not user.is_active:
            return Response({"detail": "Akkaunt faol emas"}, status=status.HTTP_403_FORBIDDEN)
        return _token_response(user)
