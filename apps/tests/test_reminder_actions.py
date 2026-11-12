import asyncio
import os
from io import StringIO
from types import SimpleNamespace
from unittest import SkipTest, mock

from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.ai.notify import reminder_markup
from apps.bookings import events
from apps.bookings.models import Booking
from apps.bookings.services import BookingError, cancel_by_client, respond_by_client
from apps.tests.base import BookingTestBase
from telegram_bot.api import ApiError, NotLinked


class RespondByClientTests(BookingTestBase):
    def test_confirm_sets_timestamp_once(self):
        booking = self.make_booking(hours_from_now=3)
        result = respond_by_client(self.client_user, booking.id, "confirm")
        booking.refresh_from_db()
        first = booking.client_confirmed_at
        self.assertIsNotNone(first)
        self.assertTrue(result["client_confirmed"])
        respond_by_client(self.client_user, booking.id, "confirm")  # takroriy bosish
        booking.refresh_from_db()
        self.assertEqual(booking.client_confirmed_at, first)

    def test_other_clients_booking_is_not_found(self):
        booking = self.make_booking(client=self.other_client, hours_from_now=3)
        with self.assertRaisesMessage(BookingError, "Bron topilmadi"):
            respond_by_client(self.client_user, booking.id, "confirm")
        booking.refresh_from_db()
        self.assertIsNone(booking.client_confirmed_at)

    def test_inactive_or_past_booking_is_rejected(self):
        for status in (Booking.Status.CANCELLED, Booking.Status.COMPLETED, Booking.Status.NO_SHOW):
            booking = self.make_booking(hours_from_now=3, status=status)
            with self.assertRaises(BookingError):
                respond_by_client(self.client_user, booking.id, "confirm")
        past = self.make_booking(hours_from_now=-1)
        with self.assertRaisesMessage(BookingError, "o'tib bo'lgan"):
            respond_by_client(self.client_user, past.id, "confirm")

    def test_late_notifies_master_once_and_counts_as_confirmation(self):
        booking = self.make_booking(hours_from_now=1)
        with mock.patch.object(events, "notify_master_running_late") as notify:
            result = respond_by_client(self.client_user, booking.id, "late", 10)
            respond_by_client(self.client_user, booking.id, "late", 10)  # takror: ustaga qayta xabar yo'q
            self.assertEqual(notify.call_count, 1)
            respond_by_client(self.client_user, booking.id, "late", 20)  # vaqt o'zgardi: yangi xabar
            self.assertEqual(notify.call_count, 2)
        booking.refresh_from_db()
        self.assertEqual(booking.late_minutes, 20)
        self.assertIsNotNone(booking.client_confirmed_at)
        self.assertEqual(result["late_minutes"], 10)

    def test_late_window_rules(self):
        too_early = self.make_booking(hours_from_now=10)
        with self.assertRaisesMessage(BookingError, "yaqinroq"):
            respond_by_client(self.client_user, too_early.id, "late", 10)
        just_started = self.make_booking(hours_from_now=-0.2)  # 12 daqiqa oldin boshlangan: hali mumkin
        respond_by_client(self.client_user, just_started.id, "late", 10)
        long_gone = self.make_booking(hours_from_now=-1)
        with self.assertRaisesMessage(BookingError, "o'tib ketgan"):
            respond_by_client(self.client_user, long_gone.id, "late", 10)

    def test_invalid_action_and_minutes(self):
        booking = self.make_booking(hours_from_now=1)
        with self.assertRaises(BookingError):
            respond_by_client(self.client_user, booking.id, "delete")
        with self.assertRaises(BookingError):
            respond_by_client(self.client_user, booking.id, "late", 999)

    def test_master_gets_telegram_message_about_lateness(self):
        self.master_user.telegram_id = 222
        self.master_user.save()
        booking = self.make_booking(hours_from_now=1)
        with mock.patch("apps.ai.notify.send_telegram", return_value=True) as sender, \
                self.captureOnCommitCallbacks(execute=True):
            respond_by_client(self.client_user, booking.id, "late", 20)
        self.assertEqual(sender.call_args[0][0], 222)
        self.assertIn("20 daqiqa", sender.call_args[0][1])

    def test_cancel_via_button_path_frees_slot_and_respects_two_hour_rule(self):
        soon = self.make_booking(hours_from_now=1)
        with self.assertRaises(BookingError):
            cancel_by_client(self.client_user, soon.id)
        later = self.make_booking(hours_from_now=5)
        cancel_by_client(self.client_user, later.id)
        later.refresh_from_db()
        self.assertEqual(later.status, Booking.Status.CANCELLED)


class RespondApiTests(BookingTestBase):
    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.api.force_authenticate(self.client_user)

    def url(self, booking):
        return f"/api/bookings/{booking.id}/respond/"

    def test_confirm_and_late(self):
        booking = self.make_booking(hours_from_now=2)
        resp = self.api.post(self.url(booking), {"action": "confirm"}, format="json")
        self.assertEqual(resp.status_code, 200)
        resp = self.api.post(self.url(booking), {"action": "late", "minutes": 10}, format="json")
        self.assertEqual(resp.data["late_minutes"], 10)

    def test_foreign_booking_404_and_anonymous_401(self):
        booking = self.make_booking(client=self.other_client, hours_from_now=2)
        self.assertEqual(self.api.post(self.url(booking), {"action": "confirm"}, format="json").status_code, 404)
        self.api.force_authenticate(None)
        self.assertEqual(self.api.post(self.url(booking), {"action": "confirm"}, format="json").status_code, 401)

    def test_validation_errors(self):
        booking = self.make_booking(hours_from_now=2)
        self.assertEqual(self.api.post(self.url(booking), {"action": "x"}, format="json").status_code, 400)
        self.assertEqual(
            self.api.post(self.url(booking), {"action": "late", "minutes": 7}, format="json").status_code, 400)

    def test_owner_sees_confirmation_in_shop_list(self):
        booking = self.make_booking(hours_from_now=2)
        respond_by_client(self.client_user, booking.id, "confirm")
        self.api.force_authenticate(self.owner)
        resp = self.api.get("/api/bookings/shop/", {"shop": self.shop.id})
        self.assertEqual(resp.status_code, 200)
        rows = resp.data["results"] if isinstance(resp.data, dict) and "results" in resp.data else resp.data
        self.assertIsNotNone(rows[0]["client_confirmed_at"])


class ReminderButtonsTests(BookingTestBase):
    def setUp(self):
        super().setUp()
        self.client_user.telegram_id = 111
        self.client_user.save()

    def test_markup_shape_and_callback_limits(self):
        markup = reminder_markup(123456789, with_late=True)
        buttons = [b for row in markup["inline_keyboard"] for b in row]
        self.assertEqual([b["callback_data"].rsplit(":", 1)[1] for b in buttons], ["c", "l", "x"])
        self.assertTrue(all(len(b["callback_data"].encode()) <= 64 for b in buttons))
        no_late = reminder_markup(5, with_late=False)
        self.assertEqual(len([b for row in no_late["inline_keyboard"] for b in row]), 2)

    def run_cmd(self, *args):
        with mock.patch("apps.ai.management.commands.send_reminders.send_telegram", return_value=True) as sender:
            call_command("send_reminders", *args, stdout=StringIO())
        return sender

    def test_reminder_is_sent_with_buttons_including_late(self):
        booking = self.make_booking(hours_from_now=2, status=Booking.Status.CONFIRMED)
        sender = self.run_cmd()
        markup = sender.call_args.kwargs["reply_markup"]
        data = [b["callback_data"] for row in markup["inline_keyboard"] for b in row]
        self.assertEqual(data, [f"rem:{booking.id}:c", f"rem:{booking.id}:l", f"rem:{booking.id}:x"])

    def test_early_risk_reminder_has_no_late_button(self):
        base = timezone.now() - timezone.timedelta(days=60)
        for i in range(3):
            start = base + timezone.timedelta(days=i)
            Booking.objects.create(client=self.client_user, master=self.master, service=self.service,
                                   start_time=start, end_time=start + timezone.timedelta(minutes=30),
                                   price=50000, status=Booking.Status.NO_SHOW)
        self.make_booking(hours_from_now=20, status=Booking.Status.CONFIRMED)
        sender = self.run_cmd()
        markup = sender.call_args.kwargs["reply_markup"]
        codes = [b["callback_data"].rsplit(":", 1)[1] for row in markup["inline_keyboard"] for b in row]
        self.assertEqual(codes, ["c", "x"])


class BotReminderHandlerTests(BookingTestBase):
    """on_reminder oqimi soxta Telegram va backend bilan."""

    def setUp(self):
        super().setUp()
        patcher = mock.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "1:test", "TELEGRAM_BOT_SECRET": "s"})
        patcher.start()
        self.addCleanup(patcher.stop)
        try:
            from telegram_bot import main
        except ImportError:
            raise SkipTest("aiogram o'rnatilmagan")
        self.main = main

    BASE_TEXT = "⏰ Eslatma: bugun soat 15:00 da Demo da Jasur ustaga yozilgansiz."

    def call(self, data, text=None):
        log = {"answers": [], "edits": []}

        async def answer(text=None, show_alert=False, **kw):
            log["answers"].append((text, show_alert))

        async def edit_text(text, reply_markup=None, **kw):
            log["edits"].append((text, reply_markup))

        message = SimpleNamespace(text=text or self.BASE_TEXT, edit_text=edit_text)
        return SimpleNamespace(data=data, from_user=SimpleNamespace(id=42), message=message, answer=answer), log

    def backend(self, respond_error=None, cancel_error=None, token_error=None):
        calls = []

        async def get_token(user_id, **kw):
            if token_error:
                raise token_error
            return "tok"

        async def respond_booking(token, booking_id, action, minutes=10):
            calls.append(("respond", booking_id, action, minutes))
            if respond_error:
                raise respond_error
            return {}

        async def cancel_booking(token, booking_id):
            calls.append(("cancel", booking_id))
            if cancel_error:
                raise cancel_error
            return {}

        backend = SimpleNamespace(get_token=get_token, respond_booking=respond_booking, cancel_booking=cancel_booking)
        return backend, calls

    def run_handler(self, data, backend, text=None):
        call, log = self.call(data, text)
        with mock.patch.object(self.main, "backend", backend):
            asyncio.run(self.main.on_reminder(call))
        return log

    def codes(self, markup):
        if markup is None:
            return None
        return [b.callback_data.rsplit(":", 1)[1] for row in markup.inline_keyboard for b in row]

    def test_confirm_edits_message_and_keeps_only_cancel_button(self):
        backend, calls = self.backend()
        log = self.run_handler("rem:7:c", backend)
        self.assertEqual(calls, [("respond", 7, "confirm", 10)])
        text, markup = log["edits"][0]
        self.assertIn("sizni kutamiz", text)
        self.assertIn("Eslatma", text)  # asl matn saqlanadi
        self.assertEqual(self.codes(markup), ["x"])

    def test_late_button(self):
        backend, calls = self.backend()
        log = self.run_handler("rem:7:l", backend)
        self.assertEqual(calls, [("respond", 7, "late", 10)])
        self.assertIn("10 daqiqa", log["edits"][0][0])

    def test_cancel_asks_first_without_calling_backend(self):
        backend, calls = self.backend()
        log = self.run_handler("rem:7:x", backend)
        self.assertEqual(calls, [])
        text, markup = log["edits"][0]
        self.assertIn("Rostdan bekor qilasizmi?", text)
        self.assertEqual(self.codes(markup), ["xy", "xn"])

    def test_cancel_no_restores_buttons_without_duplicate_question(self):
        backend, calls = self.backend()
        asked = self.BASE_TEXT + self.main.CANCEL_QUESTION
        log = self.run_handler("rem:7:xn", backend, text=asked)
        self.assertEqual(calls, [])
        text, markup = log["edits"][0]
        self.assertNotIn("Rostdan", text)
        self.assertEqual(self.codes(markup), ["c", "x"])

    def test_cancel_yes_cancels_and_removes_buttons(self):
        backend, calls = self.backend()
        log = self.run_handler("rem:7:xy", backend, text=self.BASE_TEXT + self.main.CANCEL_QUESTION)
        self.assertEqual(calls, [("cancel", 7)])
        text, markup = log["edits"][0]
        self.assertIn("bekor qilindi", text)
        self.assertNotIn("Rostdan", text)
        self.assertIsNone(markup)

    def test_too_late_to_cancel_shows_reason_and_restores_buttons(self):
        backend, _ = self.backend(cancel_error=ApiError(400, "Bronni kamida 2 soat oldin bekor qilish mumkin."))
        log = self.run_handler("rem:7:xy", backend, text=self.BASE_TEXT + self.main.CANCEL_QUESTION)
        self.assertIn("2 soat", log["answers"][0][0])
        self.assertTrue(log["answers"][0][1])  # alert
        self.assertEqual(self.codes(log["edits"][0][1]), ["c", "x"])

    def test_not_linked_and_garbage_data(self):
        backend, calls = self.backend(token_error=NotLinked(404, "x"))
        log = self.run_handler("rem:7:c", backend)
        self.assertIn("/start", log["answers"][0][0])
        self.assertEqual(log["edits"], [])
        for bad in ("rem:abc:c", "rem:7:zzz", "rem:7"):
            backend, calls = self.backend()
            log = self.run_handler(bad, backend)
            self.assertEqual((calls, log["edits"]), ([], []))
