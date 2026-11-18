from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.users.throttles import AuthThrottle


class ClientIpBehindProxyTests(TestCase):
    """Caddy orqasida har bir mijoz o'z IP'si bo'yicha hisoblanishi kerak (umumiy bitta Caddy IP bo'yicha emas)."""

    def setUp(self):
        cache.clear()

    def test_throttle_ident_uses_forwarded_ip(self):
        from rest_framework.request import Request
        from django.test import RequestFactory
        from rest_framework import settings as drf_settings
        from rest_framework.settings import api_settings

        req = RequestFactory().get("/", HTTP_X_FORWARDED_FOR="203.0.113.7", REMOTE_ADDR="172.18.0.5")
        with override_settings(REST_FRAMEWORK={**api_settings.user_settings, "NUM_PROXIES": 1}):
            api_settings.reload()
            try:
                ident = AuthThrottle().get_ident(Request(req))
            finally:
                api_settings.reload()
        self.assertEqual(ident, "203.0.113.7")
