from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.users.models import User
from apps.users.telegram import normalize_phone

SECRET = "test-secret"
URL = "/api/users/telegram/auth/"


class NormalizePhoneTests(TestCase):
    def test_valid_formats(self):
        self.assertEqual(normalize_phone("+998901234567"), "+998901234567")
        self.assertEqual(normalize_phone("998901234567"), "+998901234567")
        self.assertEqual(normalize_phone("+998 90 123-45-67"), "+998901234567")

    def test_invalid(self):
        self.assertIsNone(normalize_phone("+79001234567"))
        self.assertIsNone(normalize_phone("90123"))
        self.assertIsNone(normalize_phone(""))
        self.assertIsNone(normalize_phone(None))


@override_settings(TELEGRAM_BOT_SECRET=SECRET)
class TelegramAuthTests(TestCase):
    def setUp(self):
        self.api = APIClient()

    def post(self, payload, secret=SECRET):
        headers = {"HTTP_X_BOT_SECRET": secret} if secret is not None else {}
        return self.api.post(URL, payload, format="json", **headers)

    def test_without_secret_forbidden(self):
        self.assertEqual(self.post({"telegram_id": 1}, secret=None).status_code, 403)

    def test_wrong_secret_forbidden(self):
        self.assertEqual(self.post({"telegram_id": 1}, secret="xato").status_code, 403)

    @override_settings(TELEGRAM_BOT_SECRET="")
    def test_disabled_when_secret_not_configured(self):
        self.assertEqual(self.post({"telegram_id": 1}, secret="").status_code, 403)

    def test_unknown_telegram_without_phone_is_404(self):
        self.assertEqual(self.post({"telegram_id": 555}).status_code, 404)

    def test_phone_creates_user_and_token_works(self):
        resp = self.post({"telegram_id": 555, "phone": "998901234567", "first_name": "Ali"})
        self.assertEqual(resp.status_code, 200)
        user = User.objects.get(phone="+998901234567")
        self.assertEqual(user.telegram_id, 555)
        self.assertEqual(user.role, "client")
        self.assertTrue(user.is_phone_verified)
        self.assertFalse(user.has_usable_password())

        me = APIClient()
        me.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.json()['access']}")
        self.assertEqual(me.get("/api/users/me/").json()["phone"], "+998901234567")

    def test_second_call_without_phone_returns_token(self):
        self.post({"telegram_id": 555, "phone": "+998901234567"})
        resp = self.post({"telegram_id": 555})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("access", resp.json())

    def test_existing_user_gets_linked(self):
        user = User.objects.create_user(phone="+998901234567", password="pass12345", first_name="Vali")
        resp = self.post({"telegram_id": 777, "phone": "+998901234567"})
        self.assertEqual(resp.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.telegram_id, 777)
        self.assertEqual(User.objects.count(), 1)

    def test_non_uzbek_phone_rejected(self):
        self.assertEqual(self.post({"telegram_id": 1, "phone": "+79001234567"}).status_code, 400)

    def test_phone_already_linked_to_other_telegram_conflicts(self):
        self.post({"telegram_id": 555, "phone": "+998901234567"})
        self.assertEqual(self.post({"telegram_id": 999, "phone": "+998901234567"}).status_code, 409)

    def test_telegram_already_linked_to_other_phone_conflicts(self):
        self.post({"telegram_id": 555, "phone": "+998901234567"})
        self.assertEqual(self.post({"telegram_id": 555, "phone": "+998909999999"}).status_code, 409)

    def test_inactive_user_forbidden(self):
        self.post({"telegram_id": 555, "phone": "+998901234567"})
        User.objects.filter(telegram_id=555).update(is_active=False)
        self.assertEqual(self.post({"telegram_id": 555}).status_code, 403)
