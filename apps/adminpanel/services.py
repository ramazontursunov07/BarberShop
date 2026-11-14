"""Platforma administratori amallari: egasi/usta akkauntlarini yaratish, sartaroshxona va usta qo'shish."""
import re
import secrets
from datetime import time

from django.db import transaction

from apps.masters.models import Master, WorkSchedule
from apps.shops.models import Shop
from apps.users.models import User

PHONE_RE = re.compile(r"^\+998\d{9}$")


class AdminError(ValueError):
    pass


def normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    phone = f"+{digits}" if digits else ""
    if not PHONE_RE.match(phone):
        raise AdminError("Telefon raqam +998901234567 formatida bo'lishi kerak")
    return phone


def staff_user(phone: str, first_name: str, last_name: str, password: str, role: str):
    """Telefon bo'yicha foydalanuvchini topadi yoki yaratadi va unga rol beradi.

    Qaytaradi: (user, created, temp_password). Yangi foydalanuvchiga parol berilmasa, tasodifiy parol
    yaratiladi va FAQAT shu javobda bir marta qaytariladi. Mavjud foydalanuvchi paroli o'zgarmaydi.
    """
    phone = normalize_phone(phone)
    user = User.objects.filter(phone=phone).first()
    if user is None:
        if not first_name.strip():
            raise AdminError("Yangi foydalanuvchi uchun ism majburiy")
        if password and len(password) < 8:
            raise AdminError("Parol kamida 8 ta belgi bo'lishi kerak")
        temp = "" if password else secrets.token_urlsafe(9)
        user = User.objects.create_user(phone=phone, password=password or temp, first_name=first_name.strip()[:20],
                                        last_name=last_name.strip()[:20], role=role, is_phone_verified=True)
        return user, True, temp

    if user.role == role:
        return user, False, ""
    if user.role == "client":  # oddiy mijoz akkaunti egasi/usta bo'lishi mumkin
        user.role = role
        user.save(update_fields=["role"])
        return user, False, ""
    raise AdminError(f"Bu raqam allaqachon '{user.role}' rolida, rolini o'zgartirib bo'lmaydi")


@transaction.atomic
def create_shop(data: dict, owner_data: dict) -> tuple[Shop, bool, str]:
    """Sartaroshxona yaratadi (darhol tasdiqlangan) va egasini biriktiradi."""
    owner, created, temp = staff_user(owner_data.get("phone", ""), owner_data.get("first_name", ""),
                                      owner_data.get("last_name", ""), owner_data.get("password", ""), "owner")
    shop = Shop(owner=owner, is_approved=True, is_active=True, **data)
    shop.full_clean(exclude=["owner"])
    shop.save()
    return shop, created, temp


@transaction.atomic
def create_master(shop: Shop, data: dict) -> tuple[Master, bool, str]:
    """Shu sartaroshxonaga usta qo'shadi. Odatiy jadval: dushanba–shanba, sartaroshxona ish vaqtida."""
    user, created, temp = staff_user(data.get("phone", ""), data.get("first_name", ""), data.get("last_name", ""),
                                     data.get("password", ""), "master")
    if Master.objects.filter(user=user).exists():
        raise AdminError("Bu foydalanuvchi allaqachon usta sifatida ro'yxatdan o'tgan")
    if user.id == shop.owner_id:
        raise AdminError("Sartaroshxona egasini usta qilib bo'lmaydi (alohida raqam kerak)")
    percent = int(data.get("commission_percent", 50))
    if not 0 <= percent <= 100:
        raise AdminError("Komissiya 0 dan 100 gacha bo'lishi kerak")
    master = Master.objects.create(user=user, shop=shop, bio=data.get("bio", ""), commission_percent=percent)
    for weekday in range(6):
        WorkSchedule.objects.create(master=master, weekday=weekday, start_time=shop.opens_at, end_time=shop.closes_at)
    return master, created, temp
