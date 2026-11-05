from django.db import InternalError, connection, transaction
from django.test import TestCase

from audit import service
from audit.models import AppendOnlyError, AuditEntry


class AuditIntegrity(TestCase):
    def setUp(self):
        for i in range(4):
            service.log(None, "upload", actor_name=f"user{i}", detail=f"event {i}")

    def tamper(self, sql, params):
        """Change the table behind the ORM's back, like an attacker with database access.
        On PostgreSQL the trigger must refuse; we then disable it to prove the hash chain
        still detects the damage even if the trigger is defeated."""
        if connection.vendor == "postgresql":
            with self.assertRaises(InternalError), transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(sql, params)
            with connection.cursor() as cursor:
                cursor.execute("ALTER TABLE audit_auditentry DISABLE TRIGGER USER")
        with connection.cursor() as cursor:
            cursor.execute(sql, params)

    def test_chain_is_valid_when_untouched(self):
        result = service.verify_chain()
        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 4)

    def test_orm_refuses_updates_and_deletes(self):
        entry = AuditEntry.objects.first()
        entry.detail = "changed"
        with self.assertRaises(AppendOnlyError):
            entry.save()
        with self.assertRaises(AppendOnlyError):
            entry.delete()
        with self.assertRaises(AppendOnlyError):
            AuditEntry.objects.all().delete()
        with self.assertRaises(AppendOnlyError):
            AuditEntry.objects.all().update(detail="x")

    def test_editing_a_row_behind_the_orms_back_is_detected(self):
        target = AuditEntry.objects.order_by("id")[1]
        self.tamper("UPDATE audit_auditentry SET detail = 'tampered' WHERE id = %s", [target.id])
        result = service.verify_chain()
        self.assertFalse(result["ok"])
        self.assertEqual(result["bad_id"], target.id)

    def test_removing_a_row_in_the_middle_is_detected(self):
        target = AuditEntry.objects.order_by("id")[1]
        self.tamper("DELETE FROM audit_auditentry WHERE id = %s", [target.id])
        self.assertFalse(service.verify_chain()["ok"])

    def test_chain_cannot_fork(self):
        first = AuditEntry.objects.order_by("id").first()
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError), transaction.atomic():
            AuditEntry.objects.create(timestamp=first.timestamp, actor_username="x", action="x",
                                      outcome="allowed", prev_hash=first.prev_hash, entry_hash="y")
