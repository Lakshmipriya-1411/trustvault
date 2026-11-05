import io
import os
import re
import zipfile

from django.conf import settings
from django.core.exceptions import ValidationError

# extension -> content type WE choose (the browser's claim is never trusted)
ALLOWED_TYPES = {
    "pdf": "application/pdf",
    "txt": "text/plain",
    "csv": "text/csv",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def clean_display_name(raw, extension=""):
    name = os.path.basename((raw or "").replace("\\", "/"))
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()
    suffix = "." + extension
    if extension and name.lower().endswith(suffix):
        name = name[: -len(suffix)]
    return name[:150].strip()


def _looks_like(extension, data):
    if extension == "pdf":
        return data.startswith(b"%PDF-")
    if extension == "png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if extension in ("jpg", "jpeg"):
        return data.startswith(b"\xff\xd8\xff")
    if extension in ("docx", "xlsx"):
        try:
            if not data.startswith(b"PK\x03\x04"):
                return False
            names = zipfile.ZipFile(io.BytesIO(data)).namelist()
        except zipfile.BadZipFile:
            return False
        needed = "word/document.xml" if extension == "docx" else "xl/workbook.xml"
        return needed in names
    if extension in ("txt", "csv"):
        if b"\x00" in data:
            return False
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            return False
        return True
    return False


def validate_upload(uploaded):
    """Returns (extension, content_type, bytes). Raises ValidationError if unacceptable."""
    limit = settings.MAX_UPLOAD_BYTES
    if uploaded.size > limit:
        raise ValidationError(f"File is too large (limit {limit // (1024 * 1024)} MB).")
    extension = os.path.splitext(uploaded.name or "")[1].lstrip(".").lower()
    if extension not in ALLOWED_TYPES:
        raise ValidationError("File type not allowed. Allowed: " + ", ".join(sorted(ALLOWED_TYPES)) + ".")
    data = uploaded.read(limit + 1)
    if not data:
        raise ValidationError("The file is empty.")
    if len(data) > limit:
        raise ValidationError("File is too large.")
    if not _looks_like(extension, data):
        raise ValidationError("The file's content does not match its extension.")
    return extension, ALLOWED_TYPES[extension], data
