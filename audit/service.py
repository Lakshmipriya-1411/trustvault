import hashlib
import json
from datetime import timedelta
from datetime import timezone as dt_timezone

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import GENESIS, AuditEntry

HASHED_FIELDS = (
    "actor_username", "actor_role", "action", "outcome",
    "document_id", "document_name", "target_username", "detail", "ip",
)


def client_ip(request):
    if request is None:
        return ""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ip = forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR", "")
    return ip[:64]


def compute_hash(prev_hash, timestamp, fields):
    values = [prev_hash, timestamp.astimezone(dt_timezone.utc).isoformat()]
    for name in HASHED_FIELDS:
        value = fields[name]
        values.append("" if value is None else str(value))
    payload = json.dumps(values, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _append(fields):
    for _ in range(10):
        try:
            with transaction.atomic():
                last = AuditEntry.objects.order_by("-id").values_list("entry_hash", flat=True).first()
                prev = last or GENESIS
                now = timezone.now()
                entry_hash = compute_hash(prev, now, fields)
                return AuditEntry.objects.create(
                    timestamp=now, prev_hash=prev, entry_hash=entry_hash, **fields
                )
        except IntegrityError:
            continue  # someone else appended at the same moment; re-read the head and retry
    raise RuntimeError("Could not append audit entry")


def log(request, action, outcome="allowed", *, actor=None, actor_name="", document=None,
        document_id=None, document_name="", target="", detail=""):
    """Write one audit entry. Called for successes AND refused attempts."""
    if actor is None and request is not None and getattr(request, "user", None) is not None \
            and request.user.is_authenticated:
        actor = request.user
    if document is not None:
        document_id = document.pk
        document_name = document.name
    fields = {
        "actor_username": (actor.username if actor else actor_name or "anonymous")[:150],
        "actor_role": getattr(actor, "role", "") if actor else "",
        "action": action,
        "outcome": outcome,
        "document_id": document_id,
        "document_name": (document_name or "")[:200],
        "target_username": (target or "")[:150],
        "detail": (detail or "")[:500],
        "ip": client_ip(request),
    }
    return _append(fields)


def verify_chain():
    """Recompute every hash from the start. Detects edited rows and removed rows
    (but not removal of the newest rows: see THREATS.md)."""
    prev = GENESIS
    count = 0
    for entry in AuditEntry.objects.order_by("id").iterator():
        count += 1
        fields = {name: getattr(entry, name) for name in HASHED_FIELDS}
        expected = compute_hash(entry.prev_hash, entry.timestamp, fields)
        if entry.prev_hash != prev or entry.entry_hash != expected:
            return {"ok": False, "bad_id": entry.id, "count": count, "head": prev}
        prev = entry.entry_hash
    return {"ok": True, "bad_id": None, "count": count, "head": prev}


def recent_failed_logins(username, minutes):
    since = timezone.now() - timedelta(minutes=minutes)
    return AuditEntry.objects.filter(
        action="login_failed", actor_username=username[:150], timestamp__gte=since
    ).count()
