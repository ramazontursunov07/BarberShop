"""Insights: no-show xavfi, talab prognozi, dinamik narx, shaxsiy tavsiya, egasi API'si."""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.ai import services as ai
from apps.bookings.models import Booking
from apps.insights import demand, noshow, pricing
from apps.insights.models import PricingRule
from apps.insights.profile import client_profile

from .base import BookingTestBase, make_user

TZ = ZoneInfo("Asia/Tashkent")


class PricingTests(BookingTestBase):
    def test_apply_discount_rounds_to_thousand(self):
        self.assertEqual(pricing.apply_discount(50000, 20), 40000)
        self.assertEqual(pricing.apply_discount(45000, 15), 38000)
        self.assertEqual(pricing.apply_discount(50000, 0), 50000)

    def test_rule_applies_by_weekday_and_time_and_max_wins(self):
        PricingRule.objects.create(shop=self.shop, start_time=time(9, 0), end_time=time(12, 0), percent=10)
        PricingRule.objects.create(shop=self.shop, weekday=0, start_time=time(9, 0), end_time=time(11, 0), percent=25)
        monday_10 = datetime(2030, 1, 7, 10, 0, tzinfo=TZ)  # dushanba
        tuesday_10 = datetime(2030, 1, 8, 10, 0, tzinfo=TZ)
        monday_15 = datetime(2030, 1, 7, 15, 0, tzinfo=TZ)
        self.assertEqual(pricing.discount_percent(self.shop.id, monday_10), 25)
        self.assertEqual(pricing.discount_percent(self.shop.id, tuesday_10), 10)
        self.assertEqual(pricing.discount_percent(self.shop.id, monday_15), 0)

    def test_inactive_rule_ignored(self):
        PricingRule.objects.create(shop=self.shop, start_time=time(9, 0), end_time=time(18, 0), percent=30,
                                   is_active=False)
        self.assertEqual(pricing.discount_percent(self.shop.id, datetime(2030, 1, 7, 10, 0, tzinfo=TZ)), 0)

    def test_create_booking_uses_discounted_price_and_slots_show_it(self):
        PricingRule.objects.create(shop=self.shop, start_time=time(9, 0), end_time=time(18, 0), percent=20)
        day = (timezone.now().astimezone(TZ) + timedelta(days=2)).date().isoformat()
        best = ai.find_best_slots(self.client_user, self.service.id, day, master_id=self.master.id)
        first = best["suggestions"][0]
        self.assertEqual(first["price"], 40000)
        self.assertEqual(first["discount_percent"], 20)
        res = ai.create_booking(self.client_user, self.master.id, self.service.id, first["date"], first["start_time"])
        self.assertEqual(res["price"], 40000)
        self.assertEqual(int(Booking.objects.get(pk=res["booking_id"]).price), 40000)


class NoShowTests(BookingTestBase):
    def _history(self, client, completed, missed):
        base = timezone.now() - timedelta(days=60)
        for i in range(completed + missed):
            start = base + timedelta(days=i)
            Booking.objects.create(
                client=client, master=self.master, service=self.service, start_time=start,
                end_time=start + timedelta(minutes=30), price=50000,
                status=Booking.Status.COMPLETED if i < completed else Booking.Status.NO_SHOW)

    def test_new_client_is_low_risk(self):
        r = noshow.risk_score(self.client_user, self.shop.id, timezone.now() + timedelta(hours=5))
        self.assertEqual(r["level"], "low")

    def test_repeat_no_show_client_is_riskier_than_reliable_one(self):
        self._history(self.client_user, completed=0, missed=3)
        self._history(self.other_client, completed=5, missed=0)
        when = timezone.now() + timedelta(days=4)
        bad = noshow.risk_score(self.client_user, self.shop.id, when)
        good = noshow.risk_score(self.other_client, self.shop.id, when)
        self.assertGreater(bad["probability"], good["probability"])
        self.assertIn(bad["level"], ("medium", "high"))
        self.assertEqual(good["level"], "low")

    def test_far_ahead_booking_riskier_than_same_day(self):
        far = noshow.risk_score(self.client_user, self.shop.id, timezone.now() + timedelta(days=5))
        near = noshow.risk_score(self.client_user, self.shop.id, timezone.now() + timedelta(hours=2))
        self.assertGreater(far["probability"], near["probability"])

    def test_smoothed_rate(self):
        self.assertAlmostEqual(noshow.smoothed_rate(0, 0, 0.1), 0.1)
        self.assertGreater(noshow.smoothed_rate(2, 2, 0.1), noshow.smoothed_rate(1, 2, 0.1))


class DemandTests(BookingTestBase):
    def test_compute_demand_flags_shortage_and_quiet_hours(self):
        # 4 hafta, dushanba 10:00-11:00 da har hafta 2 ta bron bir vaqtda; ishlaydigan usta 1 ta
        mon = datetime(2030, 1, 7, 10, 0)
        intervals = [(mon + timedelta(weeks=w), mon + timedelta(weeks=w, hours=1)) for w in range(4)] * 2
        report = demand.compute_demand(intervals, {0: {10: 1, 11: 1}}, weeks=4)
        day = report["days"][0]
        row10 = next(r for r in day["hours"] if r["hour"] == 10)
        self.assertEqual(row10["avg_busy_masters"], 2.0)
        self.assertEqual(row10["needed_masters"], 3)  # ceil(2 / 0.8)
        rec = demand.recommendations(report)
        self.assertTrue(any("Dushanba" in s and "10:00" in s for s in rec["staffing"]))
        self.assertTrue(any(d["start"] == "11:00" for d in rec["discount_suggestions"]))

    def test_booking_spanning_hours_splits_minutes(self):
        start = datetime(2030, 1, 7, 10, 30)
        report = demand.compute_demand([(start, start + timedelta(hours=1))], {0: {10: 1, 11: 1}}, weeks=1)
        rows = {r["hour"]: r["avg_busy_masters"] for r in report["days"][0]["hours"]}
        self.assertEqual(rows, {10: 0.5, 11: 0.5})

    def test_forecast_marks_small_data_unreliable(self):
        self.make_booking(hours_from_now=-48, status=Booking.Status.COMPLETED)
        report = demand.demand_forecast(self.shop, weeks=4)
        self.assertFalse(report["reliable"])
        self.assertIn("note", report)
        self.assertEqual(report["bookings_used"], 1)


class ProfileTests(BookingTestBase):
    def test_no_history(self):
        self.assertEqual(client_profile(self.client_user)["visits"], 0)

    def test_favorite_and_last_visit(self):
        for h in (-24 * 30, -24 * 20, -24 * 10):
            self.make_booking(hours_from_now=h, status=Booking.Status.COMPLETED)
        p = client_profile(self.client_user)
        self.assertEqual(p["visits"], 3)
        self.assertEqual(p["favorite_master"]["id"], self.master.id)
        self.assertEqual(p["last_visit"]["service_id"], self.service.id)
        self.assertEqual(p["typical_interval_days"], 10)
        self.assertIn("Jasur", p["suggestion"])

    def test_only_own_history(self):
        self.make_booking(client=self.other_client, hours_from_now=-48, status=Booking.Status.COMPLETED)
        self.assertEqual(ai.my_recommendations(self.client_user)["visits"], 0)

    def test_tool_registered(self):
        from apps.ai.tools import run_tool
        self.assertEqual(run_tool("my_recommendations", self.client_user, {})["visits"], 0)


class InsightsApiTests(BookingTestBase):
    def setUp(self):
        super().setUp()
        self.api = APIClient()

    def test_owner_gets_own_shop_only(self):
        self.api.force_authenticate(self.owner)
        ok = self.api.get(reverse("insights-demand"), {"shop": self.shop.id})
        self.assertEqual(ok.status_code, 200)
        self.assertIn("days", ok.json())
        rb = self.api.get(reverse("insights-risky"), {"shop": self.shop.id})
        self.assertEqual(rb.status_code, 200)

    def test_other_owner_gets_404(self):
        other = make_user("+998900000099", "Boshqa egasi", "owner")
        self.api.force_authenticate(other)
        self.assertEqual(self.api.get(reverse("insights-demand"), {"shop": self.shop.id}).status_code, 404)

    def test_client_forbidden_and_shop_required(self):
        self.api.force_authenticate(self.client_user)
        self.assertEqual(self.api.get(reverse("insights-demand"), {"shop": self.shop.id}).status_code, 403)
        self.api.force_authenticate(self.owner)
        self.assertEqual(self.api.get(reverse("insights-demand")).status_code, 400)

    def test_risky_bookings_sorted_by_risk(self):
        self.make_booking(client=self.client_user, hours_from_now=96)
        self.api.force_authenticate(self.owner)
        data = self.api.get(reverse("insights-risky"), {"shop": self.shop.id}).json()["bookings"]
        self.assertEqual(len(data), 1)
        self.assertIn(data[0]["level"], ("low", "medium", "high"))
