"""Telegram Mini App autentifikatsiyasi."""
import hashlib
import hmac
import json
import os
import time
import unittest
from unittest import mock
from urllib.parse import urlencode

from django.urls import reverse
from rest_framework.test import APIClient

from apps.users.webapp_auth import InitDataError, validate_init_data

from .base import BookingTestBase

TOKEN = "123456:TEST-TOKEN"


def make_init_data(user_id=777, token=TOKEN, auth_date=None, tamper=False):
    fields = {
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
        "query_id": "AAH",
        "user": json.dumps({"id": user_id, "first_name": "Ali"}, separators=(",", ":")),
    }
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if tamper:
        fields["user"] = json.dumps({"id": 1}, separators=(",", ":"))
    return urlencode(fields)


class ValidateInitDataTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(validate_init_data(make_init_data(), TOKEN)["id"], 777)

    def test_wrong_token(self):
        with self.assertRaises(InitDataError):
            validate_init_data(make_init_data(), "999:OTHER")

    def test_tampered(self):
        with self.assertRaises(InitDataError):
            validate_init_data(make_init_data(tamper=True), TOKEN)

    def test_expired(self):
        old = int(time.time()) - 3 * 24 * 3600
        with self.assertRaises(InitDataError):
            validate_init_data(make_init_data(auth_date=old), TOKEN)

    def test_missing_hash_and_empty(self):
        for bad in ("", "auth_date=1&user=%7B%7D"):
            with self.assertRaises(InitDataError):
                validate_init_data(bad, TOKEN)

    def test_no_bot_token(self):
        with self.assertRaises(InitDataError):
            validate_init_data(make_init_data(), "")


class WebAppEndpointTests(BookingTestBase):
    def setUp(self):
        super().setUp()
        self.api = APIClient()
        patcher = mock.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": TOKEN})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_unlinked_telegram_gets_404(self):
        r = self.api.post(reverse("telegram-webapp"), {"init_data": make_init_data()}, format="json")
        self.assertEqual(r.status_code, 404)

    def test_bad_signature_gets_403(self):
        r = self.api.post(reverse("telegram-webapp"), {"init_data": make_init_data(tamper=True)}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_link_then_login(self):
        self.api.force_authenticate(self.client_user)
        r = self.api.post(reverse("telegram-link"), {"init_data": make_init_data()}, format="json")
        self.assertEqual(r.status_code, 200)
        self.client_user.refresh_from_db()
        self.assertEqual(self.client_user.telegram_id, 777)

        anon = APIClient()
        r = anon.post(reverse("telegram-webapp"), {"init_data": make_init_data()}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("access", r.json())
        self.assertIn("refresh", r.json())

    def test_cannot_link_telegram_owned_by_another_user(self):
        self.other_client.telegram_id = 777
        self.other_client.save()
        self.api.force_authenticate(self.client_user)
        r = self.api.post(reverse("telegram-link"), {"init_data": make_init_data()}, format="json")
        self.assertEqual(r.status_code, 409)

    def test_link_requires_login(self):
        r = self.api.post(reverse("telegram-link"), {"init_data": make_init_data()}, format="json")
        self.assertEqual(r.status_code, 401)
