from rest_framework.test import APIClient

from apps.bookings.models import Booking
from apps.faq.models import FAQItem
from apps.products import services as product_services
from apps.products.models import Product, ProductReservation
from apps.reviews.models import Review

from .base import BookingTestBase


class ProductTests(BookingTestBase):
    def setUp(self):
        super().setUp()
        self.product = Product.objects.create(shop=self.shop, name="Soqol yog'i", price=40000, stock=3,
                                              category="Soqol")

    def test_reserve_reduces_stock(self):
        res = product_services.reserve(self.client_user, self.product.id, 2)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)
        self.assertEqual(res.total, 80000)

    def test_cannot_reserve_more_than_stock(self):
        with self.assertRaises(product_services.ProductError):
            product_services.reserve(self.client_user, self.product.id, 4)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

    def test_cancel_returns_stock_once(self):
        res = product_services.reserve(self.client_user, self.product.id, 2)
        product_services.cancel_by_client(self.client_user, res.id)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)
        with self.assertRaises(product_services.ProductError):
            product_services.cancel_by_client(self.client_user, res.id)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

    def test_other_client_cannot_cancel(self):
        res = product_services.reserve(self.client_user, self.product.id, 1)
        with self.assertRaises(product_services.ProductError):
            product_services.cancel_by_client(self.other_client, res.id)

    def test_owner_marks_picked_up(self):
        res = product_services.reserve(self.client_user, self.product.id, 1)
        product_services.set_status_by_owner(self.owner, res.id, "picked_up")
        res.refresh_from_db()
        self.assertEqual(res.status, ProductReservation.Status.PICKED_UP)
        with self.assertRaises(product_services.ProductError):
            product_services.set_status_by_owner(self.owner, res.id, "cancelled")

    def test_public_list_hides_stock_and_inactive(self):
        Product.objects.create(shop=self.shop, name="Yashirin", price=1000, stock=1, is_active=False)
        resp = APIClient().get("/api/products/", {"shop": self.shop.id})
        self.assertEqual(resp.status_code, 200)
        items = resp.json()["results"]
        self.assertEqual([p["name"] for p in items], ["Soqol yog'i"])
        self.assertNotIn("stock", items[0])
        self.assertTrue(items[0]["in_stock"])

    def test_owner_api_and_client_reservation_api(self):
        api = APIClient()
        api.force_authenticate(self.owner)
        created = api.post("/api/products/my/", {"shop": self.shop.id, "name": "Shampun", "price": 25000,
                                                  "stock": 5}, format="json")
        self.assertEqual(created.status_code, 201)

        api.force_authenticate(self.client_user)
        self.assertEqual(api.get("/api/products/my/").status_code, 403)
        res = api.post("/api/products/reservations/", {"product": created.json()["id"], "quantity": 2},
                       format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["total"], 50000)


class FAQTests(BookingTestBase):
    def test_public_list_and_owner_crud(self):
        FAQItem.objects.create(shop=self.shop, question="Karta qabul qilasizmi?", answer="Ha", position=2)
        FAQItem.objects.create(shop=self.shop, question="Yopiq", answer="x", is_active=False)
        api = APIClient()
        resp = api.get("/api/faq/", {"shop": self.shop.id})
        self.assertEqual([i["question"] for i in resp.json()], ["Karta qabul qilasizmi?"])
        self.assertEqual(api.get("/api/faq/").status_code, 400)

        api.force_authenticate(self.owner)
        created = api.post("/api/faq/my/", {"shop": self.shop.id, "question": "Bolalarga soch olasizmi?",
                                            "answer": "Ha"}, format="json")
        self.assertEqual(created.status_code, 201)
        api.force_authenticate(self.client_user)
        self.assertEqual(api.get("/api/faq/my/").status_code, 403)


class ShopRatingTests(BookingTestBase):
    def test_shop_list_and_detail_show_rating(self):
        for rating in (5, 4):
            booking = self.make_booking(hours_from_now=-48, status=Booking.Status.COMPLETED)
            Review.objects.create(booking=booking, client=self.client_user, rating=rating)
        api = APIClient()
        shop = api.get("/api/shops/").json()["results"][0]
        self.assertEqual(shop["avg_rating"], 4.5)
        self.assertEqual(shop["reviews_count"], 2)
        detail = api.get(f"/api/shops/{self.shop.id}/").json()
        self.assertEqual(detail["avg_rating"], 4.5)

    def test_shop_without_reviews(self):
        shop = APIClient().get("/api/shops/").json()["results"][0]
        self.assertIsNone(shop["avg_rating"])
        self.assertEqual(shop["reviews_count"], 0)
