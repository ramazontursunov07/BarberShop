"""Bron testlari uchun ortak yordamchilar (boshqa app testlari ham ishlatadi)."""
from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.masters.models import Master, WorkSchedule
from apps.services.models import Service
from apps.shops.models import Shop

from apps.bookings.models import Booking

User = get_user_model()


def make_user(phone, first_name, role="client"):
    return User.objects.create_user(phone=phone, password="pass12345", first_name=first_name, role=role)


class BookingTestBase(TestCase):
    def setUp(self):
        self.owner = make_user("+998900000001", "Egasi", "owner")
        self.master_user = make_user("+998900000002", "Jasur", "master")
        self.client_user = make_user("+998900000004", "Mijoz")
        self.other_client = make_user("+998900000005", "Boshqa")

        self.shop = Shop.objects.create(
            owner=self.owner, name="Demo", phone="+998900000001", city="Toshkent",
            address="Manzil 1", opens_at=time(9, 0), closes_at=time(19, 0),
            is_approved=True, is_active=True,
        )
        self.service = Service.objects.create(shop=self.shop, name="Soch olish", price=50000, duration_minutes=30)
        self.master = Master.objects.create(user=self.master_user, shop=self.shop)
        for weekday in range(7):
            WorkSchedule.objects.create(
                master=self.master, weekday=weekday, start_time=time(9, 0), end_time=time(18, 0)
            )

    def make_booking(self, client=None, hours_from_now=24, status=Booking.Status.PENDING):
        start = timezone.now() + timedelta(hours=hours_from_now)
        return Booking.objects.create(
            client=client or self.client_user, master=self.master, service=self.service,
            start_time=start, end_time=start + timedelta(minutes=30),
            price=self.service.price, status=status,
        )
