from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import render
from django.utils import timezone

from accounts.decorators import role_required
from accounts.models import User

from . import service
from .models import AuditEntry

PERMISSION_ACTIONS = ("grant", "revoke")


@role_required(User.Role.ADMIN)
def activity(request):
    """Administrator's view: all activity, permission changes, refused attempts."""
    view = request.GET.get("view", "all")
    entries = AuditEntry.objects.all()
    if view == "permissions":
        entries = entries.filter(action__in=PERMISSION_ACTIONS)
    elif view == "denied":
        entries = entries.filter(outcome="denied")
    actor = request.GET.get("actor", "").strip()
    if actor:
        entries = entries.filter(actor_username__icontains=actor)
    action = request.GET.get("action", "").strip()
    if action:
        entries = entries.filter(action=action)

    day_ago = timezone.now() - timedelta(hours=24)
    recent_denied = AuditEntry.objects.filter(outcome="denied", timestamp__gte=day_ago)
    noteworthy = (recent_denied.values("actor_username").annotate(n=Count("id"))
                  .filter(n__gte=3).order_by("-n")[:10])
    service.log(request, "view_activity", detail=f"view={view}")
    context = {
        "page": Paginator(entries, 50).get_page(request.GET.get("page")),
        "view": view, "actor": actor, "action": action,
        "denied_24h": recent_denied.count(),
        "noteworthy": noteworthy,
        "chain": service.verify_chain(),
        "actions": AuditEntry.objects.order_by().values_list("action", flat=True).distinct(),
    }
    return render(request, "audit/activity.html", context)
