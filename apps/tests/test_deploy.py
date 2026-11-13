"""Production tayyorligi: health, login throttle, DATABASE_URL, Celery jadvali."""
from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from config.settings import _database_from_url


class HealthTests(TestCase):
    def test_ok(self):
        r = self.client.get("/health/")
        self.assertEqual((r.status_code, r.json()), (200, {"status": "ok"}))

    def test_db_down(self):
        with patch("config.health.connection.cursor", side_effect=Exception("boom")):
            self.assertEqual(self.client.get("/health/").status_code, 503)


class AuthThrottleTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_login_is_rate_limited(self):
        from rest_framework.settings import api_settings
        rates = dict(api_settings.DEFAULT_THROTTLE_RATES, auth="3/min")
        with patch.object(api_settings, "DEFAULT_THROTTLE_RATES", rates, create=True), \
                patch("apps.users.throttles.AuthThrottle.THROTTLE_RATES", rates):
            api = APIClient()
            codes = [api.post("/api/users/login/", {"phone": "+998900000000", "password": "x"}).status_code
                     for _ in range(5)]
        self.assertEqual(codes[:3], [401, 401, 401])
        self.assertEqual(codes[-1], 429)


class DatabaseUrlTests(SimpleTestCase):
    def test_parse_postgres(self):
        d = _database_from_url("postgres://barber:p%40ss@db:5433/barber")
        self.assertEqual((d["ENGINE"], d["NAME"], d["USER"], d["PASSWORD"], d["HOST"], d["PORT"]),
                         ("django.db.backends.postgresql", "barber", "barber", "p@ss", "db", "5433"))

    def test_rejects_other_schemes(self):
        with self.assertRaises(RuntimeError):
            _database_from_url("mysql://u:p@h/d")


class CeleryScheduleTests(SimpleTestCase):
    def test_every_task_exists_and_runs_command(self):
        from config.celery import app
        from apps.ai import tasks
        for name, entry in app.conf.beat_schedule.items():
            fn = getattr(tasks, entry["task"].rsplit(".", 1)[1])
            with patch("apps.ai.tasks.call_command") as cc:
                fn()
            cc.assert_called_once_with(name.replace("-", "_"))
