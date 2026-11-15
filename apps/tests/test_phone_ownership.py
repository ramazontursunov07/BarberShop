"""Telefon raqamni "egallab olish" va parol o'rnatish."""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.users.models import User

SECRET = "test-secret"
PHONE = "+998901234567"


def login(phone, password):
    return APIClient().post("/api/users/login/", {"phone": phone, "password": password}, format="json")


def authed(access):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


@override_settings(TELEGRAM_BOT_SECRET=SECRET)
class PhoneSquattingTests(TestCase):
    def bot_auth(self, telegram_id, phone):
        return APIClient().post(
            "/api/users/telegram/auth/", {"telegram_id": telegram_id, "phone": phone},
            format="json", HTTP_X_BOT_SECRET=SECRET,
        )

    def test_linking_unverified_account_revokes_password_and_tokens(self):
        # Hujumchi qurbonning raqami bilan oldindan akkaunt ochadi
        User.objects.create_user(phone=PHONE, password="attacker-pass1", first_name="X")
        attacker_access = login(PHONE, "attacker-pass1").json()["access"]
        self.assertEqual(authed(attacker_access).get("/api/users/me/").status_code, 200)

        # Haqiqiy egasi botda o'z kontaktini yuboradi
        resp = self.bot_auth(777, PHONE)
        self.assertEqual(resp.status_code, 200)

        user = User.objects.get(phone=PHONE)
        self.assertEqual(user.telegram_id, 777)
        self.assertTrue(user.is_phone_verified)
        self.assertFalse(user.has_usable_password())
        # hujumchining paroli va eski tokeni endi ishlamaydi
        self.assertEqual(login(PHONE, "attacker-pass1").status_code, 401)
        self.assertEqual(authed(attacker_access).get("/api/users/me/").status_code, 401)
        # egasining yangi tokeni ishlaydi
        self.assertEqual(authed(resp.json()["access"]).get("/api/users/me/").status_code, 200)

    def test_verified_account_keeps_password_when_linking(self):
        # Masalan, admin panel yaratgan (raqami tasdiqlangan) akkaunt
        User.objects.create_user(phone=PHONE, password="owner-pass123", first_name="Egasi", is_phone_verified=True)
        self.assertEqual(self.bot_auth(777, PHONE).status_code, 200)
        self.assertEqual(login(PHONE, "owner-pass123").status_code, 200)


class SetPasswordTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone=PHONE, password="old-pass-123", first_name="Ali")
        self.access = login(PHONE, "old-pass-123").json()["access"]

    def post(self, payload, access=None):
        return authed(access or self.access).post("/api/users/set-password/", payload, format="json")

    def test_requires_login(self):
        resp = APIClient().post("/api/users/set-password/", {"new_password": "new-pass-123"}, format="json")
        self.assertEqual(resp.status_code, 401)

    def test_wrong_current_password_rejected(self):
        resp = self.post({"current_password": "xato-parol", "new_password": "new-pass-123"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("current_password", resp.json())

    def test_weak_password_rejected(self):
        resp = self.post({"current_password": "old-pass-123", "new_password": "12345678"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("new_password", resp.json())

    def test_change_password_revokes_old_token_and_returns_new_ones(self):
        resp = self.post({"current_password": "old-pass-123", "new_password": "new-pass-123"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(login(PHONE, "old-pass-123").status_code, 401)
        self.assertEqual(login(PHONE, "new-pass-123").status_code, 200)
        self.assertEqual(authed(self.access).get("/api/users/me/").status_code, 401)
        self.assertEqual(authed(resp.json()["access"]).get("/api/users/me/").status_code, 200)

    def test_telegram_only_account_sets_first_password_without_current(self):
        tg_user = User.objects.create_user(phone="+998909999999", first_name="Vali", telegram_id=5, is_phone_verified=True)
        self.assertFalse(tg_user.has_usable_password())
        client = APIClient()
        client.force_authenticate(tg_user)
        me = client.get("/api/users/me/").json()
        self.assertFalse(me["has_password"])
        resp = client.post("/api/users/set-password/", {"new_password": "first-pass-123"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(login("+998909999999", "first-pass-123").status_code, 200)
