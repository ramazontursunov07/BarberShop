"""Egasi o'z ustalarini qo'shadi va boshqaradi."""
from rest_framework.test import APIClient

from apps.masters.models import Master
from apps.tests.base import BookingTestBase, make_user
from apps.users.models import User


class TeamTests(BookingTestBase):
    def auth(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    def post(self, user, **extra):
        body = {"shop": self.shop.id, "phone": "+998911112233", "first_name": "Aziz", **extra}
        return self.auth(user).post("/api/masters/my/team/", body, format="json")

    def test_owner_adds_new_master(self):
        res = self.post(self.owner, commission_percent=40)
        self.assertEqual(res.status_code, 201, res.content)
        self.assertTrue(res.data["temp_password"])
        master = Master.objects.get(user__phone="+998911112233")
        self.assertEqual(master.shop_id, self.shop.id)
        self.assertEqual(master.commission_percent, 40)
        self.assertEqual(master.user.role, "master")
        self.assertEqual(master.schedules.count(), 6)  # dushanba-shanba

    def test_owner_chooses_password(self):
        res = self.post(self.owner, password="parol12345")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["temp_password"], "")
        self.assertTrue(User.objects.get(phone="+998911112233").check_password("parol12345"))

    def test_existing_account_cannot_be_converted_by_owner(self):
        res = self.post(self.owner, phone=self.other_client.phone)
        self.assertEqual(res.status_code, 400)
        self.other_client.refresh_from_db()
        self.assertEqual(self.other_client.role, "client")
        self.assertFalse(Master.objects.filter(user=self.other_client).exists())

    def test_other_owner_cannot_add_to_my_shop(self):
        other = make_user("+998900000099", "Boshqa", "owner")
        res = self.post(other)
        self.assertEqual(res.status_code, 404)
        self.assertFalse(Master.objects.filter(user__phone="+998911112233").exists())

    def test_client_and_master_forbidden(self):
        self.assertEqual(self.post(self.client_user).status_code, 403)
        self.assertEqual(self.post(self.master_user).status_code, 403)

    def test_bad_phone_and_missing_name(self):
        self.assertEqual(self.post(self.owner, phone="123").status_code, 400)
        self.assertEqual(self.post(self.owner, first_name="").status_code, 400)

    def test_list_shows_phone_commission_and_upcoming(self):
        self.make_booking()
        res = self.auth(self.owner).get(f"/api/masters/my/team/?shop={self.shop.id}")
        self.assertEqual(res.status_code, 200)
        row = res.data[0]
        self.assertEqual(row["phone"], self.master_user.phone)
        self.assertEqual(row["upcoming_bookings"], 1)
        self.assertIn("commission_percent", row)

    def test_list_other_shop_is_404_and_requires_shop(self):
        other = make_user("+998900000099", "Boshqa", "owner")
        self.assertEqual(self.auth(other).get(f"/api/masters/my/team/?shop={self.shop.id}").status_code, 404)
        self.assertEqual(self.auth(self.owner).get("/api/masters/my/team/").status_code, 400)

    def test_owner_deactivates_and_sets_commission(self):
        res = self.auth(self.owner).patch(f"/api/masters/my/{self.master.id}/",
                                          {"is_active": False, "commission_percent": 30}, format="json")
        self.assertEqual(res.status_code, 200)
        self.master.refresh_from_db()
        self.assertFalse(self.master.is_active)
        self.assertEqual(self.master.commission_percent, 30)
