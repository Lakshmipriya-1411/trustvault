# THREATS.md

Ways I believe TrustVault could be broken, what I did, and what I knowingly accepted.
"Test" names point to automated tests (run `python manage.py test`).

## A. Reaching documents without a grant

| # | Threat | What I did | Test |
|---|---|---|---|
| A1 | **IDOR**: change the document id in a URL | Every document route calls `authorize()` -> `can()`. Ids are random UUIDs, but that is only a bonus: the check is the control | `StrangersCannotReachDocuments.test_user_without_grant_is_refused_on_every_route` |
| A2 | **One route forgotten** (download, edit form, delete, share) | All routes share one entry point. The test loops over every document route for two different strangers | same |
| A3 | **Anonymous access** | `LoginRequiredMiddleware` protects every view by default; only login is exempt, so a route I forget is still protected | `test_anonymous_is_sent_to_login_on_every_route` |
| A4 | **Search/list leaking** other people's names | Search only runs over `visible_to(user)`; filters are applied after that | `test_search_and_list_never_reveal_other_peoples_documents` |
| A5 | **Existence leak**: 403 vs 404 shows which ids exist | Refused and nonexistent both return an identical 404 | `test_nonexistent_and_forbidden_look_identical` |
| A6 | **Wrong grant level**: read user edits/deletes/shares | `ALLOWED_ACTIONS` table per level; only the owner can delete or share | `GrantLevels` tests |
| A7 | **Revoke via someone else's grant id**: use my document's URL with another document's grant id | `document_revoke` looks up the grant *within this document* | `test_cannot_revoke_a_grant_belonging_to_someone_elses_document` |
| A8 | **Mass assignment**: send `owner=...` or `role=...` in a form | Forms declare explicit fields; owner is always `request.user`; roles only change in the admin form | `test_owner_cannot_be_chosen_by_the_client` |
| A9 | **Admin turns into a reader** | `can()` returns False for role admin even if a grant row exists; granting to admins is refused | `test_administrator_cannot_read_documents_even_with_a_grant` |
| A10 | **Deleted document still readable** | Delete wipes the bytes, sets `is_deleted`, removes grants; `can()` refuses deleted documents | `test_deleted_document_is_unreachable_and_content_is_destroyed` |
| A11 | **Direct file URL / static path** | Files are in the database, not on disk, and are returned only by the download view | by design (no static route exists) |
| A12 | **Django `/admin/`** as a second route to data | `django.contrib.admin` is not installed | smoke test: `/admin/` is 404 |

## B. Taking access away

| # | Threat | What I did | Test |
|---|---|---|---|
| B1 | **Revoked user keeps access** (cached permission, link, session) | No permission cache: `can()` queries the grant table on every request. No download links or tokens are ever issued | `RevocationIsImmediate.test_revoked_user_is_refused_on_the_very_next_request` (same logged-in session) |
| B2 | **Deactivated user keeps a live session** | `is_active=False` makes Django drop the session on the next request | `test_deactivated_user_is_logged_out_on_next_request` |
| B3 | **Back button after logout** shows cached pages | `Cache-Control: private, no-store` on authenticated responses | by design (header) |

## C. Audit trail

| # | Threat | What I did | Test |
|---|---|---|---|
| C1 | **Refused attempts not recorded** | `authorize()` logs every denial; `role_required` logs forbidden pages; failed logins and rejected uploads are logged | `AuditTrail` tests |
| C2 | **Editing/deleting log rows through the app** | Model and queryset refuse updates/deletes | `test_orm_refuses_updates_and_deletes` |
| C3 | **Editing/deleting log rows through the database** | PostgreSQL triggers block UPDATE/DELETE/TRUNCATE (also for the table owner); verified manually against real PostgreSQL. The hash chain still detects tampering if the trigger is disabled | `test_editing_a_row_behind_the_orms_back_is_detected`, `test_removing_a_row_in_the_middle_is_detected` |
| C4 | **Two writers fork the chain** | `prev_hash` is unique, a clash raises an error and the writer retries | `test_chain_cannot_fork` |
| C5 | **Log injection** via filenames/usernames | Values are stored as data and escaped in templates; hash input is JSON-encoded so field boundaries cannot be forged | by design |

## D. Uploads

| # | Threat | What I did | Test |
|---|---|---|---|
| D1 | **Executable/HTML/script upload** | Allow-list of extensions; served only as `attachment` with `nosniff`, with a content type *I* choose | `UploadValidation` tests |
| D2 | **Extension spoofing** (`evil.pdf` that is HTML) | Magic bytes checked per type (docx/xlsx must be a real zip with the expected part) | `test_rejects_content_that_does_not_match_extension` |
| D3 | **Path traversal in filename** | Only the base name is kept, control characters stripped, never used as a path (content is in the DB) | `test_path_in_filename_is_stripped` |
| D4 | **Huge files / empty files** | 5 MB limit and empty rejection | `test_rejects_empty_and_oversized_files` |
| D5 | **Stored XSS via names** | Django templates escape output; CSP blocks inline script | by design |

## E. Accounts and sessions

| # | Threat | What I did | Test |
|---|---|---|---|
| E1 | **Password guessing** | Lock a username for 10 minutes after 5 failures (counted from the audit log); even the right password is refused while locked | `test_login_is_locked_after_repeated_failures` |
| E2 | **Weak passwords stored badly** | Django's salted hashers; password validators on user creation | framework |
| E3 | **CSRF** | Django CSRF middleware; every state change is POST with a token; logout is POST | `test_logout_requires_post` |
| E4 | **Clickjacking** | `X-Frame-Options: DENY` and CSP `frame-ancestors 'none'` | by design |
| E5 | **Cookie theft** | `HttpOnly`, `Secure` (on Render), `SameSite=Lax`, 8-hour sessions | settings |
| E6 | **Self-chosen roles** | No signup. Only an administrator creates users and chooses roles | `test_only_admin_can_create_users...` |

## Accepted risks (known weaknesses and why)

1. **The chain can be rewritten by someone who controls the database and recomputes every hash.** SHA-256 chaining detects edits and deletions of old rows, not a full rebuild. A keyed hash or an external copy would fix this; I did not add one because a changed secret would "break" the chain and I could not test key rotation in time. The admin page shows the latest hash so it can be copied elsewhere.
2. **Deleting the newest entries is undetectable** without an external record of the head hash (same fix as above).
3. **No MFA, no password change or reset screen.** Passwords are changed by an administrator re-creating the account. Out of scope for the time available.
4. **Lockout by username can be abused to lock someone out** (a denial of service), and there is no per-IP throttle. Accepted over having no brute-force protection.
5. **Client IP in the log is taken from `X-Forwarded-For`, which a client can influence.** It is informational only; no decision depends on it.
6. **Username enumeration by owners:** the share form says "Administrators cannot be granted..." for an admin username, revealing it is an admin. Owners are internal users; accepted.
7. **Administrators see document names** in the activity log (not contents).
8. **A download that already started is not interrupted by a revoke.** The check happens at the start of each request.
9. **No malware scanning and no encryption of file contents beyond the hosting provider's.** Files live in PostgreSQL.
10. **Demo passwords are public** (they are in the README for the judges). Do not reuse the pattern for real accounts.
11. **Small, free infrastructure:** one web process, free database. There is no backup or recovery of deleted documents (deletion is final by design).
