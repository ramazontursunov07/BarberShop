from datetime import time

from rest_framework.test import APIClient

from apps.bookings.tests import BookingTestBase, make_user
from apps.shops.models import Shop

from .models import Service


class ServiceApiTests(BookingTestBase):
    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.other_owner = make_user("+998900000010", "Boshqa", "owner")
        self.other_shop = Shop.objects.create(
            owner=self.other_owner, name="Boshqa shop", phone="+998900000010", city="Toshkent",
            address="Manzil 2", opens_at=time(9, 0), closes_at=time(19, 0),
            is_approved=True, is_active=True,
        )

    def names(self, response):
        return {row["name"] for row in response.json()["results"]}

    def test_public_list_hides_inactive_and_unapproved(self):
        Service.objects.create(shop=self.shop, name="Nofaol", price=1000, duration_minutes=30, is_active=False)
        hidden_shop = Shop.objects.create(
            owner=self.other_owner, name="Tasdiqlanmagan", phone="+998900000011", city="Toshkent",
            address="Manzil 3", opens_at=time(9, 0), closes_at=time(19, 0), is_approved=False, is_active=True,
        )
        Service.objects.create(shop=hidden_shop, name="Yashirin", price=1000, duration_minutes=30)

        resp = self.api.get("/api/services/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.names(resp), {"Soch olish"})

    def test_filter_by_shop(self):
        Service.objects.create(shop=self.other_shop, name="Soqol", price=30000, duration_minutes=20)
        resp = self.api.get("/api/services/", {"shop": self.other_shop.id})
        self.assertEqual(self.names(resp), {"Soqol"})
        self.assertEqual(self.api.get("/api/services/", {"shop": "abc"}).status_code, 400)

    def test_owner_creates_service(self):
        self.api.force_authenticate(self.owner)
        resp = self.api.post(
            "/api/services/my/",
            {"shop": self.shop.id, "name": "Soqol", "price": 30000, "duration_minutes": 20},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(Service.objects.filter(shop=self.shop, name="Soqol").exists())

    def test_owner_cannot_create_for_foreign_shop(self):
        self.api.force_authenticate(self.owner)
        resp = self.api.post(
            "/api/services/my/",
            {"shop": self.other_shop.id, "name": "Soqol", "price": 30000, "duration_minutes": 20},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_client_cannot_use_owner_endpoints(self):
        self.api.force_authenticate(self.client_user)
        self.assertEqual(self.api.get("/api/services/my/").status_code, 403)

    def test_delete_is_soft(self):
        self.api.force_authenticate(self.owner)
        resp = self.api.delete(f"/api/services/my/{self.service.id}/")
        self.assertEqual(resp.status_code, 204)
        self.service.refresh_from_db()
        self.assertFalse(self.service.is_active)
        self.api.force_authenticate(None)
        self.assertEqual(self.names(self.api.get("/api/services/")), set())

    def test_other_owner_cannot_edit(self):
        self.api.force_authenticate(self.other_owner)
        resp = self.api.patch(f"/api/services/my/{self.service.id}/", {"price": 1}, format="json")
        self.assertEqual(resp.status_code, 404)
        