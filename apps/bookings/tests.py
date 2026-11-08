from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.masters.models import Master, WorkSchedule
from apps.services.models import Service
from apps.shops.models import Shop

from .models import Booking
from .services import (
    BookingError,
    BookingForbidden,
    cancel_by_client,
    change_status,
    list_my_bookings,
)

User = get_user_model()


def make_user(phone, first_name, role="client"):
    return User.objects.create_user(phone=phone, password="pass12345", first_name=first_name, role=role)


class BookingTestBase(TestCase):
    def setUp(self):
        self.owner = make_user("+998900000001", "Egasi", "owner")
        self.master_user = make_user("+998900000002", "Jasur", "master")
        self.client_user = make_user("+998900000004", "Mijoz")
        self.other_client = make_user("+998900000005", "Boshqa")

        self.shop = Shop.objects.create(
            owner=self.owner, name="Demo", phone="+998900000001", city="Toshkent",
            address="Manzil 1", opens_at=time(9, 0), closes_at=time(19, 0),
            is_approved=True, is_active=True,
        )
        self.service = Service.objects.create(shop=self.shop, name="Soch olish", price=50000, duration_minutes=30)
        self.master = Master.objects.create(user=self.master_user, shop=self.shop)
        for weekday in range(7):
            WorkSchedule.objects.create(
                master=self.master, weekday=weekday, start_time=time(9, 0), end_time=time(18, 0)
            )

    def make_booking(self, client=None, hours_from_now=24, status=Booking.Status.PENDING):
        start = timezone.now() + timedelta(hours=hours_from_now)
        return Booking.objects.create(
            client=client or self.client_user, master=self.master, service=self.service,
            start_time=start, end_time=start + timedelta(minutes=30),
            price=self.service.price, status=status,
        )


class CancelByClientTests(BookingTestBase):
    def test_client_can_cancel_future_booking(self):
        booking = self.make_booking(hours_from_now=24)
        result = cancel_by_client(self.client_user, booking.id)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CANCELLED)
        self.assertEqual(result["status"], "cancelled")

    def test_cannot_cancel_less_than_two_hours_before(self):
        booking = self.make_booking(hours_from_now=1)
        with self.assertRaises(BookingError):
            cancel_by_client(self.client_user, booking.id)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.PENDING)

    def test_cannot_cancel_someone_elses_booking(self):
        booking = self.make_booking(client=self.client_user)
        with self.assertRaises(BookingError):
            cancel_by_client(self.other_client, booking.id)

    def test_cannot_cancel_twice(self):
        booking = self.make_booking()
        cancel_by_client(self.client_user, booking.id)
        with self.assertRaises(BookingError):
            cancel_by_client(self.client_user, booking.id)


class ListMyBookingsTests(BookingTestBase):
    def test_upcoming_only_hides_cancelled_and_past(self):
        active = self.make_booking(hours_from_now=24)
        self.make_booking(hours_from_now=48, status=Booking.Status.CANCELLED)
        self.make_booking(hours_from_now=-48, status=Booking.Status.COMPLETED)
        self.make_booking(client=self.other_client, hours_from_now=24)

        result = list_my_bookings(self.client_user, upcoming_only=True)
        self.assertEqual([b["id"] for b in result], [active.id])

        all_mine = list_my_bookings(self.client_user, upcoming_only=False)
        self.assertEqual(len(all_mine), 3)


class ChangeStatusTests(BookingTestBase):
    def test_master_confirms_then_completes(self):
        booking = self.make_booking(hours_from_now=-1)
        change_status(self.master_user, booking.id, "confirmed")
        change_status(self.owner, booking.id, "completed")
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.COMPLETED)

    def test_client_cannot_change_status(self):
        booking = self.make_booking(hours_from_now=-1)
        with self.assertRaises(BookingForbidden):
            change_status(self.client_user, booking.id, "confirmed")

    def test_other_shop_owner_cannot_change_status(self):
        booking = self.make_booking(hours_from_now=-1)
        stranger = make_user("+998900000009", "Begona", "owner")
        with self.assertRaises(BookingForbidden):
            change_status(stranger, booking.id, "confirmed")

    def test_invalid_transition_rejected(self):
        booking = self.make_booking(hours_from_now=-1)  # pending
        with self.assertRaises(BookingError):
            change_status(self.owner, booking.id, "completed")

    def test_cannot_complete_before_start(self):
        booking = self.make_booking(hours_from_now=5, status=Booking.Status.CONFIRMED)
        with self.assertRaises(BookingError):
            change_status(self.owner, booking.id, "completed")

    def test_no_show_increments_counter(self):
        booking = self.make_booking(hours_from_now=-1, status=Booking.Status.CONFIRMED)
        change_status(self.owner, booking.id, "no_show")
        self.client_user.refresh_from_db()
        self.assertEqual(self.client_user.no_show_count, 1)
        self.assertIsNone(self.client_user.blocked_until)

    def test_three_no_shows_in_a_row_blocks_client(self):
        for hours in (-72, -48, -24):
            booking = self.make_booking(hours_from_now=hours, status=Booking.Status.CONFIRMED)
            change_status(self.owner, booking.id, "no_show")
        self.client_user.refresh_from_db()
        self.assertEqual(self.client_user.no_show_count, 3)
        self.assertIsNotNone(self.client_user.blocked_until)
        self.assertGreater(self.client_user.blocked_until, timezone.now())

    def test_completed_booking_breaks_the_streak(self):
        for hours, final in ((-72, "no_show"), (-48, "completed"), (-24, "no_show")):
            booking = self.make_booking(hours_from_now=hours, status=Booking.Status.CONFIRMED)
            change_status(self.owner, booking.id, final)
        self.client_user.refresh_from_db()
        self.assertIsNone(self.client_user.blocked_until)


class BookingApiTests(BookingTestBase):
    def setUp(self):
        super().setUp()
        self.api = APIClient()

    def test_requires_authentication(self):
        self.assertEqual(self.api.get("/api/bookings/").status_code, 401)

    def test_create_list_and_cancel_flow(self):
        self.api.force_authenticate(self.client_user)
        day = (timezone.now() + timedelta(days=7)).date().isoformat()

        slots = self.api.get(
            "/api/bookings/slots/", {"master": self.master.id, "service": self.service.id, "date": day}
        )
        self.assertEqual(slots.status_code, 200)
        self.assertIn("10:00", slots.json()["slots"])

        created = self.api.post(
            "/api/bookings/",
            {"master": self.master.id, "service": self.service.id, "date": day, "start_time": "10:00"},
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        booking_id = created.json()["booking_id"]

        # Xuddi shu vaqtni qayta olib bo'lmaydi
        again = self.api.post(
            "/api/bookings/",
            {"master": self.master.id, "service": self.service.id, "date": day, "start_time": "10:00"},
            format="json",
        )
        self.assertEqual(again.status_code, 400)

        listed = self.api.get("/api/bookings/")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["count"], 1)

        cancelled = self.api.post(f"/api/bookings/{booking_id}/cancel/")
        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(cancelled.json()["status"], "cancelled")

    def test_client_cannot_use_status_endpoint(self):
        booking = self.make_booking(hours_from_now=-1)
        self.api.force_authenticate(self.client_user)
        resp = self.api.post(f"/api/bookings/{booking.id}/status/", {"status": "confirmed"}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_owner_sees_shop_bookings_and_confirms(self):
        booking = self.make_booking(hours_from_now=24)
        self.api.force_authenticate(self.owner)

        listed = self.api.get("/api/bookings/shop/")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["count"], 1)

        resp = self.api.post(f"/api/bookings/{booking.id}/status/", {"status": "confirmed"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "confirmed")
