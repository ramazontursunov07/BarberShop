from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.utils import timezone

from apps.ai.models import Notification
from apps.bookings.models import Booking
from apps.tests.base import BookingTestBase


class RiskReminderTests(BookingTestBase):
    def setUp(self):
        super().setUp()
        self.client_user.telegram_id = 111
        self.client_user.save()

    def run_cmd(self, *args):
        with mock.patch("apps.ai.management.commands.send_reminders.send_telegram", return_value=True) as sender:
            call_command("send_reminders", *args, stdout=StringIO())
        return sender

    def make_no_show_history(self, n=3):
        base = timezone.now() - timedelta(days=60)
        for i in range(n):
            start = base + timedelta(days=i)
            Booking.objects.create(client=self.client_user, master=self.master, service=self.service,
                                   start_time=start, end_time=start + timedelta(minutes=30), price=50000,
                                   status=Booking.Status.NO_SHOW)

    def test_risky_client_gets_early_reminder_once(self):
        self.make_no_show_history()
        self.make_booking(hours_from_now=20, status=Booking.Status.CONFIRMED)
        sender = self.run_cmd()
        self.assertEqual(sender.call_count, 1)
        self.assertEqual(Notification.objects.filter(kind=Notification.Kind.RISK_REMINDER).count(), 1)
        self.assertEqual(self.run_cmd().call_count, 0)

    def test_reliable_client_not_bothered_early(self):
        self.make_booking(hours_from_now=20, status=Booking.Status.CONFIRMED)
        self.assertEqual(self.run_cmd().call_count, 0)

    def test_disabled_with_zero(self):
        self.make_no_show_history()
        self.make_booking(hours_from_now=20, status=Booking.Status.CONFIRMED)
        self.assertEqual(self.run_cmd("--risky-hours", "0").call_count, 0)

    def test_risky_client_still_gets_normal_reminder_later(self):
        self.make_no_show_history()
        self.make_booking(hours_from_now=2, status=Booking.Status.CONFIRMED)
        sender = self.run_cmd()
        self.assertEqual(sender.call_count, 1)  # faqat oddiy 3 soatlik eslatma
        self.assertEqual(Notification.objects.filter(kind=Notification.Kind.REMINDER).count(), 1)
