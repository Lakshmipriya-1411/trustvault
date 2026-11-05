from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from audit.models import AuditEntry

PW = "S3cure-pass-123"


class AccountTests(TestCase):
    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_logged_in_user_sees_home(self):
        User.objects.create_user("alice", password=PW)
        self.client.login(username="alice", password=PW)
        self.assertEqual(self.client.get(reverse("home")).status_code, 200)

    def test_new_user_defaults_to_least_privileged_role(self):
        self.assertEqual(User.objects.create_user("bob", password=PW).role, User.Role.VIEWER)

    def test_logout_requires_post(self):
        User.objects.create_user("carol", password=PW)
        self.client.login(username="carol", password=PW)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)

    def test_admin_pages_refuse_non_admins_and_log_it(self):
        User.objects.create_user("owner", password=PW, role="owner")
        self.client.login(username="owner", password=PW)
        for name in ("activity", "user_list", "user_create"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)
        self.assertTrue(AuditEntry.objects.filter(action="forbidden_page", outcome="denied").exists())

    def test_only_admin_can_create_users_and_role_comes_from_admin_form(self):
        User.objects.create_user("admin", password=PW, role="admin")
        self.client.login(username="admin", password=PW)
        response = self.client.post(reverse("user_create"),
                                    {"username": "newbie", "role": "owner", "password": "Another-Pass-987"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(User.objects.get(username="newbie").role, "owner")

    def test_login_is_locked_after_repeated_failures(self):
        User.objects.create_user("dave", password=PW)
        for _ in range(5):
            self.client.post(reverse("login"), {"username": "dave", "password": "wrong"})
        # even the CORRECT password is refused while locked
        response = self.client.post(reverse("login"), {"username": "dave", "password": PW})
        self.assertContains(response, "Too many failed attempts")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_deactivated_user_is_logged_out_on_next_request(self):
        user = User.objects.create_user("erin", password=PW)
        self.client.login(username="erin", password=PW)
        self.assertEqual(self.client.get(reverse("home")).status_code, 200)
        user.is_active = False
        user.save()
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])
