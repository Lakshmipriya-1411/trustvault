import hashlib

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import content_disposition_header
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import User
from audit import service as audit
from audit.models import AuditEntry

from .forms import EditForm, SearchForm, ShareForm, UploadForm
from .models import Document, Grant
from .permissions import access_level, authorize, visible_to
from .services import create_document
from .validation import clean_display_name, validate_upload


def _form_errors(form):
    return "; ".join(message for errors in form.errors.values() for message in errors)[:400]


def document_list(request):
    """Home page: documents I own or was granted, with search. Only visible_to() rows
    are ever searched, so search can never reveal other people's documents."""
    queryset = visible_to(request.user)
    form = SearchForm(request.GET)
    if form.is_valid():
        data = form.cleaned_data
        if data["q"]:
            queryset = queryset.filter(name__icontains=data["q"])
        if data["owner"]:
            queryset = queryset.filter(owner__username__icontains=data["owner"])
        if data["category"]:
            queryset = queryset.filter(category=data["category"])
        if data["date_from"]:
            queryset = queryset.filter(uploaded_at__date__gte=data["date_from"])
        if data["date_to"]:
            queryset = queryset.filter(uploaded_at__date__lte=data["date_to"])
    documents = list(queryset.select_related("owner").order_by("-uploaded_at")[:200])
    levels = dict(Grant.objects.filter(user=request.user, document__in=documents)
                  .values_list("document_id", "level"))
    for doc in documents:
        doc.my_access = "owner" if doc.owner_id == request.user.pk else levels.get(doc.pk, "")
    return render(request, "documents/list.html", {"documents": documents, "form": form})


@role_required(User.Role.OWNER)
def document_upload(request):
    form = UploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        uploaded = form.cleaned_data["file"]
        try:
            extension, content_type, data = validate_upload(uploaded)
        except ValidationError as error:
            audit.log(request, "upload", "denied", document_name=uploaded.name[:200],
                      detail="; ".join(error.messages))
            form.add_error("file", error)
        else:
            name = clean_display_name(form.cleaned_data["name"] or uploaded.name, extension)
            doc = create_document(request.user, name, form.cleaned_data["category"],
                                  extension, content_type, data)
            audit.log(request, "upload", document=doc,
                      detail=f"{doc.size} bytes, sha256 {doc.sha256[:16]}, category {doc.category}")
            messages.success(request, "Document uploaded.")
            return redirect("document_detail", pk=doc.pk)
    elif request.method == "POST":
        audit.log(request, "upload", "denied", detail=_form_errors(form))
    return render(request, "documents/upload.html", {"form": form})


def document_detail(request, pk):
    doc = authorize(request, pk, "read", "view")
    audit.log(request, "view", document=doc)
    is_owner = doc.owner_id == request.user.pk
    context = {
        "doc": doc,
        "is_owner": is_owner,
        "can_edit": access_level(request.user, doc) in ("owner", "edit"),
    }
    if is_owner:
        context["grants"] = doc.grants.select_related("user").order_by("user__username")
        context["share_form"] = ShareForm()
        context["history"] = AuditEntry.objects.filter(document_id=doc.pk)[:30]
    return render(request, "documents/detail.html", context)


def document_download(request, pk):
    doc = authorize(request, pk, "download", "download", with_data=True)
    audit.log(request, "download", document=doc, detail=f"sha256 {doc.sha256[:16]}")
    response = HttpResponse(bytes(doc.data), content_type=doc.content_type)
    response["Content-Disposition"] = content_disposition_header(True, doc.download_name)
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


def document_edit(request, pk):
    doc = authorize(request, pk, "edit", "edit", with_data=True)
    form = EditForm(request.POST or None, request.FILES or None,
                    initial={"name": doc.name, "category": doc.category})
    if request.method == "POST" and form.is_valid():
        changes = []
        new_file = form.cleaned_data["file"]
        replacement = None
        if new_file:
            try:
                replacement = validate_upload(new_file)
            except ValidationError as error:
                audit.log(request, "edit", "denied", document=doc, detail="; ".join(error.messages))
                form.add_error("file", error)
        if not form.errors:
            old_name = doc.name
            doc.name = clean_display_name(form.cleaned_data["name"], doc.extension) or old_name
            if doc.name != old_name:
                changes.append(f"renamed from '{old_name}'")
            if doc.category != form.cleaned_data["category"]:
                changes.append(f"category {doc.category} -> {form.cleaned_data['category']}")
                doc.category = form.cleaned_data["category"]
            if replacement:
                doc.extension, doc.content_type, doc.data = replacement
                doc.size = len(doc.data)
                doc.sha256 = hashlib.sha256(doc.data).hexdigest()
                changes.append(f"content replaced (sha256 {doc.sha256[:16]})")
            doc.save()
            audit.log(request, "edit", document=doc, detail="; ".join(changes) or "no changes")
            messages.success(request, "Document updated.")
            return redirect("document_detail", pk=doc.pk)
    elif request.method == "POST":
        audit.log(request, "edit", "denied", document=doc, detail=_form_errors(form))
    return render(request, "documents/edit.html", {"form": form, "doc": doc})


@require_POST
def document_delete(request, pk):
    doc = authorize(request, pk, "delete", "delete")
    audit.log(request, "delete", document=doc, detail=f"{doc.size} bytes, sha256 {doc.sha256[:16]}")
    doc.data = b""  # the content is destroyed, only the audit record remains
    doc.is_deleted = True
    doc.deleted_at = timezone.now()
    doc.save()
    doc.grants.all().delete()
    messages.success(request, "Document deleted.")
    return redirect("home")


@require_POST
def document_share(request, pk):
    doc = authorize(request, pk, "share", "grant")
    form = ShareForm(request.POST)
    if not form.is_valid():
        audit.log(request, "grant", "denied", document=doc, detail=_form_errors(form))
        messages.error(request, "Choose a username and an access level.")
        return redirect("document_detail", pk=doc.pk)
    username = form.cleaned_data["username"].strip()
    level = form.cleaned_data["level"]
    target = User.objects.filter(username=username, is_active=True).first()
    problem = None
    if target is None:
        problem = "No active user with that username."
    elif target.pk == doc.owner_id:
        problem = "You already own this document."
    elif target.role == User.Role.ADMIN:
        problem = "Administrators cannot be granted document access."
    if problem:
        audit.log(request, "grant", "denied", document=doc, target=username, detail=problem)
        messages.error(request, problem)
        return redirect("document_detail", pk=doc.pk)
    previous = Grant.objects.filter(document=doc, user=target).values_list("level", flat=True).first()
    Grant.objects.update_or_create(document=doc, user=target,
                                   defaults={"level": level, "granted_by": request.user})
    detail = f"level {level}" if not previous else f"level {previous} -> {level}"
    audit.log(request, "grant", document=doc, target=target.username, detail=detail)
    messages.success(request, f"{target.username} now has {level} access.")
    return redirect("document_detail", pk=doc.pk)


@require_POST
def document_revoke(request, pk, grant_id):
    doc = authorize(request, pk, "share", "revoke")
    grant = get_object_or_404(Grant, pk=grant_id, document=doc)  # must belong to THIS document
    target, level = grant.user.username, grant.level
    grant.delete()  # effective immediately: nothing else was issued to that person
    audit.log(request, "revoke", document=doc, target=target, detail=f"was {level}")
    messages.success(request, f"Access removed for {target}.")
    return redirect("document_detail", pk=doc.pk)
