from datetime import time

from rest_framework.test import APIClient

from apps.bookings.models import Booking
from apps.bookings.tests import BookingTestBase, make_user
from apps.reviews.models import Review

from .models import WorkSchedule


class MasterApiTests(BookingTestBase):
    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.other_owner = make_user("+998900000010", "Boshqa", "owner")

    def test_public_list_has_name_and_rating_but_no_phone(self):
        booking = self.make_booking(hours_from_now=-5, status=Booking.Status.COMPLETED)
        Review.objects.create(booking=booking, client=self.client_user, rating=4, comment="Yaxshi")

        resp = self.api.get("/api/masters/")
        self.assertEqual(resp.status_code, 200)
        row = resp.json()["results"][0]
        self.assertEqual(row["name"], "Jasur")
        self.assertEqual(row["avg_rating"], 4.0)
        self.assertEqual(row["reviews_count"], 1)
        self.assertNotIn("+998", resp.content.decode())

    def test_master_without_reviews_has_no_rating(self):
        row = self.api.get("/api/masters/").json()["results"][0]
        self.assertIsNone(row["avg_rating"])
        self.assertEqual(row["reviews_count"], 0)

    def test_unapproved_shop_masters_hidden(self):
        self.shop.is_approved = False
        self.shop.save()
        self.assertEqual(self.api.get("/api/masters/").json()["count"], 0)

    def test_owner_updates_bio(self):
        self.api.force_authenticate(self.owner)
        resp = self.api.patch(f"/api/masters/my/{self.master.id}/", {"bio": "10 yillik tajriba"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.master.refresh_from_db()
        self.assertEqual(self.master.bio, "10 yillik tajriba")

    def test_other_owner_cannot_touch_master(self):
        self.api.force_authenticate(self.other_owner)
        resp = self.api.patch(f"/api/masters/my/{self.master.id}/", {"bio": "x"}, format="json")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(self.api.get(f"/api/masters/my/{self.master.id}/schedule/").status_code, 404)

    def test_client_forbidden(self):
        self.api.force_authenticate(self.client_user)
        self.assertEqual(self.api.get("/api/masters/my/").status_code, 403)


class ScheduleApiTests(BookingTestBase):
    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.api.force_authenticate(self.owner)
        self.url = f"/api/masters/my/{self.master.id}/schedule/"

    def test_put_replaces_whole_schedule(self):
        payload = {"schedules": [
            {"weekday": 0, "start_time": "10:00", "end_time": "17:00"},
            {"weekday": 2, "start_time": "09:00", "end_time": "13:00"},
        ]}
        resp = self.api.put(self.url, payload, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([row["weekday"] for row in resp.json()], [0, 2])
        self.assertEqual(WorkSchedule.objects.filter(master=self.master).count(), 2)

        got = self.api.get(self.url).json()
        self.assertEqual(len(got), 2)
        self.assertEqual(got[0]["start_time"], "10:00:00")

    def test_invalid_time_range_rejected_and_old_schedule_kept(self):
        before = WorkSchedule.objects.filter(master=self.master).count()
        payload = {"schedules": [{"weekday": 1, "start_time": "18:00", "end_time": "09:00"}]}
        self.assertEqual(self.api.put(self.url, payload, format="json").status_code, 400)
        self.assertEqual(WorkSchedule.objects.filter(master=self.master).count(), before)

    def test_duplicate_weekday_rejected(self):
        payload = {"schedules": [
            {"weekday": 1, "start_time": "09:00", "end_time": "12:00"},
            {"weekday": 1, "start_time": "13:00", "end_time": "17:00"},
        ]}
        self.assertEqual(self.api.put(self.url, payload, format="json").status_code, 400)

    def test_bad_weekday_and_non_list_rejected(self):
        bad_day = {"schedules": [{"weekday": 9, "start_time": "09:00", "end_time": "12:00"}]}
        self.assertEqual(self.api.put(self.url, bad_day, format="json").status_code, 400)
        self.assertEqual(self.api.put(self.url, {"schedules": "x"}, format="json").status_code, 400)

    def test_empty_list_clears_schedule(self):
        self.assertEqual(self.api.put(self.url, {"schedules": []}, format="json").status_code, 200)
        self.assertEqual(WorkSchedule.objects.filter(master=self.master).count(), 0)
