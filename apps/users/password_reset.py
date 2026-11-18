"""Parolni tiklash: bir martalik 6 xonali kod foydalanuvchining Telegram'iga yuboriladi.

Oqim:
  1) POST /api/users/password-reset/request/  {phone}
     Javob har doim bir xil (raqam bazada borligini bildirmaydi). Raqam Telegram botga ulangan bo'lsa, kod yuboriladi.
  2) POST /api/users/password-reset/confirm/  {phone, code, new_password}
     Kod to'g'ri bo'lsa parol almashadi. Eski tokenlar bekor bo'ladi (CHECK_REVOKE_TOKEN).

Xavfsizlik: kod faqat xesh ko'rinishida (keshda) saqlanadi, 10 daqiqa amal qiladi, 5 ta noto'g'ri urinishdan keyin
bekor bo'ladi, qayta yuborish 60 soniyada bir marta, IP bo'yicha so'rovlar cheklangan.
"""
import hashlib
import hmac
import logging
import secrets

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.ai.notify import send_telegram

from .models import User
from .telegram import normalize_phone

logger = logging.getLogger(__name__)

CODE_TTL = 10 * 60      # kod amal qilish muddati (soniya)
RESEND_COOLDOWN = 60    # qayta yuborish oralig'i
MAX_TRIES = 5           # bitta kod uchun noto'g'ri urinishlar

GENERIC_REQUEST_REPLY = "Agar bu raqam Telegram botga ulangan bo'lsa, tasdiqlash kodi yuborildi."
BAD_CODE = "Kod noto'g'ri yoki muddati tugagan."


class ResetRequestThrottle(AnonRateThrottle):
    scope = "pw_reset"


def _key(user_id: int) -> str:
    return f"pwreset:{user_id}"


def _hash(user_id: int, code: str) -> str:
    msg = f"{user_id}:{code}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()


def _clean_phone(raw: str) -> str | None:
    return normalize_phone(raw)


class ResetRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32)


class ResetConfirmSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32)
    code = serializers.CharField(max_length=10)
    new_password = serializers.CharField(write_only=True, min_length=8)


class PasswordResetRequestView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ResetRequestThrottle]

    def post(self, request):
        ser = ResetRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        phone = _clean_phone(ser.validated_data["phone"])
        user = User.objects.filter(phone=phone).first() if phone else None

        if user and user.telegram_id and not user.telegram_blocked:
            if cache.add(f"pwreset:cd:{user.id}", 1, RESEND_COOLDOWN):  # cooldown ichida qayta yuborilmaydi
                code = f"{secrets.randbelow(10**6):06d}"
                cache.set(_key(user.id), {"h": _hash(user.id, code), "tries": 0}, CODE_TTL)
                text = (
                    f"🔐 BarberShop: parolni tiklash kodi — {code}\n"
                    f"Kod {CODE_TTL // 60} daqiqa amal qiladi. Buni siz so'ramagan bo'lsangiz, e'tibor bermang "
                    f"va kodni hech kimga bermang."
                )
                if not send_telegram(user.telegram_id, text):
                    cache.delete(_key(user.id))
                    cache.delete(f"pwreset:cd:{user.id}")
                    logger.warning("Parol tiklash kodi yuborilmadi: user=%s", user.id)
        return Response({"detail": GENERIC_REQUEST_REPLY})


class PasswordResetConfirmView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ResetRequestThrottle]

    def post(self, request):
        ser = ResetConfirmSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        phone = _clean_phone(data["phone"])
        user = User.objects.filter(phone=phone).first() if phone else None
        entry = cache.get(_key(user.id)) if user else None
        if not entry:
            return Response({"detail": BAD_CODE}, status=400)

        if entry["tries"] >= MAX_TRIES:
            cache.delete(_key(user.id))
            return Response({"detail": BAD_CODE}, status=400)
        if not hmac.compare_digest(entry["h"], _hash(user.id, data["code"].strip())):
            entry["tries"] += 1
            if entry["tries"] >= MAX_TRIES:
                cache.delete(_key(user.id))
            else:
                cache.set(_key(user.id), entry, CODE_TTL)
            return Response({"detail": BAD_CODE}, status=400)

        try:
            validate_password(data["new_password"], user)
        except DjangoValidationError as exc:
            return Response({"new_password": list(exc.messages)}, status=400)

        user.set_password(data["new_password"])
        user.save(update_fields=["password"])
        cache.delete(_key(user.id))
        return Response({"detail": "Parol yangilandi. Endi yangi parol bilan kiring."})
