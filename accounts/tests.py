from django.test import TestCase
from django.urls import reverse

from accounts.models import User


class AccountTests(TestCase):
    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_logged_in_user_sees_home(self):
        User.objects.create_user("alice", password="S3cure-pass-123")
        self.client.login(username="alice", password="S3cure-pass-123")
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)

    def test_new_user_defaults_to_least_privileged_role(self):
        user = User.objects.create_user("bob", password="S3cure-pass-123")
        self.assertEqual(user.role, User.Role.VIEWER)

    def test_logout_requires_post(self):
        User.objects.create_user("carol", password="S3cure-pass-123")
        self.client.login(username="carol", password="S3cure-pass-123")
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
