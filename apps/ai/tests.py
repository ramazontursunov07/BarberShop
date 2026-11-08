from datetime import date, datetime, time
from unittest import TestCase

from .slots import compute_slots

DAY = date(2026, 11, 9)


class ComputeSlotsTests(TestCase):
    def test_empty_day_returns_all_slots(self):
        slots = compute_slots(DAY, time(9, 0), time(12, 0), [], 30, 30)
        self.assertEqual(slots, ["09:00", "09:30", "10:00", "10:30", "11:00", "11:30"])

    def test_service_must_fit_before_closing(self):
        slots = compute_slots(DAY, time(9, 0), time(11, 0), [], 60, 30)
        self.assertEqual(slots, ["09:00", "09:30", "10:00"])

    def test_busy_interval_blocks_overlapping_slots(self):
        busy = [(time(10, 0), time(11, 0))]
        slots = compute_slots(DAY, time(9, 0), time(12, 0), busy, 60, 30)
        # 09:30 -> 10:30 band bilan kesishadi, 11:00 -> 12:00 bo'sh
        self.assertEqual(slots, ["09:00", "11:00"])

    def test_past_slots_are_skipped(self):
        now = datetime(2026, 11, 9, 10, 15)
        slots = compute_slots(DAY, time(9, 0), time(12, 0), [], 30, 30, now=now)
        self.assertEqual(slots, ["10:30", "11:00", "11:30"])

    def test_invalid_duration_returns_empty(self):
        self.assertEqual(compute_slots(DAY, time(9, 0), time(12, 0), [], 0), [])
