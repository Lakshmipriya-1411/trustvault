import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Category(models.TextChoices):
    GENERAL = "general", "General"
    CONTRACT = "contract", "Contract"
    HR = "hr", "HR"
    FINANCE = "finance", "Finance"
    LEGAL = "legal", "Legal"
    OTHER = "other", "Other"


class Level(models.TextChoices):
    READ = "read", "Read"
    EDIT = "edit", "Edit"


class Document(models.Model):
    # Random UUID: ids cannot be guessed or counted. This is NOT the security control;
    # documents.permissions.can() is.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.GENERAL)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                              related_name="owned_documents")
    content_type = models.CharField(max_length=100)
    extension = models.CharField(max_length=10)
    size = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    data = models.BinaryField(editable=False)  # file bytes live in the database, not on a public path
    uploaded_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name

    @property
    def download_name(self):
        suffix = "." + self.extension
        return self.name if self.name.lower().endswith(suffix) else self.name + suffix


class Grant(models.Model):
    """One row = one person has one level of access to one document.
    Revoking deletes the row, so the next request is refused."""

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="grants")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="grants_received")
    level = models.CharField(max_length=10, choices=Level.choices)
    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name="grants_given")
    granted_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["document", "user"], name="one_grant_per_user")]
