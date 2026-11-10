from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.utils import timezone

from apps.bookings.models import Booking
from apps.bookings.tests import BookingTestBase

from .models import Notification


class ReminderTests(BookingTestBase):
    def setUp(self):
        super().setUp()
        self.client_user.telegram_id = 111
        self.client_user.save()

    def run_cmd(self, name, *args):
        with mock.patch("apps.ai.management.commands.%s.send_telegram" % name, return_value=True) as sender:
            call_command(name, *args, stdout=StringIO())
        return sender

    def test_reminder_sent_once(self):
        self.make_booking(hours_from_now=2, status=Booking.Status.CONFIRMED)
        sender = self.run_cmd("send_reminders")
        self.assertEqual(sender.call_count, 1)
        self.assertEqual(sender.call_args[0][0], 111)
        sender = self.run_cmd("send_reminders")
        self.assertEqual(sender.call_count, 0)

    def test_far_or_cancelled_bookings_skipped(self):
        self.make_booking(hours_from_now=24)
        self.make_booking(hours_from_now=2, status=Booking.Status.CANCELLED)
        self.assertEqual(self.run_cmd("send_reminders").call_count, 0)

    def test_failed_send_is_retried(self):
        self.make_booking(hours_from_now=2)
        with mock.patch("apps.ai.management.commands.send_reminders.send_telegram", return_value=False):
            call_command("send_reminders", stdout=StringIO())
        self.assertEqual(Notification.objects.count(), 0)
        self.assertEqual(self.run_cmd("send_reminders").call_count, 1)

    def test_client_without_telegram_skipped(self):
        self.make_booking(client=self.other_client, hours_from_now=2)
        self.assertEqual(self.run_cmd("send_reminders").call_count, 0)


class WinbackTests(BookingTestBase):
    def setUp(self):
        super().setUp()
        self.client_user.telegram_id = 111
        self.client_user.save()

    def visit(self, weeks_ago, status=Booking.Status.COMPLETED):
        return self.make_booking(hours_from_now=-weeks_ago * 7 * 24, status=status)

    def run_cmd(self):
        with mock.patch("apps.ai.management.commands.winback.send_telegram", return_value=True) as sender:
            call_command("winback", stdout=StringIO())
        return sender

    def test_client_absent_five_weeks_gets_message_once(self):
        self.visit(5)
        sender = self.run_cmd()
        self.assertEqual(sender.call_count, 1)
        self.assertIn("Jasur", sender.call_args[0][1])
        self.assertEqual(self.run_cmd().call_count, 0)

    def test_recent_or_very_old_clients_skipped(self):
        self.visit(1)
        self.assertEqual(self.run_cmd().call_count, 0)
        Booking.objects.all().delete()
        self.visit(10)
        self.assertEqual(self.run_cmd().call_count, 0)

    def test_client_with_upcoming_booking_skipped(self):
        self.visit(5)
        self.make_booking(hours_from_now=48)
        self.assertEqual(self.run_cmd().call_count, 0)
