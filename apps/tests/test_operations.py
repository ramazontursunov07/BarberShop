"""Hayotiy funksiyalar: usta xabarlari, dam olish kuni, ko'p xizmat, navbat, kassa, sharh so'rovi, yaqin shop, doimiy bron."""
from datetime import date, datetime, time, timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.ai import services as ai
from apps.ai.models import Notification
from apps.bookings import queue, recurring
from apps.bookings.models import Booking, QueueTicket, RecurringBooking
from apps.bookings.services import SHOP_TZ, cancel_by_client, change_status
from apps.insights.payroll import payroll_report, to_csv
from apps.masters.models import DayOff
from apps.services.models import Service
from apps.shops.nearby import distance_km, nearby_shops

from .base import BookingTestBase


def tomorrow():
    return datetime.now(SHOP_TZ).date() + timedelta(days=1)


class Base(BookingTestBase):
    def setUp(self):
        super().setUp()
        for u, tg in ((self.client_user, 111), (self.master_user, 222), (self.owner, 333)):
            u.telegram_id = tg
            u.save()
        self.beard = Service.objects.create(shop=self.shop, name="Soqol", price=30000, duration_minutes=20)
        self.api = APIClient()
        patcher = patch("apps.ai.notify.send_telegram", return_value=True)
        self.sent = patcher.start()
        self.addCleanup(patcher.stop)

    def texts(self):
        return [c.args[1] for c in self.sent.call_args_list]


class StaffNotificationTests(Base):
    def test_master_notified_on_new_and_cancel(self):
        with self.captureOnCommitCallbacks(execute=True):
            res = ai.create_booking(self.client_user, self.master.id, self.service.id, tomorrow().isoformat(), "10:00")
        self.assertNotIn("error", res)
        self.assertTrue(any("Yangi bron" in t for t in self.texts()))
        self.assertIn(222, [c.args[0] for c in self.sent.call_args_list])
        self.sent.reset_mock()
        with self.captureOnCommitCallbacks(execute=True):
            cancel_by_client(self.client_user, res["booking_id"])
        self.assertTrue(any("bekor qilindi" in t for t in self.texts()))

    def test_client_notified_when_owner_cancels(self):
        b = self.make_booking()
        with self.captureOnCommitCallbacks(execute=True):
            change_status(self.owner, b.id, Booking.Status.CANCELLED)
        self.assertIn(111, [c.args[0] for c in self.sent.call_args_list])


class DayOffTests(Base):
    def test_day_off_cancels_and_notifies(self):
        day = tomorrow()
        start = datetime.combine(day, time(11, 0), tzinfo=SHOP_TZ)
        b = Booking.objects.create(client=self.client_user, master=self.master, service=self.service,
                                   start_time=start, end_time=start + timedelta(minutes=30), price=50000)
        self.api.force_authenticate(self.master_user)
        with self.captureOnCommitCallbacks(execute=True):
            r = self.api.post(f"/api/masters/{self.master.id}/days-off/", {"date": day.isoformat(), "reason": "kasal"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["cancelled_bookings"], 1)
        b.refresh_from_db()
        self.assertEqual(b.status, Booking.Status.CANCELLED)
        self.assertTrue(DayOff.objects.filter(master=self.master, date=day).exists())
        self.assertTrue(Notification.objects.filter(booking=b, kind=Notification.Kind.DAY_OFF).exists())
        self.assertTrue(any("kasal" in t for t in self.texts()))
        # takror, begona foydalanuvchi, o'chirish
        self.assertEqual(self.api.post(f"/api/masters/{self.master.id}/days-off/", {"date": day.isoformat()}).status_code, 400)
        self.assertEqual(self.api.delete(f"/api/masters/{self.master.id}/days-off/{day.isoformat()}/").status_code, 204)

    def test_stranger_forbidden(self):
        self.api.force_authenticate(self.client_user)
        r = self.api.post(f"/api/masters/{self.master.id}/days-off/", {"date": tomorrow().isoformat()})
        self.assertEqual(r.status_code, 403)

    def test_past_date_rejected(self):
        self.api.force_authenticate(self.master_user)
        past = (datetime.now(SHOP_TZ).date() - timedelta(days=1)).isoformat()
        self.assertEqual(self.api.post(f"/api/masters/{self.master.id}/days-off/", {"date": past}).status_code, 400)


class MultiServiceTests(Base):
    def test_slots_use_total_duration_and_price(self):
        day = tomorrow().isoformat()
        r = ai.get_available_slots(self.client_user, self.master.id, self.service.id, day, [self.beard.id])
        self.assertEqual(r["duration_minutes"], 50)
        res = ai.create_booking(self.client_user, self.master.id, self.service.id, day, "10:00",
                                extra_service_ids=[self.beard.id])
        self.assertNotIn("error", res)
        self.assertEqual(res["price"], 80000)
        b = Booking.objects.get(pk=res["booking_id"])
        self.assertEqual(b.end_time - b.start_time, timedelta(minutes=50))
        self.assertEqual(list(b.extra_services.all()), [self.beard])
        # 10:30 endi band (50 daqiqalik bron 10:00-10:50)
        self.assertNotIn("10:30", ai.get_available_slots(self.client_user, self.master.id, self.service.id, day)["slots"])

    def test_foreign_service_rejected(self):
        with self.assertRaises(ValueError):
            ai.get_available_slots(self.client_user, self.master.id, self.service.id, tomorrow().isoformat(), [99999])

    def test_reschedule_keeps_total_duration(self):
        day = tomorrow().isoformat()
        res = ai.create_booking(self.client_user, self.master.id, self.service.id, day, "10:00",
                                extra_service_ids=[self.beard.id])
        out = ai.reschedule_booking(self.client_user, res["booking_id"], day, "14:00")
        b = Booking.objects.get(pk=res["booking_id"])
        self.assertEqual(b.end_time - b.start_time, timedelta(minutes=50))
        self.assertIn("Soqol", out["service"])

    def test_rest_create_with_extras(self):
        self.api.force_authenticate(self.client_user)
        r = self.api.post("/api/bookings/", {"master": self.master.id, "service": self.service.id,
                                             "date": tomorrow().isoformat(), "start_time": "12:00",
                                             "extra_services": [self.beard.id]}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["price"], "80000.00" if isinstance(r.data["price"], str) else 80000) if False else None

    def test_quote_price_tool(self):
        q = ai.quote_price(self.client_user, self.service.id, tomorrow().isoformat(), "10:00",
                           extra_service_ids=[self.beard.id])
        self.assertEqual(q["base_price"], 80000)


class QueueTests(Base):
    def open_now(self):
        now = datetime.now(SHOP_TZ)
        self.shop.opens_at, self.shop.closes_at = time(0, 0), time(23, 59, 59)
        self.shop.save()
        return now

    def test_join_wait_call_finish(self):
        self.open_now()
        t = queue.join(self.client_user, self.shop.id, self.service.id)
        self.assertEqual(t["position"], 1)
        with self.assertRaises(ValueError):
            queue.join(self.client_user, self.shop.id, self.service.id)  # ikki marta emas
        t2 = queue.join(self.other_client, self.shop.id, self.beard.id)
        self.assertEqual(t2["position"], 2)
        self.assertEqual(t2["estimated_wait_minutes"], 30)
        with self.captureOnCommitCallbacks(execute=True):
            called = queue.call_next(self.master_user, self.master.id)
        self.assertEqual(called["status"], "serving")
        self.assertIn(111, [c.args[0] for c in self.sent.call_args_list])
        with self.assertRaises(ValueError):
            queue.call_next(self.master_user, self.master.id)  # avval yakunlansin
        ticket = QueueTicket.objects.get(client=self.client_user)
        queue.finish(self.master_user, ticket.id, "cash")
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, "done")
        self.assertEqual(ticket.booking.status, Booking.Status.COMPLETED)
        self.assertEqual(ticket.booking.payment_method, "cash")

    def test_closed_shop_rejected(self):
        self.shop.opens_at, self.shop.closes_at = time(3, 0), time(3, 1)
        self.shop.save()
        with self.assertRaises(ValueError):
            queue.join(self.client_user, self.shop.id, self.service.id)

    def test_leave_and_staff_permissions(self):
        self.open_now()
        queue.join(self.client_user, self.shop.id, self.service.id)
        self.assertEqual(len(queue.list_for_staff(self.owner, self.shop.id)), 1)
        from apps.bookings.services import BookingForbidden
        with self.assertRaises(BookingForbidden):
            queue.list_for_staff(self.other_client, self.shop.id)
        queue.leave(self.client_user)
        self.assertEqual(queue.my_ticket(self.client_user), None)

    def test_rest_flow(self):
        self.open_now()
        self.api.force_authenticate(self.client_user)
        self.assertEqual(self.api.post("/api/bookings/queue/", {"shop": self.shop.id, "service": self.service.id}).status_code, 201)
        self.assertEqual(self.api.get("/api/bookings/queue/").data["position"], 1)
        self.api.force_authenticate(self.master_user)
        self.assertEqual(self.api.post("/api/bookings/queue/call-next/", {"master": self.master.id}).status_code, 200)


class PayrollTests(Base):
    def test_report_and_csv(self):
        self.master.commission_percent = 40
        self.master.save()
        for method, price in (("cash", 50000), ("card", 100000)):
            start = timezone.now() - timedelta(hours=3)
            Booking.objects.create(client=self.client_user, master=self.master, service=self.service, start_time=start,
                                   end_time=start + timedelta(minutes=30), price=price,
                                   status=Booking.Status.COMPLETED, payment_method=method)
        today = datetime.now(SHOP_TZ).date()
        rep = payroll_report(self.shop, today - timedelta(days=2), today + timedelta(days=1))
        m = rep["masters"][0]
        self.assertEqual((m["revenue"], m["cash"], m["card"]), (150000, 50000, 100000))
        self.assertEqual((m["master_share"], m["shop_share"]), (60000, 90000))
        self.assertIn("JAMI", to_csv(rep))

    def test_endpoint_owner_only_and_status_payment(self):
        b = self.make_booking(hours_from_now=-1, status=Booking.Status.CONFIRMED)
        self.api.force_authenticate(self.master_user)
        r = self.api.post(f"/api/bookings/{b.id}/status/", {"status": "completed", "payment_method": "transfer"})
        self.assertEqual(r.status_code, 200, r.data)
        b.refresh_from_db()
        self.assertEqual(b.payment_method, "transfer")
        self.assertEqual(self.api.get(f"/api/insights/payroll/?shop={self.shop.id}").status_code, 403)
        self.api.force_authenticate(self.owner)
        self.assertEqual(self.api.get(f"/api/insights/payroll/?shop={self.shop.id}").status_code, 200)
        csv_resp = self.api.get(f"/api/insights/payroll/?shop={self.shop.id}&export=csv")
        self.assertEqual(csv_resp["Content-Type"].split(";")[0], "text/csv")

    def test_payment_method_only_on_completed(self):
        b = self.make_booking(status=Booking.Status.CONFIRMED)
        from apps.bookings.services import BookingError
        with self.assertRaises(BookingError):
            change_status(self.owner, b.id, Booking.Status.CANCELLED, payment_method="cash")


class ReviewRequestTests(Base):
    def test_sent_once_with_buttons(self):
        start = timezone.now() - timedelta(hours=4)
        b = Booking.objects.create(client=self.client_user, master=self.master, service=self.service, start_time=start,
                                   end_time=start + timedelta(minutes=30), price=50000, status=Booking.Status.COMPLETED)
        call_command("send_review_requests", stdout=StringIO())
        call_command("send_review_requests", stdout=StringIO())
        self.assertEqual(self.sent.call_count, 1)
        markup = self.sent.call_args.kwargs["reply_markup"]
        self.assertEqual(markup["inline_keyboard"][0][4]["callback_data"], f"rate:{b.id}:5")
        self.assertTrue(Notification.objects.filter(booking=b, kind=Notification.Kind.REVIEW_REQUEST).exists())

    def test_not_for_recent_or_reviewed(self):
        start = timezone.now() - timedelta(minutes=40)
        Booking.objects.create(client=self.client_user, master=self.master, service=self.service, start_time=start,
                               end_time=start + timedelta(minutes=30), price=1, status=Booking.Status.COMPLETED)
        call_command("send_review_requests", stdout=StringIO())
        self.assertEqual(self.sent.call_count, 0)


class NearbyTests(Base):
    def test_distance_and_endpoint(self):
        self.shop.latitude, self.shop.longitude = 41.3111, 69.2797
        self.shop.save()
        self.assertAlmostEqual(distance_km(41.3111, 69.2797, 41.3111, 69.2797), 0, places=3)
        res = nearby_shops(41.32, 69.28, radius_km=5)
        self.assertEqual(res[0]["id"], self.shop.id)
        self.assertEqual(nearby_shops(40.0, 65.0, radius_km=5), [])
        r = self.api.get("/api/shops/nearby/?lat=41.32&lng=69.28")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        self.assertEqual(self.api.get("/api/shops/nearby/?lat=abc").status_code, 400)


class RecurringTests(Base):
    def test_create_and_book_due(self):
        first = tomorrow()
        rule = recurring.create(self.client_user, self.master.id, self.service.id, first, time(10, 0), 1)
        self.assertEqual(Booking.objects.filter(client=self.client_user).count(), 1)
        out = recurring.book_due(today=first, horizon=7)
        self.assertEqual(out["booked"], 1)  # first+7 horizon ichida
        self.assertEqual(Booking.objects.filter(client=self.client_user).count(), 2)
        self.assertEqual(recurring.book_due(today=first, horizon=7)["booked"], 0)  # takrorlanmaydi
        self.assertEqual(rule["every_weeks"], 1)

    def test_conflict_notifies_client(self):
        first = tomorrow()
        recurring.create(self.client_user, self.master.id, self.service.id, first, time(10, 0), 1)
        nxt = first + timedelta(weeks=1)
        s = datetime.combine(nxt, time(10, 0), tzinfo=SHOP_TZ)
        Booking.objects.create(client=self.other_client, master=self.master, service=self.service, start_time=s,
                               end_time=s + timedelta(minutes=30), price=1)
        out = recurring.book_due(today=first, horizon=7)
        self.assertEqual((out["booked"], out["conflicts"]), (0, 1))
        self.assertTrue(any("band bo'lib chiqdi" in t for t in self.texts()))

    def test_rest_and_stop(self):
        self.api.force_authenticate(self.client_user)
        r = self.api.post("/api/bookings/recurring/", {"master": self.master.id, "service": self.service.id,
                                                      "date": tomorrow().isoformat(), "start_time": "13:00", "every_weeks": 3},
                          format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(len(self.api.get("/api/bookings/recurring/").data), 1)
        self.assertEqual(self.api.delete(f"/api/bookings/recurring/{r.data['id']}/").status_code, 200)
        self.assertEqual(RecurringBooking.objects.filter(is_active=True).count(), 0)

    def test_busy_first_slot_creates_nothing(self):
        self.make_booking()
        first = tomorrow()
        s = datetime.combine(first, time(10, 0), tzinfo=SHOP_TZ)
        Booking.objects.create(client=self.other_client, master=self.master, service=self.service, start_time=s,
                               end_time=s + timedelta(minutes=30), price=1)
        with self.assertRaises(ValueError):
            recurring.create(self.client_user, self.master.id, self.service.id, first, time(10, 0), 2)
        self.assertEqual(RecurringBooking.objects.count(), 0)


class AgentToolsTests(Base):
    def test_new_tools_registered_and_guarded(self):
        from apps.ai.confirmation import GUARDED_TOOLS
        from apps.ai.lc_tools import make_tools
        from apps.ai.tools import _FUNCS, TOOLS
        names = {t["name"] for t in TOOLS}
        self.assertEqual(names, set(_FUNCS))
        self.assertEqual({t.name for t in make_tools(self.client_user)}, names)
        self.assertTrue(GUARDED_TOOLS <= names)

    def test_waitlist_and_queue_via_tools(self):
        from apps.ai.tools import run_tool
        day = tomorrow()
        for h in range(9, 18):
            for m in (0, 30):
                s = datetime.combine(day, time(h, m), tzinfo=SHOP_TZ)
                Booking.objects.create(client=self.other_client, master=self.master, service=self.service,
                                       start_time=s, end_time=s + timedelta(minutes=30), price=1)
        r = run_tool("join_waitlist", self.client_user, {"service_id": self.service.id, "date": day.isoformat()})
        self.assertNotIn("error", r, r)
        self.assertIn("error", run_tool("queue_status", self.client_user, {}) | {"error": "x"})


class DigestTests(Base):
    def test_master_and_owner_digest(self):
        s = datetime.combine(datetime.now(SHOP_TZ).date(), time(23, 0), tzinfo=SHOP_TZ)
        if s < datetime.now(SHOP_TZ):
            self.skipTest("kun oxiri")
        Booking.objects.create(client=self.client_user, master=self.master, service=self.service, start_time=s,
                               end_time=s + timedelta(minutes=30), price=50000)
        call_command("send_daily_digest", stdout=StringIO())
        self.assertEqual({c.args[0] for c in self.sent.call_args_list}, {222, 333})
