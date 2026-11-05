# TrustVault

Secure document sharing where the wrong person cannot reach a file, and every access
(including refused attempts) is recorded in a tamper-evident audit trail.

**Live:** https://trustvault-7shr.onrender.com  (free tier: the first load after idle can take ~1 minute)

## Demo accounts (password for all: `TrustVault#Demo2026`)

| Role | Username | Can do |
|---|---|---|
| Administrator | `admin_demo` | Create/deactivate users, view activity log, permission changes, refused attempts. **Cannot read any document.** |
| Document owner | `owner_demo`, `owner2_demo` | Upload, edit, delete, share and revoke **their own** documents |
| Viewer | `viewer_demo`, `viewer2_demo` | See and download only documents granted to them |

Seed data: `owner_demo` has two documents, `owner2_demo` has one. `viewer_demo` was granted **read** on the
Acme contract only, so the offer letter and audit papers are unreachable to them. Try it.

## What it does
Login with roles, upload with content validation, per-document `read` / `edit` grants to named people,
immediate revocation, search (name, owner, category, date), audit trail of uploads, views, downloads,
edits, deletions, grants, revokes, logins and **refused attempts**, and an administrator view.

## Permission model (in my own words)
- Access is **per document**. A `Grant` row says "this user has `read` or `edit` on this document".
  No groups and no folders: a small model I could verify completely.
- The **owner** can do everything to their document (read, download, edit, delete, share, revoke).
  `edit` grantees can read, download and edit. `read` grantees can read and download. Only owners can share or delete.
- **Administrators never get document access**, even if a grant row exists. They manage users and watch the audit log.
- All decisions are made in **one function**, `documents/permissions.py: can()`, reached through
  `authorize()`. Every document route calls it on every request. Nothing is cached, so removing a
  grant works on the very next request. Forbidden documents answer **404**, identical to "does not exist".
- Files are stored in the database and are only ever returned by `document_download`, after `authorize()`.
  There is no public file path.

## Endpoints and who may call them
Every route requires login (enforced globally by Django's `LoginRequiredMiddleware`; only the login page is exempt).

| Method + path | Who is allowed |
|---|---|
| `GET /accounts/login/` | Anyone |
| `POST /accounts/logout/` | Any logged-in user |
| `GET /` (list + search) | Owner/viewer: only documents they own or were granted. Admin: empty list |
| `GET,POST /documents/upload/` | Role `owner` only (others: 403, logged) |
| `GET /documents/<id>/` | Owner, or anyone with a grant (read or edit) |
| `GET /documents/<id>/download/` | Owner, or anyone with a grant |
| `GET,POST /documents/<id>/edit/` | Owner, or `edit` grantee |
| `POST /documents/<id>/delete/` | Owner only |
| `POST /documents/<id>/share/` | Owner only |
| `POST /documents/<id>/revoke/<grant_id>/` | Owner only (grant must belong to this document) |
| `GET /activity/` | Administrator only |
| `GET /users/`, `GET,POST /users/new/`, `POST /users/<id>/toggle/` | Administrator only |

Anyone not allowed on a document route gets `404` and an audit entry with `outcome=denied`.

## Audit trail protection
1. Append-only in code: the model refuses `save()` on existing rows, `delete()`, and queryset `update()/delete()`.
2. Append-only in the database (PostgreSQL): triggers reject `UPDATE`, `DELETE` and `TRUNCATE` on the table.
3. Hash chain: each row's SHA-256 covers the previous row's hash, so editing or removing a row
   breaks the chain. The administrator page re-verifies the whole chain and shows the latest hash.
Limits are listed honestly in `THREATS.md`.

## Run locally
```
python -m venv venv
venv\Scripts\activate            # Windows   (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
python manage.py test            # 37 tests
```

## Deploy (Render)
1. New PostgreSQL (free). Copy the **Internal** database URL.
2. New Web Service from this repo. Build command `bash build.sh`, start command `gunicorn config.wsgi`.
3. Environment variables: `SECRET_KEY` (long random), `DATABASE_URL` (internal URL), `PYTHON_VERSION=3.12.3`.
The build runs migrations (including the audit triggers) and the idempotent demo seed.

## Deliberately not built
Groups and folder inheritance, external sharing links, file versions/recovery, retention rules,
password change/reset and MFA, AI sharing suggestions. I kept the permission model small enough to prove.

## Known gaps
See `THREATS.md` (section "Accepted risks"). In short: no MFA, the audit chain can be rewritten by someone
who controls both the database and can recompute hashes, deleting the newest entries is not detectable without
an external copy of the head hash, and no malware scanning.

## AI use
I built this with Claude as a coding assistant. `PROMPTS.md` records where it was wrong and what I changed.
