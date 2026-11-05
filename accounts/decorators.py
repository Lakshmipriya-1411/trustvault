from functools import wraps

from django.core.exceptions import PermissionDenied

from audit import service as audit


def role_required(*roles):
    """Allow only logged-in users whose role is in `roles`. Everyone else gets 403,
    and the refused attempt is written to the audit log."""

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated or request.user.role not in roles:
                audit.log(request, "forbidden_page", "denied", detail=request.path[:200])
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapper

    return decorator
