"""Security tests: one user must not reach another user's documents.
Each class maps to entries in THREATS.md."""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from audit.models import AuditEntry
from documents.models import Document, Grant
from documents.permissions import can
from documents.services import create_document

PW = "S3cure-pass-123"
PDF = b"%PDF-1.4\n%secret contents\n"


def make_user(name, role):
    return User.objects.create_user(name, password=PW, role=role)


class Base(TestCase):
    def setUp(self):
        self.owner1 = make_user("owner1", "owner")
        self.owner2 = make_user("owner2", "owner")
        self.viewer1 = make_user("viewer1", "viewer")
        self.viewer2 = make_user("viewer2", "viewer")
        self.admin = make_user("admin1", "admin")
        self.doc = create_document(self.owner1, "Salary letter", "hr", "pdf", "application/pdf", PDF)
        self.doc2 = create_document(self.owner2, "Other doc", "hr", "pdf", "application/pdf", PDF)

    def login(self, user):
        self.client.logout()
        self.assertTrue(self.client.login(username=user.username, password=PW))

    def grant(self, user, level="read", doc=None):
        return Grant.objects.create(document=doc or self.doc, user=user, level=level,
                                    granted_by=(doc or self.doc).owner)

    def doc_urls(self, doc=None):
        """Every document route: (method, url, data)."""
        doc = doc or self.doc
        pk = doc.pk
        return [
            ("get", reverse("document_detail", args=[pk]), {}),
            ("get", reverse("document_download", args=[pk]), {}),
            ("get", reverse("document_edit", args=[pk]), {}),
            ("post", reverse("document_edit", args=[pk]), {"name": "hacked", "category": "hr"}),
            ("post", reverse("document_delete", args=[pk]), {}),
            ("post", reverse("document_share", args=[pk]), {"username": "viewer2", "level": "edit"}),
        ]

    def call(self, method, url, data):
        return getattr(self.client, method)(url, data)


class StrangersCannotReachDocuments(Base):
    def test_user_without_grant_is_refused_on_every_route(self):
        for stranger in (self.viewer2, self.owner2):
            self.login(stranger)
            for method, url, data in self.doc_urls():
                with self.subTest(user=stranger.username, method=method, url=url):
                    self.assertEqual(self.call(method, url, data).status_code, 404)
        self.doc.refresh_from_db()
        self.assertFalse(self.doc.is_deleted)
        self.assertEqual(self.doc.name, "Salary letter")
        self.assertEqual(bytes(self.doc.data), PDF)
        self.assertFalse(Grant.objects.exists())

    def test_anonymous_is_sent_to_login_on_every_route(self):
        for method, url, data in self.doc_urls() + [("get", reverse("home"), {}),
                                                    ("get", reverse("document_upload"), {})]:
            with self.subTest(url=url):
                response = self.call(method, url, data)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/accounts/login/", response["Location"])

    def test_administrator_cannot_read_documents_even_with_a_grant(self):
        self.login(self.admin)
        self.assertEqual(self.client.get(reverse("document_download", args=[self.doc.pk])).status_code, 404)
        Grant.objects.create(document=self.doc, user=self.admin, level="edit", granted_by=self.owner1)
        self.assertFalse(can(self.admin, self.doc, "read"))
        self.assertEqual(self.client.get(reverse("document_download", args=[self.doc.pk])).status_code, 404)

    def test_search_and_list_never_reveal_other_peoples_documents(self):
        self.login(self.viewer2)
        for params in ({}, {"q": "Salary"}, {"owner": "owner1"}, {"category": "hr"}):
            response = self.client.get(reverse("home"), params)
            self.assertNotContains(response, "Salary letter")
            self.assertNotContains(response, str(self.doc.pk))

    def test_nonexistent_and_forbidden_look_identical(self):
        self.login(self.viewer2)
        forbidden = self.client.get(reverse("document_download", args=[self.doc.pk]))
        import uuid
        missing = self.client.get(reverse("document_download", args=[uuid.uuid4()]))
        self.assertEqual(forbidden.status_code, missing.status_code)


class GrantLevels(Base):
    def test_read_grant_can_download_but_not_change_delete_or_share(self):
        self.grant(self.viewer1, "read")
        self.login(self.viewer1)
        response = self.client.get(reverse("document_download", args=[self.doc.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, PDF)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        for method, url, data in self.doc_urls()[2:]:  # edit, delete, share
            with self.subTest(url=url, method=method):
                self.assertEqual(self.call(method, url, data).status_code, 404)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.name, "Salary letter")
        self.assertFalse(self.doc.is_deleted)

    def test_edit_grant_can_edit_but_not_delete_or_share(self):
        self.grant(self.viewer1, "edit")
        self.login(self.viewer1)
        response = self.client.post(reverse("document_edit", args=[self.doc.pk]),
                                    {"name": "Renamed", "category": "legal"})
        self.assertEqual(response.status_code, 302)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.name, "Renamed")
        self.assertEqual(self.client.post(reverse("document_delete", args=[self.doc.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("document_share", args=[self.doc.pk]),
                                          {"username": "viewer2", "level": "read"}).status_code, 404)
        self.assertFalse(Grant.objects.filter(user=self.viewer2).exists())


class RevocationIsImmediate(Base):
    def test_revoked_user_is_refused_on_the_very_next_request(self):
        grant = self.grant(self.viewer1, "edit")
        self.login(self.viewer1)
        url = reverse("document_download", args=[self.doc.pk])
        self.assertEqual(self.client.get(url).status_code, 200)  # still logged in, same session

        owner_client = type(self.client)()
        owner_client.login(username="owner1", password=PW)
        owner_client.post(reverse("document_revoke", args=[self.doc.pk, grant.pk]))

        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get(reverse("document_detail", args=[self.doc.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("document_edit", args=[self.doc.pk]),
                                          {"name": "x", "category": "hr"}).status_code, 404)
        self.assertNotContains(self.client.get(reverse("home")), "Salary letter")

    def test_cannot_revoke_a_grant_belonging_to_someone_elses_document(self):
        grant = self.grant(self.viewer1, "read")  # on owner1's doc
        self.login(self.owner2)  # owner2 owns doc2 and tries to use ITS url with owner1's grant id
        response = self.client.post(reverse("document_revoke", args=[self.doc2.pk, grant.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Grant.objects.filter(pk=grant.pk).exists())
        response = self.client.post(reverse("document_revoke", args=[self.doc.pk, grant.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Grant.objects.filter(pk=grant.pk).exists())

    def test_deleted_document_is_unreachable_and_content_is_destroyed(self):
        self.login(self.owner1)
        self.client.post(reverse("document_delete", args=[self.doc.pk]))
        self.assertEqual(self.client.get(reverse("document_download", args=[self.doc.pk])).status_code, 404)
        self.doc.refresh_from_db()
        self.assertEqual(bytes(self.doc.data), b"")
        self.assertTrue(self.doc.is_deleted)

    def test_deleting_removes_existing_grants(self):
        self.grant(self.viewer1, "read")
        self.login(self.owner1)
        self.client.post(reverse("document_delete", args=[self.doc.pk]))
        self.assertFalse(Grant.objects.filter(document=self.doc).exists())


class SharingRules(Base):
    def test_owner_can_grant_and_change_level(self):
        self.login(self.owner1)
        url = reverse("document_share", args=[self.doc.pk])
        self.client.post(url, {"username": "viewer1", "level": "read"})
        self.assertEqual(Grant.objects.get(user=self.viewer1).level, "read")
        self.client.post(url, {"username": "viewer1", "level": "edit"})
        self.assertEqual(Grant.objects.filter(user=self.viewer1).count(), 1)
        self.assertEqual(Grant.objects.get(user=self.viewer1).level, "edit")

    def test_invalid_share_form_attempt_is_recorded_in_the_audit_log(self):
        self.login(self.owner1)
        url = reverse("document_share", args=[self.doc.pk])
        self.client.post(url, {"username": "", "level": "read"})
        self.client.post(url, {"username": "viewer1", "level": "superuser"})
        denied = AuditEntry.objects.filter(action="grant", outcome="denied", actor_username="owner1")
        self.assertEqual(denied.count(), 2)
        self.assertFalse(Grant.objects.exists())

    def test_cannot_grant_to_admin_owner_unknown_or_deactivated_users(self):
        self.viewer2.is_active = False
        self.viewer2.save()
        self.login(self.owner1)
        url = reverse("document_share", args=[self.doc.pk])
        for name in ("admin1", "owner1", "nobody", "viewer2"):
            self.client.post(url, {"username": name, "level": "read"})
        self.assertFalse(Grant.objects.exists())


class AuditTrail(Base):
    def test_refused_attempts_are_recorded(self):
        self.login(self.viewer2)
        self.client.get(reverse("document_download", args=[self.doc.pk]))
        entry = AuditEntry.objects.filter(action="download", outcome="denied").first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.actor_username, "viewer2")
        self.assertEqual(entry.document_id, self.doc.pk)

    def test_successful_actions_are_recorded(self):
        self.login(self.owner1)
        self.client.get(reverse("document_download", args=[self.doc.pk]))
        self.client.post(reverse("document_share", args=[self.doc.pk]), {"username": "viewer1", "level": "read"})
        grant = Grant.objects.get(user=self.viewer1)
        self.client.post(reverse("document_revoke", args=[self.doc.pk, grant.pk]))
        self.client.post(reverse("document_edit", args=[self.doc.pk]), {"name": "New", "category": "hr"})
        self.client.post(reverse("document_delete", args=[self.doc.pk]))
        actions = set(AuditEntry.objects.filter(outcome="allowed").values_list("action", flat=True))
        for expected in ("login", "download", "grant", "revoke", "edit", "delete"):
            self.assertIn(expected, actions)

    def test_upload_is_recorded_and_rejected_upload_is_recorded(self):
        self.login(self.owner1)
        self.client.post(reverse("document_upload"), {"file": SimpleUploadedFile("a.pdf", PDF), "category": "hr"})
        self.client.post(reverse("document_upload"), {"file": SimpleUploadedFile("evil.exe", b"MZ"), "category": "hr"})
        self.assertTrue(AuditEntry.objects.filter(action="upload", outcome="allowed").exists())
        self.assertTrue(AuditEntry.objects.filter(action="upload", outcome="denied").exists())

    def test_admin_activity_view_lists_events_and_flags_repeated_refusals(self):
        self.login(self.viewer2)
        for _ in range(3):
            self.client.get(reverse("document_download", args=[self.doc.pk]))
        self.login(self.admin)
        response = self.client.get(reverse("activity"))
        self.assertContains(response, "viewer2")
        self.assertContains(response, "Worth noticing")
        self.assertContains(self.client.get(reverse("activity"), {"view": "denied"}), "needs &#x27;download&#x27; access")


class UploadValidation(Base):
    def upload(self, name, content, **extra):
        self.login(self.owner1)
        before = Document.objects.count()
        response = self.client.post(reverse("document_upload"),
                                    {"file": SimpleUploadedFile(name, content), "category": "hr", **extra})
        return response, Document.objects.count() - before

    def test_valid_pdf_is_accepted(self):
        response, added = self.upload("ok.pdf", PDF)
        self.assertEqual((response.status_code, added), (302, 1))

    def test_rejects_disallowed_extension(self):
        self.assertEqual(self.upload("run.exe", b"MZ....")[1], 0)
        self.assertEqual(self.upload("page.html", b"<script>alert(1)</script>")[1], 0)
        self.assertEqual(self.upload("noext", b"hello")[1], 0)

    def test_empty_upload_attempt_is_recorded_in_the_audit_log(self):
        self.upload("empty.pdf", b"")
        self.assertTrue(AuditEntry.objects.filter(action="upload", outcome="denied",
                                                  actor_username="owner1").exists())

    def test_rejects_content_that_does_not_match_extension(self):
        self.assertEqual(self.upload("fake.pdf", b"<script>alert(1)</script>")[1], 0)
        self.assertEqual(self.upload("fake.png", PDF)[1], 0)
        self.assertEqual(self.upload("fake.docx", b"PK\x03\x04notreallyzip")[1], 0)

    def test_rejects_empty_and_oversized_files(self):
        self.assertEqual(self.upload("empty.pdf", b"")[1], 0)
        with override_settings(MAX_UPLOAD_BYTES=100):
            self.assertEqual(self.upload("big.pdf", PDF + b"x" * 200)[1], 0)

    def test_path_in_filename_is_stripped(self):
        self.upload("../../etc/passwd.txt", b"hello")
        doc = Document.objects.order_by("-uploaded_at").first()
        self.assertEqual(doc.name, "passwd")

    def test_owner_cannot_be_chosen_by_the_client(self):
        self.upload("a.pdf", PDF, owner=str(self.owner2.pk), owner_id=str(self.owner2.pk))
        self.assertEqual(Document.objects.order_by("-uploaded_at").first().owner, self.owner1)

    def test_viewers_and_admins_cannot_upload(self):
        for user in (self.viewer1, self.admin):
            self.login(user)
            response = self.client.post(reverse("document_upload"),
                                        {"file": SimpleUploadedFile("a.pdf", PDF), "category": "hr"})
            self.assertEqual(response.status_code, 403)
        self.assertEqual(Document.objects.count(), 2)
