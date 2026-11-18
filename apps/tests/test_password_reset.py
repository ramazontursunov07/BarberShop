import re
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.users.models import User

REQ = "/api/users/password-reset/request/"
CONF = "/api/users/password-reset/confirm/"
SEND = "apps.users.password_reset.send_telegram"


class PasswordResetTests(TestCase):
    def setUp(self):
        cache.clear()
        self.api = APIClient()
        self.user = User.objects.create_user(phone="+998901234567", password="EskiParol123", first_name="Ali", telegram_id=555)

    def _request_code(self, phone="+998901234567"):
        with mock.patch(SEND, return_value=True) as send:
            resp = self.api.post(REQ, {"phone": phone}, format="json")
        return resp, send

    def _code(self, send):
        return re.search(r"\b(\d{6})\b", send.call_args.args[1]).group(1)

    def test_full_flow_changes_password(self):
        resp, send = self._request_code()
        self.assertEqual(resp.status_code, 200)
        send.assert_called_once()
        self.assertEqual(send.call_args.args[0], 555)
        code = self._code(send)
        resp = self.api.post(CONF, {"phone": "+998901234567", "code": code, "new_password": "YangiParol456"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("YangiParol456"))
        # kod bir marta ishlaydi
        again = self.api.post(CONF, {"phone": "+998901234567", "code": code, "new_password": "Boshqa789012"}, format="json")
        self.assertEqual(again.status_code, 400)

    def test_phone_format_is_normalized(self):
        resp, send = self._request_code("998 90 123-45-67")
        self.assertEqual(resp.status_code, 200)
        send.assert_called_once()

    def test_unknown_phone_gets_same_reply_and_no_message(self):
        ok, _ = self._request_code()
        cache.clear()
        resp, send = self._request_code("+998900000000")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), ok.json())
        send.assert_not_called()

    def test_user_without_telegram_gets_nothing(self):
        User.objects.filter(pk=self.user.pk).update(telegram_id=None)
        resp, send = self._request_code()
        self.assertEqual(resp.status_code, 200)
        send.assert_not_called()

    def test_blocked_bot_gets_nothing(self):
        User.objects.filter(pk=self.user.pk).update(telegram_blocked=True)
        _, send = self._request_code()
        send.assert_not_called()

    def test_resend_cooldown(self):
        self._request_code()
        _, send = self._request_code()
        send.assert_not_called()

    def test_failed_send_allows_retry(self):
        with mock.patch(SEND, return_value=False):
            self.api.post(REQ, {"phone": "+998901234567"}, format="json")
        _, send = self._request_code()
        send.assert_called_once()

    def test_wrong_code_rejected_and_locks_after_five(self):
        _, send = self._request_code()
        good = self._code(send)
        bad = "000000" if good != "000000" else "111111"
        for _ in range(5):
            r = self.api.post(CONF, {"phone": "+998901234567", "code": bad, "new_password": "YangiParol456"}, format="json")
            self.assertEqual(r.status_code, 400)
        # to'g'ri kod ham endi ishlamaydi: kod bekor bo'lgan
        r = self.api.post(CONF, {"phone": "+998901234567", "code": good, "new_password": "YangiParol456"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("EskiParol123"))

    def test_confirm_without_request_fails(self):
        r = self.api.post(CONF, {"phone": "+998901234567", "code": "123456", "new_password": "YangiParol456"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_weak_password_rejected_and_code_kept(self):
        _, send = self._request_code()
        code = self._code(send)
        r = self.api.post(CONF, {"phone": "+998901234567", "code": code, "new_password": "12345678"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("new_password", r.json())
        r = self.api.post(CONF, {"phone": "+998901234567", "code": code, "new_password": "YangiParol456"}, format="json")
        self.assertEqual(r.status_code, 200)

    def test_old_tokens_revoked_after_reset(self):
        login = self.api.post("/api/users/login/", {"phone": "+998901234567", "password": "EskiParol123"}, format="json").json()
        _, send = self._request_code()
        self.api.post(CONF, {"phone": "+998901234567", "code": self._code(send), "new_password": "YangiParol456"}, format="json")
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {login['access']}")
        self.assertEqual(c.get("/api/users/me/").status_code, 401)
        new = self.api.post("/api/users/login/", {"phone": "+998901234567", "password": "YangiParol456"}, format="json")
        self.assertEqual(new.status_code, 200)

    def test_code_is_not_stored_in_plain_text(self):
        _, send = self._request_code()
        code = self._code(send)
        self.assertNotIn(code, repr(cache.get(f"pwreset:{self.user.id}")))
        