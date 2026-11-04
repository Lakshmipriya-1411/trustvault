import os

from django.core.management.base import BaseCommand

from accounts.models import User

DEMO_USERS = [
    ("admin_demo", User.Role.ADMIN),
    ("owner_demo", User.Role.OWNER),
    ("viewer_demo", User.Role.VIEWER),
]


class Command(BaseCommand):
    help = "Create demo accounts (one per role). Safe to run repeatedly."

    def handle(self, *args, **options):
        password = os.environ.get("DEMO_PASSWORD", "TrustVault#Demo2026")
        for username, role in DEMO_USERS:
            user, created = User.objects.get_or_create(
                username=username, defaults={"role": role}
            )
            if created:
                user.set_password(password)
                user.save()
                self.stdout.write(f"Created {username} ({role})")
            else:
                self.stdout.write(f"Exists  {username}")
