import io
import tempfile
from datetime import time
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from rest_framework.test import APITestCase

from apps.shops.models import Shop, ShopPhoto


User = get_user_model()
TEMP_MEDIA = tempfile.mkdtemp()  # test rasmlari haqiqiy media/ papkasiga tushmasin


def make_image(name="photo.png"):
    buf = io.BytesIO()
    Image.new("RGB", (20, 20), (200, 50, 50)).save(buf, format="PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class ShopPhotoUploadTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            phone="+998901110001", password="x12345678", first_name="Egasi1", role="owner")
        self.other_owner = User.objects.create_user(
            phone="+998901110002", password="x12345678", first_name="Egasi2", role="owner")
        self.client_user = User.objects.create_user(
            phone="+998901110003", password="x12345678", first_name="Mijoz", role="client")

        common = dict(phone="+998901110000", city="Toshkent", address="Ko'cha 1",
                      opens_at=time(9, 0), closes_at=time(19, 0))
        self.shop = Shop.objects.create(owner=self.owner, name="Mening shop", **common)
        self.foreign_shop = Shop.objects.create(owner=self.other_owner, name="Begona shop", **common)
        self.url = reverse("shop-photo-create")

    def _post(self, shop_id, image):
        return self.client.post(self.url, {"shop": shop_id, "image": image}, format="multipart")

    def test_owner_uploads_photo_to_own_shop(self):
        self.client.force_authenticate(self.owner)
        resp = self._post(self.shop.id, make_image())
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(ShopPhoto.objects.filter(shop=self.shop).count(), 1)
        self.assertEqual(Shop.objects.count(), 2)  # eski xato: rasm o'rniga yangi Shop yaratilardi

    def test_owner_cannot_upload_to_foreign_shop(self):
        self.client.force_authenticate(self.owner)
        resp = self._post(self.foreign_shop.id, make_image())
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(ShopPhoto.objects.count(), 0)

    def test_client_role_is_forbidden(self):
        self.client.force_authenticate(self.client_user)
        resp = self._post(self.shop.id, make_image())
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(ShopPhoto.objects.count(), 0)

    def test_anonymous_is_rejected(self):
        resp = self._post(self.shop.id, make_image())
        self.assertIn(resp.status_code, (401, 403))
        self.assertEqual(ShopPhoto.objects.count(), 0)

    def test_non_image_file_is_rejected(self):
        self.client.force_authenticate(self.owner)
        fake = SimpleUploadedFile("x.png", b"bu rasm emas", content_type="image/png")
        resp = self._post(self.shop.id, fake)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(ShopPhoto.objects.count(), 0)

    def test_too_large_image_is_rejected(self):
        self.client.force_authenticate(self.owner)
        with mock.patch("apps.shops.serializers.MAX_PHOTO_BYTES", 10):
            resp = self._post(self.shop.id, make_image())
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(ShopPhoto.objects.count(), 0)

    def test_uploaded_photo_appears_in_shop_detail(self):
        self.client.force_authenticate(self.owner)
        self._post(self.shop.id, make_image())
        # ommaviy ro'yxat faqat tasdiqlangan shop'larni ko'rsatadi
        Shop.objects.filter(pk=self.shop.pk).update(is_approved=True)
        self.client.force_authenticate(None)
        resp = self.client.get(reverse("shop-detail", args=[self.shop.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data["photos"]), 1)
