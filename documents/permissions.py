"""THE authorisation decision for documents lives here, and only here.

Every view that touches a document goes through authorize() -> can().
If can() is removed or weakened, tests in documents/tests.py fail."""

from django.db.models import Q
from django.http import Http404

from audit import service as audit

from .models import Document, Grant

ALLOWED_ACTIONS = {
    "owner": {"read", "download", "edit", "delete", "share"},
    "edit": {"read", "download", "edit"},
    "read": {"read", "download"},
}


def access_level(user, document):
    """'owner', 'edit', 'read' or None. Queries the database every time: no cache,
    so a revoked grant stops working on the very next request."""
    if document.owner_id == user.pk:
        return "owner"
    return Grant.objects.filter(document=document, user=user).values_list("level", flat=True).first()


def can(user, document, action):
    if user is None or not user.is_authenticated or not user.is_active:
        return False
    if user.role == "admin":
        return False  # administrators manage the system; they never read document contents
    if document.is_deleted:
        return False
    level = access_level(user, document)
    return level is not None and action in ALLOWED_ACTIONS[level]


def visible_to(user):
    """Documents this user may at least read. Used for lists and search."""
    if not user.is_authenticated or not user.is_active or user.role == "admin":
        return Document.objects.none()
    return (Document.objects.filter(is_deleted=False)
            .filter(Q(owner=user) | Q(grants__user=user))
            .distinct().defer("data"))


def authorize(request, pk, action, audit_action, with_data=False):
    """Fetch a document only if request.user may perform `action` on it.
    Otherwise log the refused attempt and answer 404 (same as 'does not exist')."""
    queryset = Document.objects.select_related("owner")
    if not with_data:
        queryset = queryset.defer("data")
    document = queryset.filter(pk=pk).first()
    if document is None or not can(request.user, document, action):
        audit.log(request, audit_action, "denied", document_id=pk,
                  document_name=document.name if document else "",
                  detail="no such document" if document is None else f"needs '{action}' access")
        raise Http404
    return document
