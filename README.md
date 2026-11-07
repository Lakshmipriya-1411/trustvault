# TrustVault

A document-sharing platform where **the wrong person cannot reach a file** and **you can prove who did**:
per-document permissions decided by one server-side function, immediate revocation, and a tamper-evident audit
trail that records refused attempts too.

- **Live site:** https://trustvault-7shr.onrender.com  (free hosting: the first load after a quiet period can take up to a minute)
- **Other documents in this repository:** `THREATS.md` (attack routes and what I did about each), `PROMPTS.md` (where the AI was wrong and how I corrected it), `WRITEUP.md` (short write-up)

## Demo accounts

Password for all accounts: **`TrustVault#Demo2026`**

| Role | Username | What this account can do |
|---|---|---|
| Administrator | `admin_demo` | Create and deactivate users; see all activity, permission changes and refused attempts; verify the audit chain. **Cannot read any document.** |
| Document owner | `owner_demo` | Owns "Offer letter - A. Sharma" and "Customer contract - Acme". Upload, edit, delete, share, revoke. |
| Document owner | `owner2_demo` | Owns "Audit papers 2026". Same powers, on their own documents only. |
| Viewer | `viewer_demo` | Granted **read** on the Acme contract only. |
| Viewer | `viewer2_demo` | Granted **read** on "Audit papers 2026" only. |

## Five-minute tour for the evaluator

1. Log in as `viewer_demo`. You see only the Acme contract. Download it: it works.
2. Open a **new private window**, log in as `owner_demo`, open the Acme contract and **Revoke** `viewer_demo`.
3. Back in the first window, refresh the contract page or its download link: **"Not found"**, immediately, without logging out.
4. As `owner_demo`, grant `viewer2_demo` **read** on the Acme contract, then try the same download as `viewer2_demo`.
5. Try to open another owner's document by pasting its link (for example `owner2_demo`'s audit papers as `viewer_demo`): **"Not found"**, same page as a document that does not exist.
6. Log in as `admin_demo` and open **Activity**: every step above is there, including the refused attempts (button **Refused attempts**), with who, when, what, why and from which IP. The line at the top says whether the audit chain is **intact**.
7. As `admin_demo`, paste a document link: **"Not found"**. Administrators manage the system; they do not read documents.

Please attack it. Please also keep it usable for the next evaluator: reactivate any account you deactivate.

## What it does
Login with three roles; upload with content checks; per-document `read` / `edit` grants to named people;
immediate revocation; search by name, owner, category and date; an audit trail of uploads, views, downloads, edits,
deletions, grants, revokes, logins and **refused attempts**; and an administrator view of activity and permission changes.

## Technology
Python 3.12, **Django 6.1**, PostgreSQL (SQLite for local development and tests), Gunicorn, WhiteNoise, hosted on Render.
Server-rendered HTML templates; no JavaScript framework.

## Permission model (in my own words)
- Access is **per document**. A grant row says "this person has `read` or `edit` on this document". No groups and no folders.
- The **owner** can read, download, edit, delete, share and revoke their own documents. An **edit** grantee can read, download and edit.
  A **read** grantee can read and download. Only owners share or delete.
- **Administrators never get document access**, even if a grant row exists. They manage users and watch the audit log.
- Every decision is made in **one function**, `can()` in `documents/permissions.py`, reached through `authorize()` from
  every document route. Nothing is cached, so removing a grant works on the next request. A forbidden document answers
  **404**, identical to a document that does not exist.
- File contents are stored in the database and returned only by the download route after `authorize()`. There is no public file path.

## Audit trail protection
1. **In code:** the model refuses to update or delete existing rows.
2. **In the database (PostgreSQL):** triggers reject `UPDATE`, `DELETE` and `TRUNCATE` on the audit table.
3. **Hash chain:** each row's SHA-256 covers the previous row's hash, so editing or removing a row breaks the chain.
   The administrator page re-verifies the whole chain and shows the latest hash.
Limits are listed honestly in `THREATS.md`.

## API reference: who may call what

Every route requires login. This is enforced for all views by Django's `LoginRequiredMiddleware`; only the login page is exempt.

| Method and path | Who is allowed |
|---|---|
| `GET /accounts/login/` | Anyone |
| `POST /accounts/logout/` | Any logged-in user |
| `GET /` (list and search) | Owner or viewer: only documents they own or were granted. Administrator: empty list |
| `GET, POST /documents/upload/` | Role `owner` only (others get 403, and it is logged) |
| `GET /documents/<id>/` | Owner, or anyone with a grant (read or edit) |
| `GET /documents/<id>/download/` | Owner, or anyone with a grant |
| `GET, POST /documents/<id>/edit/` | Owner, or an `edit` grantee |
| `POST /documents/<id>/delete/` | Owner only |
| `POST /documents/<id>/share/` | Owner only |
| `POST /documents/<id>/revoke/<grant_id>/` | Owner only (the grant must belong to that document) |
| `GET /activity/` | Administrator only |
| `GET /users/`, `GET, POST /users/new/`, `POST /users/<id>/toggle/` | Administrator only |

Anyone who is not allowed on a document route gets `404` and an audit entry with `outcome = denied`.
Search parameters on `GET /`: `q` (name), `owner`, `category`, `date_from`, `date_to`.

## Project layout
```
config/      settings, urls, security-headers middleware
accounts/    custom user with role, login throttling, admin user management, demo seed command
documents/   models, permissions.py (the authorisation decision), upload validation, views, tests
audit/       append-only hash-chained log, signals, admin activity view, tests
templates/   HTML pages
build.sh     build steps used on Render
```

## Run it from a clean clone
```
git clone <repo-url>
cd trustvault
python -m venv venv
venv\Scripts\activate            (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```
Open http://127.0.0.1:8000 and use the demo accounts above.

## Run the tests
```
python manage.py test
```
39 tests. They cover: strangers refused on every document route; anonymous users redirected; administrators refused;
read and edit levels; revocation on the very next request; a grant of one document not usable on another; deletion;
upload validation; that refused attempts and successes are logged; that audit rows cannot be changed and tampering is
detected; login lockout; and deactivated users being logged out. Removing the check in `can()` makes 16 of them fail.

## Deploy (Render)
1. Create a PostgreSQL database (free). Copy its **Internal** database URL.
2. Create a Web Service from this repository. Build command: `bash build.sh`. Start command: `gunicorn config.wsgi`.
3. Environment variables: `SECRET_KEY` (a long random value; the app refuses to start in production without it),
   `DATABASE_URL` (the internal URL), `PYTHON_VERSION=3.12.3`.
`build.sh` installs the requirements, collects static files, runs the migrations (including the audit triggers) and
runs the idempotent demo seed.

## Deliberately not built
Groups and folder inheritance, external sharing links, file versions and recovery, retention rules, password change
and reset, MFA, and AI sharing suggestions. I wanted a permission model small enough to prove.

## Known gaps
Listed with reasons in `THREATS.md` (section "Accepted risks"). In short: no MFA; the audit chain can be rebuilt by
someone who controls the database and recomputes the hashes, and deleting the newest entries is not detectable
without an external copy of the latest hash; lockout is per username; no malware scanning; free-tier infrastructure.

## How I used AI
I built this with Claude (Anthropic) as a coding assistant, running, testing and attacking everything myself.
At the end I also ran GitHub's AI assistant over the repository as an independent review; it found one gap that I then verified and fixed.
`PROMPTS.md` records the places where the AI was wrong and what I did about each.
