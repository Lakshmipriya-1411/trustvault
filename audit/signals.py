from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from . import service


@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    service.log(request, "login", actor=user)


@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    if user is not None:
        service.log(request, "logout", actor=user)


@receiver(user_login_failed)
def on_login_failed(sender, credentials, request=None, **kwargs):
    service.log(request, "login_failed", "denied", actor_name=str(credentials.get("username", "")))
