"""Egasi statistikasi va mijozlar bazasi."""
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.bookings.models import Booking
from apps.services.models import Service

from .base import BookingTestBase, make_user


class OwnerStatsClientsTests(BookingTestBase):
    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.service2 = Service.objects.create(shop=self.shop, name="Soqol", price=30000, duration_minutes=20)

    def add(self, client, service, days_ago, status, price=None):
        start = timezone.now() - timedelta(days=days_ago)
        return Booking.objects.create(
            client=client, master=self.master, service=service, start_time=start,
            end_time=start + timedelta(minutes=30), price=price if price is not None else service.price,
            status=status,
        )

    def seed(self):
        C = Booking.Status
        self.add(self.client_user, self.service, 10, C.COMPLETED)
        self.add(self.client_user, self.service, 3, C.COMPLETED)
        self.add(self.client_user, self.service2, 2, C.COMPLETED)
        self.add(self.other_client, self.service, 4, C.NO_SHOW)
        self.add(self.other_client, self.service, 1, C.CANCELLED)

    def test_stats_revenue_and_top_service(self):
        self.seed()
        self.api.force_authenticate(self.owner)
        data = self.api.get(reverse("insights-stats"), {"shop": self.shop.id, "days": 30}).json()
        self.assertEqual(data["total_bookings"], 5)
        self.assertEqual(data["completed"], 3)
        self.assertEqual(data["revenue"], 50000 + 50000 + 30000)
        self.assertEqual(data["average_check"], round(130000 / 3))
        self.assertEqual(data["top_services"][0]["service"], "Soch olish")
        self.assertEqual(data["top_services"][0]["bookings"], 3)  # bekor qilingan hisobga kirmaydi
        self.assertEqual(data["by_status"]["no_show"], 1)
        self.assertEqual(data["no_show_rate"], 0.2)
        self.assertEqual(data["cancel_rate"], 0.2)
        self.assertEqual(data["masters"][0]["revenue"], 130000)
        self.assertTrue(data["busiest_hours"])

    def test_stats_period_excludes_old_bookings(self):
        self.seed()
        self.add(self.client_user, self.service, 100, Booking.Status.COMPLETED)
        self.api.force_authenticate(self.owner)
        data = self.api.get(reverse("insights-stats"), {"shop": self.shop.id, "days": 30}).json()
        self.assertEqual(data["total_bookings"], 5)

    def test_stats_empty_shop(self):
        self.api.force_authenticate(self.owner)
        data = self.api.get(reverse("insights-stats"), {"shop": self.shop.id}).json()
        self.assertEqual(data["revenue"], 0)
        self.assertEqual(data["average_check"], 0)
        self.assertEqual(data["top_services"], [])

    def test_clients_list_and_favorites(self):
        self.seed()
        self.api.force_authenticate(self.owner)
        data = self.api.get(reverse("insights-clients"), {"shop": self.shop.id, "ordering": "visits"}).json()
        self.assertEqual(data["count"], 2)
        top = data["clients"][0]
        self.assertEqual(top["phone"], self.client_user.phone)
        self.assertEqual(top["visits"], 3)
        self.assertEqual(top["total_spent"], 130000)
        self.assertEqual(top["favorite_service"]["name"], "Soch olish")
        self.assertEqual(top["favorite_master"]["name"], "Jasur")
        other = data["clients"][1]
        self.assertEqual(other["no_shows"], 1)
        self.assertEqual(other["cancelled"], 1)
        self.assertIsNone(other["favorite_master"])

    def test_clients_search(self):
        self.seed()
        self.api.force_authenticate(self.owner)
        data = self.api.get(reverse("insights-clients"), {"shop": self.shop.id, "search": "boshqa"}).json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["clients"][0]["phone"], self.other_client.phone)

    def test_client_detail_history(self):
        self.seed()
        self.api.force_authenticate(self.owner)
        url = reverse("insights-client-detail", args=[self.client_user.id])
        data = self.api.get(url, {"shop": self.shop.id}).json()
        self.assertEqual(len(data["history"]), 3)
        self.assertGreater(data["history"][0]["date"], data["history"][-1]["date"])  # yangisi birinchi

    def test_client_detail_unknown_client_404(self):
        self.api.force_authenticate(self.owner)
        stranger = make_user("+998900000077", "Begona")
        url = reverse("insights-client-detail", args=[stranger.id])
        self.assertEqual(self.api.get(url, {"shop": self.shop.id}).status_code, 404)

    def test_other_owner_and_client_forbidden(self):
        self.seed()
        other_owner = make_user("+998900000099", "Boshqa egasi", "owner")
        for name in ("insights-stats", "insights-clients"):
            self.api.force_authenticate(other_owner)
            self.assertEqual(self.api.get(reverse(name), {"shop": self.shop.id}).status_code, 404)
            self.api.force_authenticate(self.client_user)
            self.assertEqual(self.api.get(reverse(name), {"shop": self.shop.id}).status_code, 403)

    def test_shop_param_required(self):
        self.api.force_authenticate(self.owner)
        self.assertEqual(self.api.get(reverse("insights-stats")).status_code, 400)
