"""Egasi o'z sartaroshxonasi profilini boshqaradi: tahrirlash va rasm o'chirish."""
from django.core.files.base import ContentFile
from rest_framework.test import APIClient

from apps.shops.models import ShopPhoto
from apps.tests.base import BookingTestBase, make_user


def _photo(shop):
    return ShopPhoto.objects.create(shop=shop, image=ContentFile(b"x", name="p.jpg"))


class ShopProfileTests(BookingTestBase):
    def auth(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_owner_updates_own_shop(self):
        res = self.auth(self.owner).patch(
            f"/api/shops/my/{self.shop.id}/",
            {"name": "Yangi nom", "phone": "+998901234567", "description": "Tavsif", "district": "Chilonzor",
             "opens_at": "08:00", "closes_at": "20:00", "latitude": "41.311081", "longitude": "69.240562"},
            format="json")
        self.assertEqual(res.status_code, 200, res.content)
        self.shop.refresh_from_db()
        self.assertEqual(self.shop.name, "Yangi nom")
        self.assertEqual(str(self.shop.latitude), "41.311081")

    def test_invalid_hours_rejected(self):
        res = self.auth(self.owner).patch(f"/api/shops/my/{self.shop.id}/",
                                          {"opens_at": "20:00", "closes_at": "08:00"}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_other_owner_cannot_edit(self):
        other = make_user("+998900000099", "Boshqa egasi", "owner")
        res = self.auth(other).patch(f"/api/shops/my/{self.shop.id}/", {"name": "Hack"}, format="json")
        self.assertEqual(res.status_code, 404)
        self.shop.refresh_from_db()
        self.assertEqual(self.shop.name, "Demo")

    def test_client_cannot_edit(self):
        res = self.auth(self.client_user).patch(f"/api/shops/my/{self.shop.id}/", {"name": "Hack"}, format="json")
        self.assertEqual(res.status_code, 403)

    def test_owner_deletes_own_photo(self):
        photo = _photo(self.shop)
        res = self.auth(self.owner).delete(f"/api/shops/photos/{photo.id}/")
        self.assertEqual(res.status_code, 204)
        self.assertFalse(ShopPhoto.objects.filter(pk=photo.pk).exists())

    def test_other_owner_cannot_delete_photo(self):
        photo = _photo(self.shop)
        other = make_user("+998900000099", "Boshqa egasi", "owner")
        res = self.auth(other).delete(f"/api/shops/photos/{photo.id}/")
        self.assertEqual(res.status_code, 404)
        self.assertTrue(ShopPhoto.objects.filter(pk=photo.pk).exists())

    def test_client_cannot_delete_photo(self):
        photo = _photo(self.shop)
        res = self.auth(self.client_user).delete(f"/api/shops/photos/{photo.id}/")
        self.assertEqual(res.status_code, 403)
        self.assertTrue(ShopPhoto.objects.filter(pk=photo.pk).exists())
