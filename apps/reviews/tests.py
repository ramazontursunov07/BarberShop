from rest_framework.test import APIClient

from apps.bookings.models import Booking
from apps.bookings.tests import BookingTestBase

from .models import Review

URL = "/api/reviews/"


class ReviewApiTests(BookingTestBase):
    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.api.force_authenticate(self.client_user)

    def completed_booking(self, client=None):
        return self.make_booking(client=client, hours_from_now=-5, status=Booking.Status.COMPLETED)

    def post(self, booking, rating=5, comment="Zo'r xizmat"):
        return self.api.post(
            URL, {"booking": booking.id, "rating": rating, "comment": comment}, format="json"
        )

    def test_client_reviews_completed_booking(self):
        booking = self.completed_booking()
        resp = self.post(booking)
        self.assertEqual(resp.status_code, 201)
        review = Review.objects.get(booking=booking)
        self.assertEqual(review.client, self.client_user)
        self.assertEqual(review.rating, 5)
        self.assertEqual(resp.json()["client_name"], "Mijoz")

    def test_pending_booking_rejected(self):
        booking = self.make_booking(hours_from_now=24)
        self.assertEqual(self.post(booking).status_code, 400)

    def test_someone_elses_booking_rejected(self):
        booking = self.completed_booking(client=self.other_client)
        self.assertEqual(self.post(booking).status_code, 400)
        self.assertEqual(Review.objects.count(), 0)

    def test_duplicate_review_rejected(self):
        booking = self.completed_booking()
        self.assertEqual(self.post(booking).status_code, 201)
        self.assertEqual(self.post(booking).status_code, 400)
        self.assertEqual(Review.objects.count(), 1)

    def test_rating_must_be_1_to_5(self):
        booking = self.completed_booking()
        self.assertEqual(self.post(booking, rating=0).status_code, 400)
        self.assertEqual(self.post(booking, rating=6).status_code, 400)
        self.assertEqual(Review.objects.count(), 0)

    def test_post_requires_auth_but_list_is_public(self):
        booking = self.completed_booking()
        anon = APIClient()
        self.assertEqual(anon.post(URL, {"booking": booking.id, "rating": 5}, format="json").status_code, 401)
        self.assertEqual(anon.get(URL).status_code, 200)

    def test_public_list_hides_phone_and_filters_by_master(self):
        booking = self.completed_booking()
        self.post(booking)
        anon = APIClient()

        resp = anon.get(URL, {"master": self.master.id})
        self.assertEqual(resp.json()["count"], 1)
        self.assertNotIn("+998", resp.content.decode())
        self.assertEqual(anon.get(URL, {"master": 99999}).json()["count"], 0)
        self.assertEqual(anon.get(URL, {"shop": "abc"}).status_code, 400)

    def test_my_reviews_only_own(self):
        mine = self.completed_booking()
        theirs = self.completed_booking(client=self.other_client)
        Review.objects.create(booking=mine, client=self.client_user, rating=4)
        Review.objects.create(booking=theirs, client=self.other_client, rating=2)
        resp = self.api.get(URL + "my/")
        self.assertEqual(resp.json()["count"], 1)
        self.assertEqual(resp.json()["results"][0]["rating"], 4)
