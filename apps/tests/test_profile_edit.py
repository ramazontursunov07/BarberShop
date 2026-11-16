from rest_framework.test import APIClient
from django.test import TestCase

from apps.users.models import User


class ProfileEditTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("+998901112233", "parol12345", first_name="Ali", last_name="Valiyev",
                                             is_phone_verified=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_update_names(self):
        r = self.client.patch("/api/users/me/", {"first_name": " Vali ", "last_name": ""}, format="json")
        self.assertEqual(r.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual((self.user.first_name, self.user.last_name), ("Vali", ""))
        self.assertTrue(self.user.is_phone_verified)

    def test_blank_first_name_rejected(self):
        r = self.client.patch("/api/users/me/", {"first_name": "  "}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_phone_change_needs_current_password(self):
        r = self.client.patch("/api/users/me/", {"phone": "+998909998877"}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.client.patch("/api/users/me/", {"phone": "+998909998877", "current_password": "xato"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_phone_change_resets_verification(self):
        r = self.client.patch("/api/users/me/", {"phone": "+998909998877", "current_password": "parol12345"},
                              format="json")
        self.assertEqual(r.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone, "+998909998877")
        self.assertFalse(self.user.is_phone_verified)

    def test_phone_taken_and_bad_format(self):
        User.objects.create_user("+998905550000", "parol12345", first_name="B")
        for phone in ("+998905550000", "12345"):
            r = self.client.patch("/api/users/me/", {"phone": phone, "current_password": "parol12345"}, format="json")
            self.assertEqual(r.status_code, 400)

    def test_role_cannot_be_changed(self):
        self.client.patch("/api/users/me/", {"role": "admin"}, format="json")
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, "client")
