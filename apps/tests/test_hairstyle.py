"""Selfi orqali soch turmagi: rasm tozalash, model javobini tekshirish, API."""
import io
import json
from unittest import mock

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from apps.insights import hairstyle
from apps.insights.hairstyle import InvalidImage, NoFaceDetected

from .base import BookingTestBase


def make_image(fmt="JPEG", size=(1600, 1200), exif=False):
    img = Image.new("RGB", size, (120, 90, 60))
    buf = io.BytesIO()
    kwargs = {}
    if exif:
        e = Image.Exif()
        e[0x010F] = "SecretMaker"  # Make
        kwargs["exif"] = e
    img.save(buf, format=fmt, **kwargs)
    return buf.getvalue()


def vision(shape="oval", confidence=0.9, detected=True):
    return lambda jpeg: json.dumps({"face_detected": detected, "face_shape": shape, "confidence": confidence})


class SanitizeTests(BookingTestBase):
    def test_downscales_and_strips_exif(self):
        out = hairstyle.sanitize_image(make_image(size=(2000, 1000), exif=True))
        img = Image.open(io.BytesIO(out))
        self.assertEqual(img.format, "JPEG")
        self.assertLessEqual(max(img.size), hairstyle.MAX_SIDE)
        self.assertEqual(len(img.getexif()), 0)

    def test_accepts_png_and_webp(self):
        for fmt in ("PNG", "WEBP"):
            self.assertEqual(Image.open(io.BytesIO(hairstyle.sanitize_image(make_image(fmt)))).format, "JPEG")

    def test_rejects_non_image_and_other_formats(self):
        with self.assertRaises(InvalidImage):
            hairstyle.sanitize_image(b"not an image")
        with self.assertRaises(InvalidImage):
            hairstyle.sanitize_image(make_image("GIF"))

    def test_rejects_huge_pixel_count(self):
        with mock.patch.object(hairstyle, "MAX_PIXELS", 100):
            with self.assertRaises(InvalidImage):
                hairstyle.sanitize_image(make_image(size=(50, 50)))


class ParseTests(BookingTestBase):
    def test_valid_and_fenced_json(self):
        self.assertEqual(hairstyle.parse_detection('```json\n{"face_detected": true, "face_shape": "Round", '
                                                   '"confidence": 0.7}\n```')["shape"], "round")

    def test_confidence_clamped(self):
        r = hairstyle.parse_detection('{"face_detected": true, "face_shape": "oval", "confidence": 7}')
        self.assertEqual(r["confidence"], 1.0)

    def test_no_face_unknown_shape_and_garbage(self):
        for raw in ('{"face_detected": false}', '{"face_detected": true, "face_shape": "triangle"}', "salom", "[]"):
            with self.assertRaises(NoFaceDetected):
                hairstyle.parse_detection(raw)


class RecommendTests(BookingTestBase):
    def test_every_shape_has_table_entries(self):
        for key, info in hairstyle.SHAPES.items():
            self.assertTrue(info["hairstyles"], key)
            self.assertTrue(info["name"], key)

    def test_recommendation_comes_from_table_not_model(self):
        res = hairstyle.recommend_from_selfie(make_image(), vision_call=vision("round"))
        self.assertEqual(res["face_shape"], "round")
        self.assertEqual(res["face_shape_name"], "Yumaloq")
        self.assertEqual([h["name"] for h in res["hairstyles"]],
                         [n for n, _ in hairstyle.SHAPES["round"]["hairstyles"]])
        self.assertNotIn("note", res)

    def test_low_confidence_adds_note(self):
        res = hairstyle.recommend_from_selfie(make_image(), vision_call=vision("oval", 0.2))
        self.assertIn("note", res)

    def test_model_receives_sanitized_jpeg(self):
        seen = {}

        def spy(jpeg):
            seen["fmt"] = Image.open(io.BytesIO(jpeg)).format
            return vision()(jpeg)

        hairstyle.recommend_from_selfie(make_image("PNG"), vision_call=spy)
        self.assertEqual(seen["fmt"], "JPEG")


class HairstyleApiTests(BookingTestBase):
    def setUp(self):
        super().setUp()
        cache.clear()  # so'rovlar chegarasi (throttle) testlar orasida to'lib qolmasin
        self.api = APIClient()
        self.url = reverse("insights-hairstyle")

    def post(self, data, name="selfie.jpg", ctype="image/jpeg"):
        return self.api.post(self.url, {"photo": SimpleUploadedFile(name, data, content_type=ctype)},
                             format="multipart")

    def test_requires_login(self):
        self.assertEqual(self.post(make_image()).status_code, 401)

    def test_success(self):
        self.api.force_authenticate(self.client_user)
        with mock.patch.object(hairstyle, "_vision_llm", vision("square")):
            r = self.post(make_image())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["face_shape"], "square")

    def test_missing_file_bad_image_too_big_no_face(self):
        self.api.force_authenticate(self.client_user)
        self.assertEqual(self.api.post(self.url, {}, format="multipart").status_code, 400)
        self.assertEqual(self.post(b"garbage").status_code, 400)
        with mock.patch("apps.insights.views.MAX_UPLOAD_BYTES", 10):
            self.assertEqual(self.post(make_image()).status_code, 413)
        with mock.patch.object(hairstyle, "_vision_llm", vision(detected=False)):
            self.assertEqual(self.post(make_image()).status_code, 422)

    def test_provider_errors_mapped(self):
        from openai import APIConnectionError, RateLimitError
        self.api.force_authenticate(self.client_user)
        with mock.patch.object(hairstyle, "_vision_llm",
                               side_effect=APIConnectionError(request=mock.Mock())):
            self.assertEqual(self.post(make_image()).status_code, 502)
        err = RateLimitError("limit", response=mock.Mock(status_code=429, headers={}), body=None)
        with mock.patch.object(hairstyle, "_vision_llm", side_effect=err):
            self.assertEqual(self.post(make_image()).status_code, 429)
