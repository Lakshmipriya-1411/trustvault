from django.db import models

GENESIS = "0" * 64  # "previous hash" of the very first entry


class AppendOnlyError(Exception):
    pass


class AppendOnlyQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise AppendOnlyError("Audit entries cannot be updated.")

    def delete(self):
        raise AppendOnlyError("Audit entries cannot be deleted.")


class AuditEntry(models.Model):
    """One row per event. Rows are never updated or deleted, and each row's hash
    covers the previous row's hash, so editing or removing history is detectable."""

    timestamp = models.DateTimeField(db_index=True)
    actor_username = models.CharField(max_length=150, db_index=True)
    actor_role = models.CharField(max_length=20, blank=True)
    action = models.CharField(max_length=40, db_index=True)
    outcome = models.CharField(max_length=10, db_index=True)  # "allowed" / "denied"
    document_id = models.UUIDField(null=True, blank=True, db_index=True)
    document_name = models.CharField(max_length=200, blank=True)
    target_username = models.CharField(max_length=150, blank=True)
    detail = models.TextField(blank=True)
    ip = models.CharField(max_length=64, blank=True)
    prev_hash = models.CharField(max_length=64, unique=True)  # unique => the chain cannot fork
    entry_hash = models.CharField(max_length=64)

    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        ordering = ["-id"]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise AppendOnlyError("Audit entries cannot be modified.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise AppendOnlyError("Audit entries cannot be deleted.")

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M:%S} {self.actor_username} {self.action} {self.outcome}"
