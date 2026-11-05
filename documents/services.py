import hashlib

from .models import Document


def create_document(owner, name, category, extension, content_type, data):
    return Document.objects.create(
        name=name or "Untitled", category=category, owner=owner,
        content_type=content_type, extension=extension, size=len(data),
        sha256=hashlib.sha256(data).hexdigest(), data=data,
    )
