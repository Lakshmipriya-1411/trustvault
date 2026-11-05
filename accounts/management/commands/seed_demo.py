import os

from django.core.management.base import BaseCommand

from accounts.models import User
from audit import service as audit
from documents.models import Document, Grant
from documents.services import create_document

DEMO_USERS = [
    ("admin_demo", User.Role.ADMIN),
    ("owner_demo", User.Role.OWNER),
    ("owner2_demo", User.Role.OWNER),
    ("viewer_demo", User.Role.VIEWER),
    ("viewer2_demo", User.Role.VIEWER),
]

# (owner, name, category, text)
DEMO_DOCS = [
    ("owner_demo", "Offer letter - A. Sharma", "hr", "Confidential salary letter (demo data)."),
    ("owner_demo", "Customer contract - Acme", "contract", "Contract between us and Acme (demo data)."),
    ("owner2_demo", "Audit papers 2026", "finance", "Audit working papers (demo data)."),
]

# (document name, grantee, level): viewer_demo can read ONLY the Acme contract
DEMO_GRANTS = [
    ("Customer contract - Acme", "viewer_demo", "read"),
    ("Audit papers 2026", "viewer2_demo", "read"),
]


class Command(BaseCommand):
    help = "Create demo accounts, documents and grants. Safe to run repeatedly."

    def handle(self, *args, **options):
        password = os.environ.get("DEMO_PASSWORD", "TrustVault#Demo2026")
        users = {}
        for username, role in DEMO_USERS:
            user, created = User.objects.get_or_create(username=username, defaults={"role": role})
            if created:
                user.set_password(password)
                user.save()
                audit.log(None, "user_created", actor_name="system", target=username, detail=f"role={role}")
                self.stdout.write(f"Created {username} ({role})")
            else:
                self.stdout.write(f"Exists  {username}")
            users[username] = user

        for owner_name, name, category, text in DEMO_DOCS:
            owner = users[owner_name]
            if Document.objects.filter(owner=owner, name=name).exists():
                continue
            doc = create_document(owner, name, category, "txt", "text/plain", text.encode())
            audit.log(None, "upload", actor_name="system", document=doc, detail="seed data")
            self.stdout.write(f"Created document {name}")

        for doc_name, grantee, level in DEMO_GRANTS:
            doc = Document.objects.filter(name=doc_name, is_deleted=False).first()
            if doc and not Grant.objects.filter(document=doc, user=users[grantee]).exists():
                Grant.objects.create(document=doc, user=users[grantee], level=level,
                                     granted_by=doc.owner)
                audit.log(None, "grant", actor_name="system", document=doc, target=grantee,
                          detail=f"level {level} (seed data)")
