from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APIClient

from apps.ai import services as availability
from apps.bookings.models import Booking
from apps.bookings.services import cancel_by_client
from apps.promotions import services as promotions
from apps.promotions.models import GiftCertificate, LoyaltyProgram, PromoCode

from .base import BookingTestBase


class PromotionsBase(BookingTestBase):
    def setUp(self):
        super().setUp()
        self.day = (timezone.now() + timedelta(days=7)).date().isoformat()

    def book(self, time="10:00", user=None, **kwargs):
        return availability.create_booking(
            user or self.client_user, self.master.id, self.service.id, self.day, time, **kwargs
        )


class PromoCodeTests(PromotionsBase):
    def test_percent_promo_applies(self):
        promo = PromoCode.objects.create(shop=self.shop, code="new10", percent=10)
        result = self.book(promo_code="NEW10")
        self.assertEqual(result["price"], 45000)
        self.assertEqual(result["discount_kind"], "promo")
        booking = Booking.objects.get(pk=result["booking_id"])
        self.assertEqual(booking.promo_code, promo)
        self.assertEqual(booking.discount_amount, 5000)

    def test_fixed_amount_promo(self):
        PromoCode.objects.create(shop=self.shop, code="MINUS15", amount=15000)
        self.assertEqual(self.book(promo_code="minus15")["price"], 35000)

    def test_invalid_promo_creates_no_booking(self):
        result = self.book(promo_code="YOQ")
        self.assertIn("error", result)
        self.assertEqual(Booking.objects.count(), 0)

    def test_expired_promo_rejected(self):
        PromoCode.objects.create(shop=self.shop, code="OLD", percent=10,
                                 valid_until=timezone.now() - timedelta(days=1))
        self.assertIn("error", self.book(promo_code="OLD"))

    def test_once_per_user(self):
        PromoCode.objects.create(shop=self.shop, code="ONCE", percent=10)
        self.assertNotIn("error", self.book("10:00", promo_code="ONCE"))
        self.assertIn("error", self.book("11:00", promo_code="ONCE"))
        # boshqa mijoz foydalana oladi
        self.assertNotIn("error", self.book("12:00", user=self.other_client, promo_code="ONCE"))

    def test_cancelled_booking_releases_promo(self):
        PromoCode.objects.create(shop=self.shop, code="ONCE", percent=10)
        first = self.book("10:00", promo_code="ONCE")
        cancel_by_client(self.client_user, first["booking_id"])
        self.assertNotIn("error", self.book("11:00", promo_code="ONCE"))

    def test_max_uses(self):
        PromoCode.objects.create(shop=self.shop, code="LIMIT", percent=10, max_uses=1)
        self.assertNotIn("error", self.book("10:00", promo_code="LIMIT"))
        self.assertIn("error", self.book("11:00", user=self.other_client, promo_code="LIMIT"))

    def test_first_visit_only(self):
        PromoCode.objects.create(shop=self.shop, code="FIRST", percent=10, first_visit_only=True)
        self.make_booking(hours_from_now=-48, status=Booking.Status.COMPLETED)
        self.assertIn("error", self.book(promo_code="FIRST"))
        self.assertNotIn("error", self.book("11:00", user=self.other_client, promo_code="FIRST"))


class LoyaltyTests(PromotionsBase):
    def setUp(self):
        super().setUp()
        LoyaltyProgram.objects.create(shop=self.shop, every_n_visits=2, discount_percent=50)

    def test_no_reward_before_threshold(self):
        self.make_booking(hours_from_now=-48, status=Booking.Status.COMPLETED)
        result = self.book()
        self.assertFalse(result["loyalty_applied"])
        self.assertEqual(result["price"], 50000)

    def test_reward_after_n_visits_and_used_once(self):
        self.make_booking(hours_from_now=-72, status=Booking.Status.COMPLETED)
        self.make_booking(hours_from_now=-48, status=Booking.Status.COMPLETED)
        status = promotions.loyalty_status(self.client_user, self.shop.id)
        self.assertTrue(status["reward_available"])

        first = self.book("10:00")
        self.assertTrue(first["loyalty_applied"])
        self.assertEqual(first["price"], 25000)
        # mukofot ishlatildi: keyingi bron to'liq narxda
        second = self.book("11:00")
        self.assertFalse(second["loyalty_applied"])
        self.assertEqual(second["price"], 50000)

    def test_cancel_restores_reward(self):
        self.make_booking(hours_from_now=-72, status=Booking.Status.COMPLETED)
        self.make_booking(hours_from_now=-48, status=Booking.Status.COMPLETED)
        first = self.book("10:00")
        cancel_by_client(self.client_user, first["booking_id"])
        self.assertTrue(self.book("11:00")["loyalty_applied"])

    def test_best_discount_wins_and_promo_not_stacked(self):
        self.make_booking(hours_from_now=-72, status=Booking.Status.COMPLETED)
        self.make_booking(hours_from_now=-48, status=Booking.Status.COMPLETED)
        PromoCode.objects.create(shop=self.shop, code="SMALL", percent=10)
        result = self.book(promo_code="SMALL")
        self.assertEqual(result["discount_kind"], "loyalty")
        self.assertEqual(result["price"], 25000)
        self.assertIsNone(result["promo_code"])
        self.assertTrue(result["notes"])


class GiftCertificateTests(PromotionsBase):
    def test_certificate_reduces_price_and_balance(self):
        cert = promotions.issue_certificate(self.shop, 30000)
        result = self.book(certificate_code=cert.code)
        self.assertEqual(result["price"], 20000)
        self.assertEqual(result["certificate_amount"], 30000)
        self.assertEqual(promotions.certificate_balance(cert), 0)

    def test_certificate_larger_than_price_keeps_remainder(self):
        cert = promotions.issue_certificate(self.shop, 80000)
        result = self.book(certificate_code=cert.code)
        self.assertEqual(result["price"], 0)
        self.assertEqual(promotions.certificate_balance(cert), 30000)
        again = self.book("11:00", certificate_code=cert.code)
        self.assertEqual(again["price"], 20000)
        self.assertEqual(promotions.certificate_balance(cert), 0)

    def test_cancel_refunds_certificate(self):
        cert = promotions.issue_certificate(self.shop, 30000)
        result = self.book(certificate_code=cert.code)
        cancel_by_client(self.client_user, result["booking_id"])
        self.assertEqual(promotions.certificate_balance(cert), 30000)

    def test_empty_certificate_rejected(self):
        cert = promotions.issue_certificate(self.shop, 50000)
        self.book(certificate_code=cert.code)
        self.assertIn("error", self.book("11:00", certificate_code=cert.code))

    def test_certificate_from_other_shop_rejected(self):
        from apps.shops.models import Shop
        other = Shop.objects.create(owner=self.owner, name="Boshqa", phone="+998900000009", city="Toshkent",
                                    address="x", opens_at=self.shop.opens_at, closes_at=self.shop.closes_at,
                                    is_approved=True)
        cert = promotions.issue_certificate(other, 30000)
        self.assertIn("error", self.book(certificate_code=cert.code))

    def test_expired_and_unknown_certificate(self):
        cert = GiftCertificate.objects.create(shop=self.shop, amount=30000,
                                              expires_at=timezone.now() - timedelta(days=1))
        self.assertIn("error", self.book(certificate_code=cert.code))
        self.assertIn("error", self.book(certificate_code="GC-XXXX-XXXX"))

    def test_code_format_is_unique(self):
        codes = {promotions.issue_certificate(self.shop, 10000).code for _ in range(20)}
        self.assertEqual(len(codes), 20)
        self.assertTrue(all(c.startswith("GC-") for c in codes))


class PromotionsApiTests(PromotionsBase):
    def setUp(self):
        super().setUp()
        self.api = APIClient()

    def test_quote_does_not_create_booking(self):
        PromoCode.objects.create(shop=self.shop, code="NEW10", percent=10)
        self.api.force_authenticate(self.client_user)
        resp = self.api.post("/api/promotions/quote/", {
            "service": self.service.id, "date": self.day, "start_time": "10:00", "promo_code": "NEW10",
        }, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["price"], 45000)
        self.assertEqual(Booking.objects.count(), 0)

    def test_booking_api_accepts_promo(self):
        PromoCode.objects.create(shop=self.shop, code="NEW10", percent=10)
        self.api.force_authenticate(self.client_user)
        resp = self.api.post("/api/bookings/", {
            "master": self.master.id, "service": self.service.id, "date": self.day,
            "start_time": "10:00", "promo_code": "NEW10",
        }, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["price"], 45000)

    def test_owner_creates_promo_only_for_own_shop(self):
        self.api.force_authenticate(self.owner)
        ok = self.api.post("/api/promotions/my/promo-codes/",
                           {"shop": self.shop.id, "code": "yangi", "percent": 15}, format="json")
        self.assertEqual(ok.status_code, 201)
        self.assertEqual(ok.json()["code"], "YANGI")

        both = self.api.post("/api/promotions/my/promo-codes/",
                             {"shop": self.shop.id, "code": "X", "percent": 15, "amount": 1000}, format="json")
        self.assertEqual(both.status_code, 400)

        self.api.force_authenticate(self.other_client)
        self.assertEqual(self.api.get("/api/promotions/my/promo-codes/").status_code, 403)

    def test_owner_issues_certificate_and_client_checks_it(self):
        self.api.force_authenticate(self.owner)
        created = self.api.post("/api/promotions/my/certificates/",
                                {"shop": self.shop.id, "amount": 100000, "recipient_name": "Ali"}, format="json")
        self.assertEqual(created.status_code, 201)
        code = created.json()["code"]

        self.api.force_authenticate(self.client_user)
        check = self.api.get("/api/promotions/certificates/check/", {"code": code})
        self.assertEqual(check.status_code, 200)
        self.assertEqual(check.json()["balance"], 100000)
        self.assertEqual(self.api.get("/api/promotions/certificates/check/", {"code": "yoq"}).status_code, 404)

    def test_loyalty_upsert_and_status(self):
        self.api.force_authenticate(self.owner)
        resp = self.api.put("/api/promotions/my/loyalty/",
                            {"shop": self.shop.id, "every_n_visits": 5, "discount_percent": 20}, format="json")
        self.assertEqual(resp.status_code, 201)
        resp = self.api.put("/api/promotions/my/loyalty/",
                            {"shop": self.shop.id, "every_n_visits": 4, "discount_percent": 25}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(LoyaltyProgram.objects.filter(shop=self.shop).count(), 1)

        self.api.force_authenticate(self.client_user)
        status = self.api.get("/api/promotions/loyalty/", {"shop": self.shop.id})
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["visits_to_next_reward"], 4)

    def test_public_offers_show_only_public_promos(self):
        PromoCode.objects.create(shop=self.shop, code="OCHIQ", percent=10, is_public=True)
        PromoCode.objects.create(shop=self.shop, code="MAXFIY", percent=30)
        resp = self.api.get("/api/promotions/offers/", {"shop": self.shop.id})
        self.assertEqual([p["code"] for p in resp.json()], ["OCHIQ"])
        