from datetime import datetime, time, timedelta

from django.utils import timezone

from apps.bookings.models import Booking
from apps.tests.base import BookingTestBase
from apps.masters.models import DayOff

from apps.ai import services


class FindBestSlotsTests(BookingTestBase):
    def setUp(self):
        super().setUp()
        self.day = (timezone.now() + timedelta(days=3)).astimezone(services.SHOP_TZ).date()

    def find(self, **kwargs):
        return services.find_best_slots(
            self.client_user, service_id=self.service.id, date=self.day.isoformat(), **kwargs
        )

    def test_evening_returns_only_late_slots(self):
        result = self.find(part_of_day="evening")
        times = [s["start_time"] for s in result["suggestions"]]
        self.assertTrue(times)
        self.assertTrue(all(t >= "17:00" for t in times))

    def test_preferred_time_comes_first(self):
        result = self.find(preferred_time="12:00")
        self.assertEqual(result["suggestions"][0]["start_time"], "12:00")

    def test_busy_slot_is_not_suggested(self):
        start = datetime.combine(self.day, time(12, 0), tzinfo=services.SHOP_TZ)
        Booking.objects.create(
            client=self.other_client, master=self.master, service=self.service,
            start_time=start, end_time=start + timedelta(minutes=30),
            price=self.service.price, status=Booking.Status.CONFIRMED,
        )
        result = self.find(preferred_time="12:00")
        times = [s["start_time"] for s in result["suggestions"]]
        self.assertNotIn("12:00", times)
        self.assertIn(times[0], ("11:30", "12:30"))

    def test_moves_to_next_day_when_master_has_day_off(self):
        DayOff.objects.create(master=self.master, date=self.day)
        result = self.find(search_days=3)
        dates = {s["date"] for s in result["suggestions"]}
        self.assertTrue(dates)
        self.assertNotIn(self.day.isoformat(), dates)

    def test_nothing_found_returns_empty_list(self):
        DayOff.objects.create(master=self.master, date=self.day)
        result = self.find(search_days=1)
        self.assertEqual(result["suggestions"], [])

    def test_specific_master_filter(self):
        result = self.find(master_id=self.master.id)
        self.assertTrue(all(s["master_id"] == self.master.id for s in result["suggestions"]))

    def test_invalid_part_of_day_raises(self):
        with self.assertRaises(ValueError):
            self.find(part_of_day="midnight")
