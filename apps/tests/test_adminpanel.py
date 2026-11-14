"""Admin paneli (sartaroshxona/usta qo'shish) va usta sahifasi API'lari."""
from datetime import datetime, timedelta

from django.utils import timezone
from rest_framework.test import APIClient

from apps.bookings.models import Booking
from apps.bookings.services import SHOP_TZ
from apps.masters.models import Master
from apps.shops.models import Shop
from apps.users.models import User

from .base import BookingTestBase, make_user

SHOP = {"name": "Yangi Barber", "phone": "+998901234567", "city": "Toshkent", "address": "Chilonzor 5",
        "opens_at": "09:00", "closes_at": "20:00"}


class AdminBase(BookingTestBase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser(phone="+998900000099", password="pass12345", first_name="Admin")
        self.api = APIClient()
        self.api.force_authenticate(self.admin)


class PermissionTests(AdminBase):
    def test_only_admin(self):
        for user in (self.owner, self.master_user, self.client_user):
            c = APIClient()
            c.force_authenticate(user)
            self.assertEqual(c.get("/api/admin/shops/").status_code, 403, user.role)
            self.assertEqual(c.post("/api/admin/shops/", {}, format="json").status_code, 403)
        self.assertEqual(APIClient().get("/api/admin/stats/").status_code, 401)

    def test_superuser_has_admin_role(self):
        self.assertEqual(self.admin.role, "admin")


class ShopTests(AdminBase):
    def test_create_with_new_owner_returns_temp_password_once(self):
        r = self.api.post("/api/admin/shops/", {"shop": SHOP, "owner": {"phone": "+998 90 777-66-55", "first_name": "Ali"}},
                          format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data["owner_created"])
        temp = r.data["temp_password"]
        self.assertGreaterEqual(len(temp), 8)
        shop = Shop.objects.get(pk=r.data["shop"]["id"])
        self.assertTrue(shop.is_approved)
        self.assertEqual((shop.owner.phone, shop.owner.role), ("+998907776655", "owner"))
        # egasi shu parol bilan kira oladi
        login = APIClient().post("/api/users/login/", {"phone": "+998907776655", "password": temp}, format="json")
        self.assertEqual(login.status_code, 200)
        # ro'yxatda ko'rinadi
        listed = self.api.get("/api/admin/shops/?q=Yangi")
        self.assertEqual([s["name"] for s in listed.data["results"]], ["Yangi Barber"])

    def test_existing_client_is_promoted_and_password_untouched(self):
        old_hash = self.client_user.password
        r = self.api.post("/api/admin/shops/", {"shop": SHOP, "owner": {"phone": self.client_user.phone}}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertFalse(r.data["owner_created"])
        self.assertEqual(r.data["temp_password"], "")
        self.client_user.refresh_from_db()
        self.assertEqual((self.client_user.role, self.client_user.password), ("owner", old_hash))

    def test_master_cannot_become_owner(self):
        r = self.api.post("/api/admin/shops/", {"shop": SHOP, "owner": {"phone": self.master_user.phone}}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Shop.objects.filter(name="Yangi Barber").exists())

    def test_validation(self):
        bad = dict(SHOP, opens_at="21:00", closes_at="09:00")
        self.assertEqual(self.api.post("/api/admin/shops/", {"shop": bad, "owner": {"phone": "+998901112200", "first_name": "A"}},
                                       format="json").status_code, 400)
        self.assertEqual(self.api.post("/api/admin/shops/", {"shop": SHOP, "owner": {"phone": "12345", "first_name": "A"}},
                                       format="json").status_code, 400)
        self.assertEqual(User.objects.filter(phone="+998901112200").count(), 0)  # tranzaksiya ortga qaytdi

    def test_approve_and_deactivate(self):
        s = Shop.objects.create(owner=self.owner, name="Kutayotgan", phone="+998900000009", city="T", address="a",
                                opens_at="09:00", closes_at="18:00")
        self.assertEqual(len(self.api.get("/api/admin/shops/?state=pending").data["results"]), 1)
        self.assertEqual(self.api.get("/api/admin/stats/").data["shops_pending"], 1)
        r = self.api.patch(f"/api/admin/shops/{s.id}/", {"is_approved": True}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(Shop.objects.get(pk=s.id).is_approved)
        self.api.patch(f"/api/admin/shops/{s.id}/", {"is_active": False, "name": "Yopildi"}, format="json")
        s.refresh_from_db()
        self.assertEqual((s.is_active, s.name), (False, "Yopildi"))
        self.assertEqual(len(self.api.get("/api/admin/shops/?state=inactive").data["results"]), 1)


class MasterTests(AdminBase):
    def test_create_master_with_default_schedule(self):
        r = self.api.post(f"/api/admin/shops/{self.shop.id}/masters/",
                          {"phone": "+998905550011", "first_name": "Bobur", "commission_percent": 40}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        m = Master.objects.get(pk=r.data["master"]["id"])
        self.assertEqual((m.user.role, m.shop_id, m.commission_percent), ("master", self.shop.id, 40))
        self.assertEqual(m.schedules.count(), 6)
        self.assertEqual(len(self.api.get(f"/api/admin/shops/{self.shop.id}/masters/").data), 2)

    def test_duplicates_and_owner_rejected(self):
        url = f"/api/admin/shops/{self.shop.id}/masters/"
        self.assertEqual(self.api.post(url, {"phone": self.master_user.phone}, format="json").status_code, 400)
        self.assertEqual(self.api.post(url, {"phone": self.owner.phone}, format="json").status_code, 400)

    def test_client_promoted_to_master(self):
        r = self.api.post(f"/api/admin/shops/{self.shop.id}/masters/", {"phone": self.client_user.phone}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.client_user.refresh_from_db()
        self.assertEqual(self.client_user.role, "master")

    def test_patch_master(self):
        r = self.api.patch(f"/api/admin/masters/{self.master.id}/", {"is_active": False, "commission_percent": 30}, format="json")
        self.assertEqual(r.status_code, 200)
        self.master.refresh_from_db()
        self.assertEqual((self.master.is_active, self.master.commission_percent), (False, 30))


class UserTests(AdminBase):
    def test_search_and_block(self):
        r = self.api.get("/api/admin/users/?q=Mijoz")
        self.assertEqual([u["id"] for u in r.data["results"]], [self.client_user.id])
        self.assertEqual(self.api.patch(f"/api/admin/users/{self.client_user.id}/", {"is_active": False}, format="json").status_code, 200)
        self.client_user.refresh_from_db()
        self.assertFalse(self.client_user.is_active)
        self.assertEqual(self.api.patch(f"/api/admin/users/{self.admin.id}/", {"is_active": False}, format="json").status_code, 400)


class MasterMeTests(BookingTestBase):
    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.api.force_authenticate(self.master_user)

    def test_profile(self):
        r = self.api.get("/api/masters/me/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.data["id"], r.data["shop_name"], r.data["commission_percent"]), (self.master.id, "Demo", 50))
        self.assertEqual(len(r.data["schedule"]), 7)

    def test_others_forbidden(self):
        for user in (self.owner, self.client_user):
            c = APIClient()
            c.force_authenticate(user)
            self.assertEqual(c.get("/api/masters/me/").status_code, 403)
            self.assertEqual(c.get("/api/masters/me/earnings/").status_code, 403)

    def test_earnings(self):
        self.master.commission_percent = 40
        self.master.save()
        start = timezone.now() - timedelta(hours=3)
        for price, pm in ((100000, "cash"), (50000, "card")):
            Booking.objects.create(client=self.client_user, master=self.master, service=self.service, start_time=start,
                                   end_time=start + timedelta(minutes=30), price=price,
                                   status=Booking.Status.COMPLETED, payment_method=pm)
        # boshqa ustaning bron'i hisobga kirmasligi kerak
        other = Master.objects.create(user=make_user("+998900000077", "Boshqa usta", "master"), shop=self.shop)
        Booking.objects.create(client=self.client_user, master=other, service=self.service, start_time=start,
                               end_time=start + timedelta(minutes=30), price=999, status=Booking.Status.COMPLETED)
        r = self.api.get("/api/masters/me/earnings/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data["revenue"], r.data["cash"], r.data["card"], r.data["master_share"]),
                         (150000, 100000, 50000, 60000))
        self.assertEqual(r.data["days"][0]["bookings"], 2)
        self.assertEqual(self.api.get("/api/masters/me/earnings/?from=bad").status_code, 400)

    def test_master_marks_own_day_off(self):
        day = (datetime.now(SHOP_TZ).date() + timedelta(days=2)).isoformat()
        self.assertEqual(self.api.post(f"/api/masters/{self.master.id}/days-off/", {"date": day}).status_code, 201)
        self.assertEqual([d["date"] for d in self.api.get("/api/masters/me/").data["days_off"]], [day])
