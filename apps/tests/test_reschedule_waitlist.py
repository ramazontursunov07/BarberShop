from datetime import time, timedelta
from unittest import mock

from django.utils import timezone
from rest_framework.test import APIClient

from apps.ai import services as availability
from apps.bookings.models import Booking, WaitlistEntry
from apps.bookings.services import BookingError, change_status, reschedule_by_client, cancel_by_client
from apps.bookings import waitlist
from apps.masters.models import WorkSchedule
from apps.services.models import Service

from .base import BookingTestBase


class RescheduleTests(BookingTestBase):
    def setUp(self):
        super().setUp()
        self.day = (timezone.now() + timedelta(days=7)).date().isoformat()

    def book(self, time="10:00", user=None, service=None):
        svc = service or self.service
        result = availability.create_booking(user or self.client_user, self.master.id, svc.id, self.day, time)
        return Booking.objects.get(pk=result["booking_id"])

    def test_reschedule_moves_booking_and_keeps_price(self):
        booking = self.book("10:00")
        result = reschedule_by_client(self.client_user, booking.id, self.day, "14:00")
        booking.refresh_from_db()
        self.assertEqual(result["start_time"], "14:00")
        self.assertEqual(booking.price, 50000)
        # eski vaqt bo'shadi
        self.assertIn("10:00", availability.get_available_slots(
            self.other_client, self.master.id, self.service.id, self.day)["slots"])

    def test_can_move_to_overlapping_own_time(self):
        long = Service.objects.create(shop=self.shop, name="Uzun", price=80000, duration_minutes=60)
        booking = self.book("10:00", service=long)
        result = reschedule_by_client(self.client_user, booking.id, self.day, "10:30")
        self.assertEqual(result["start_time"], "10:30")
        self.assertEqual(result["end_time"], "11:30")

    def test_taken_slot_rejected(self):
        self.book("10:00", user=self.other_client)
        booking = self.book("12:00")
        with self.assertRaises(BookingError):
            reschedule_by_client(self.client_user, booking.id, self.day, "10:00")
        booking.refresh_from_db()
        self.assertEqual(booking.start_time.astimezone(availability.SHOP_TZ).strftime("%H:%M"), "12:00")

    def test_too_late_rejected(self):
        booking = self.make_booking(hours_from_now=1)
        with self.assertRaises(BookingError):
            reschedule_by_client(self.client_user, booking.id, self.day, "10:00")

    def test_other_clients_booking_not_found(self):
        booking = self.book("10:00")
        with self.assertRaises(BookingError) as ctx:
            reschedule_by_client(self.other_client, booking.id, self.day, "11:00")
        self.assertEqual(str(ctx.exception), "Bron topilmadi")

    def test_cancelled_booking_cannot_be_rescheduled(self):
        booking = self.book("10:00")
        cancel_by_client(self.client_user, booking.id)
        with self.assertRaises(BookingError):
            reschedule_by_client(self.client_user, booking.id, self.day, "11:00")

    def test_api(self):
        booking = self.book("10:00")
        api = APIClient()
        api.force_authenticate(self.client_user)
        resp = api.post(f"/api/bookings/{booking.id}/reschedule/", {"date": self.day, "start_time": "15:00"},
                        format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["start_time"], "15:00")
        bad = api.post(f"/api/bookings/{booking.id}/reschedule/", {"date": self.day, "start_time": "03:00"},
                       format="json")
        self.assertEqual(bad.status_code, 400)


class WaitlistTests(BookingTestBase):
    def setUp(self):
        super().setUp()
        # Usta kuniga bitta slot (10:00) ishlaydi: shuni band qilsak, kun to'la
        WorkSchedule.objects.all().update(start_time=time(10, 0), end_time=time(10, 30))
        self.day_date = (timezone.now() + timedelta(days=7)).date()
        self.day = self.day_date.isoformat()
        self.other_client.telegram_id = 111222
        self.other_client.save()

    def fill_day(self):
        result = availability.create_booking(self.client_user, self.master.id, self.service.id, self.day, "10:00")
        return Booking.objects.get(pk=result["booking_id"])

    def test_cannot_join_when_slot_is_free(self):
        with self.assertRaises(BookingError):
            waitlist.join(self.other_client, self.service, self.day_date)

    def test_join_and_leave(self):
        self.fill_day()
        entry = waitlist.join(self.other_client, self.service, self.day_date)
        self.assertEqual(entry.status, WaitlistEntry.Status.WAITING)
        with self.assertRaises(BookingError):  # takror
            waitlist.join(self.other_client, self.service, self.day_date)
        waitlist.leave(self.other_client, entry.id)
        entry.refresh_from_db()
        self.assertEqual(entry.status, WaitlistEntry.Status.CANCELLED)

    def test_past_and_far_dates_rejected(self):
        with self.assertRaises(BookingError):
            waitlist.join(self.other_client, self.service, timezone.now().date() - timedelta(days=1))
        with self.assertRaises(BookingError):
            waitlist.join(self.other_client, self.service, timezone.now().date() + timedelta(days=90))

    def test_cancel_notifies_waiting_client_once(self):
        booking = self.fill_day()
        entry = waitlist.join(self.other_client, self.service, self.day_date)

        with mock.patch("apps.ai.notify.send_telegram", return_value=True) as send:
            with self.captureOnCommitCallbacks(execute=True):
                cancel_by_client(self.client_user, booking.id)
        send.assert_called_once()
        self.assertEqual(send.call_args.args[0], 111222)
        entry.refresh_from_db()
        self.assertEqual(entry.status, WaitlistEntry.Status.NOTIFIED)

        # Qayta xabar yuborilmaydi
        self.assertEqual(waitlist.notify_freed(booking), 0)

    def test_owner_cancel_also_notifies(self):
        booking = self.fill_day()
        waitlist.join(self.other_client, self.service, self.day_date)
        with mock.patch("apps.ai.notify.send_telegram", return_value=True) as send:
            with self.captureOnCommitCallbacks(execute=True):
                change_status(self.owner, booking.id, Booking.Status.CANCELLED)
        send.assert_called_once()

    def test_failed_send_returns_entry_to_waiting(self):
        booking = self.fill_day()
        entry = waitlist.join(self.other_client, self.service, self.day_date)
        with mock.patch("apps.ai.notify.send_telegram", return_value=False):
            cancel_by_client(self.client_user, booking.id)
            waitlist.notify_freed(booking)
        entry.refresh_from_db()
        self.assertEqual(entry.status, WaitlistEntry.Status.WAITING)

    def test_time_window_respected(self):
        booking = self.fill_day()
        entry = waitlist.join(self.other_client, self.service, self.day_date,
                              from_time=time(15, 0), to_time=time(18, 0))
        with mock.patch("apps.ai.notify.send_telegram", return_value=True) as send:
            cancel_by_client(self.client_user, booking.id)
            self.assertEqual(waitlist.notify_freed(booking), 0)
        send.assert_not_called()
        entry.refresh_from_db()
        self.assertEqual(entry.status, WaitlistEntry.Status.WAITING)

    def test_booking_marks_entry_booked(self):
        booking = self.fill_day()
        entry = waitlist.join(self.other_client, self.service, self.day_date)
        cancel_by_client(self.client_user, booking.id)
        availability.create_booking(self.other_client, self.master.id, self.service.id, self.day, "10:00")
        entry.refresh_from_db()
        self.assertEqual(entry.status, WaitlistEntry.Status.BOOKED)

    def test_limit_of_active_entries(self):
        self.fill_day()
        for i in range(waitlist.MAX_ACTIVE_ENTRIES):
            other_day = self.day_date + timedelta(days=i + 1)
            WaitlistEntry.objects.create(client=self.other_client, service=self.service, date=other_day)
        with self.assertRaises(BookingError):
            waitlist.join(self.other_client, self.service, self.day_date)

    def test_api(self):
        self.fill_day()
        api = APIClient()
        api.force_authenticate(self.other_client)
        created = api.post("/api/bookings/waitlist/", {"service": self.service.id, "date": self.day}, format="json")
        self.assertEqual(created.status_code, 201)
        listed = api.get("/api/bookings/waitlist/")
        self.assertEqual(len(listed.json()), 1)
        deleted = api.delete(f"/api/bookings/waitlist/{created.json()['id']}/")
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(api.get("/api/bookings/waitlist/").json(), [])
        