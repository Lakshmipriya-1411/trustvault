# THREATS.md

The ways I believe TrustVault could be broken, what I did about each, and what I knowingly accepted.
"Test" names point to automated tests (`python manage.py test`, 39 tests). Items marked **Live** I also checked
by hand against the deployed site on 5 November 2026 (details at the end).

## A. Reaching documents without a grant

| # | Threat | What I did | Test / evidence |
|---|---|---|---|
| A1 | **IDOR**: change the document id in a URL | Every document route calls `authorize()` -> `can()`. Random UUID ids are only a bonus; the check is the control | `test_user_without_grant_is_refused_on_every_route`. **Live** (tests 3, 6, 7) |
| A2 | **A route I forgot** (download, edit form, delete, share) | All document routes share one entry point; the test loops over every route for two different strangers | same test |
| A3 | **Anonymous access** | `LoginRequiredMiddleware` protects every view by default; only the login page is exempt, so a route I forget is still protected | `test_anonymous_is_sent_to_login_on_every_route`. **Live** (test 1) |
| A4 | **Search or list leaking** other people's documents | Search runs only over `visible_to(user)`; filters are applied after that | `test_search_and_list_never_reveal_other_peoples_documents` |
| A5 | **Existence leak**: 403 vs 404 reveals which ids exist | Forbidden and nonexistent both answer an identical 404 | `test_nonexistent_and_forbidden_look_identical` |
| A6 | **Wrong level**: a read user edits, deletes or shares | `ALLOWED_ACTIONS` per level; only the owner can delete or share | `GrantLevels` tests. **Live** (test 4) |
| A7 | **Revoking with someone else's grant id** | `document_revoke` looks the grant up *within this document* | `test_cannot_revoke_a_grant_belonging_to_someone_elses_document` |
| A8 | **Mass assignment**: send `owner=` or `role=` in a form | Forms declare explicit fields; the owner is always `request.user`; roles change only through the admin form | `test_owner_cannot_be_chosen_by_the_client` |
| A9 | **Administrator becomes a reader** | `can()` returns False for the admin role even if a grant row exists; granting to an admin is refused | `test_administrator_cannot_read_documents_even_with_a_grant`. **Live** (tests 8, 18) |
| A10 | **Deleted document still readable** | Delete wipes the bytes, marks the row deleted and removes grants; `can()` refuses deleted documents | `test_deleted_document_is_unreachable_and_content_is_destroyed` |
| A11 | **Direct file URL or static path** | Files are stored in the database, not on disk, and are returned only by the download view | by design; no file route exists |
| A12 | **Django `/admin/`** as a second route to the data | `django.contrib.admin` is not installed | **Live** (test 8: 404) |
| A13 | **Wrong role on admin pages** | `role_required` answers 403 and writes a `forbidden_page` audit entry | `test_admin_pages_refuse_non_admins_and_log_it`. **Live** (tests 5, 9) |

## B. Taking access away

| # | Threat | What I did | Test / evidence |
|---|---|---|---|
| B1 | **Revoked user keeps access** (cached permission, link, session) | No permission cache: `can()` reads the grant table on every request. No download links or tokens are ever issued | `test_revoked_user_is_refused_on_the_very_next_request` (same logged-in session). **Live** (test 11) |
| B2 | **Deactivated user keeps a live session** | `is_active=False` makes Django drop the session on the user's next request | `test_deactivated_user_is_logged_out_on_next_request` |
| B3 | **Back button after logout** shows cached pages | `Cache-Control: private, no-store` on authenticated responses | by design. **Live** (test 10) |

## C. Audit trail

| # | Threat | What I did | Test / evidence |
|---|---|---|---|
| C1 | **Refused attempts not recorded** | `authorize()` logs every denial; `role_required` logs forbidden pages; failed logins, rejected uploads and refused grants are logged | `AuditTrail` tests. **Live** (Activity page shows every attack test) |
| C2 | **Editing or deleting log rows through the app** | The model refuses `save()` on existing rows, `delete()`, and queryset `update()` / `delete()` | `test_orm_refuses_updates_and_deletes` |
| C3 | **Editing or deleting log rows in the database** | PostgreSQL triggers reject UPDATE, DELETE and TRUNCATE on the audit table. If the trigger is disabled, the hash chain still detects edits and removals | `test_editing_a_row_behind_the_orms_back_is_detected`, `test_removing_a_row_in_the_middle_is_detected` (on PostgreSQL they also prove the trigger blocks the SQL). I also confirmed against a real PostgreSQL that raw UPDATE, DELETE and TRUNCATE are refused |
| C4 | **Two writers fork the chain** | `prev_hash` is unique; a clash raises an error and the writer retries | `test_chain_cannot_fork` |
| C5 | **Log injection** through filenames or usernames | Values are stored as data and escaped in templates; the hash input is JSON-encoded so field boundaries cannot be forged | by design |
| C6 | **Refused actions that never reach the main check are not logged** | Found by comparing my live attack tests with the Activity page: an empty-file upload (rejected by the form) and login attempts made during a lockout left no entry. Both are now logged. A later independent review (a second AI tool that I ran over the repository) found that invalid share-form submissions were not logged either; that is fixed too | `test_empty_upload_attempt_is_recorded_in_the_audit_log`, extended lockout test, `test_invalid_share_form_attempt_is_recorded_in_the_audit_log`. **Live** (entry 98 for the empty upload) |

## D. Uploads

| # | Threat | What I did | Test / evidence |
|---|---|---|---|
| D1 | **Executable, HTML or script upload** | Extension allow-list; files are served only as attachments with `nosniff` and a content type that I choose | `UploadValidation` tests. **Live** (test 13) |
| D2 | **Extension spoofing** (a `.pdf` that is really HTML) | Magic bytes are checked per type; a docx or xlsx must be a real zip with the expected part | `test_rejects_content_that_does_not_match_extension`. **Live** (test 12) |
| D3 | **Path traversal in the filename** | Only the base name is kept, control characters are removed, and the name is never used as a path (content lives in the database) | `test_path_in_filename_is_stripped`. **Live**: `reports/2026/passwd` stored as `passwd`. A literal `../../etc/passwd` was blocked earlier by the hosting provider's firewall (a 403 page that is not my app's), so my own code did not see it |
| D4 | **Huge or empty files** | 5 MB limit; empty files rejected | `test_rejects_empty_and_oversized_files`. **Live** (tests 14, 15) |
| D5 | **Stored XSS through names** | Django templates escape output; a CSP restricts scripts. A name containing `<script>` tags was stored with the path-like part stripped (`script>`) and displayed as plain text; no script ran | **Live** (test 16) |

## E. Accounts and sessions

| # | Threat | What I did | Test / evidence |
|---|---|---|---|
| E1 | **Password guessing** | An account is locked for 10 minutes after 5 failed logins (counted from the audit log); even the right password is refused while locked, and the refusal is logged | `test_login_is_locked_after_repeated_failures`. **Live** (test 21) |
| E2 | **Passwords stored badly** | Django's salted password hashing; password validators when an administrator creates users | framework behaviour |
| E3 | **CSRF** | Django CSRF middleware; every state change is a POST with a token; logout is POST-only | `test_logout_requires_post`. **Live** (test 2: 403) |
| E4 | **Clickjacking** | `X-Frame-Options: DENY` and CSP `frame-ancestors 'none'` | **Live** (test 22, response headers) |
| E5 | **Cookie theft** | `HttpOnly`, `Secure` on Render, `SameSite=Lax`, sessions limited to 8 hours | settings |
| E6 | **Self-chosen roles** | There is no signup; only an administrator creates users and chooses roles | `test_only_admin_can_create_users_and_role_comes_from_admin_form` |
| E7 | **Open redirect through the login `next` parameter** | Django's login view only follows redirects to the same host | framework behaviour; I did not test it separately |
| E8 | **Session fixation** | Django starts a new session key at login | framework behaviour; I did not test it separately |

## F. Configuration

| # | Threat | What I did | Test / evidence |
|---|---|---|---|
| F1 | **Forged sessions through a default secret key** | The settings file had a public development fallback key. The app now refuses to start in production unless a real `SECRET_KEY` is set | **Live**: key present on Render and the service starts |
| F2 | **Debug pages leaking internals** | `DEBUG` is on only when the Render hostname variable is absent (my laptop) | live 403/404 pages are the plain app pages |
| F3 | **Missing browser protections** | CSP, `X-Frame-Options`, `nosniff`, `Referrer-Policy`, HSTS | **Live** (test 22) |

## Accepted risks (known weaknesses and why)

1. **The audit chain can be rebuilt by someone who controls the database and recomputes every hash.** SHA-256 chaining detects edits and removals of old rows, not a complete rebuild. A keyed hash or an external copy would fix this. I did not add a key because rotating it would make the chain look "broken", and I could not test rotation in the time available. The admin page shows the latest hash so it can be copied elsewhere.
2. **Deleting the newest entries is not detectable** without an external record of the latest hash (same fix as above).
3. **No MFA, no password change or reset screen.** Passwords are changed by an administrator re-creating the account.
4. **Lockout by username can be abused to lock someone out**, and there is no per-IP throttle. I accepted this over having no brute-force protection.
5. **The client IP in the log comes from `X-Forwarded-For`, which a client can influence.** It is informational only; no decision depends on it.
6. **Username enumeration by owners:** the share form says "Administrators cannot be granted..." for an admin username, which reveals that the username is an admin. Owners are internal users, so I accepted it.
7. **Administrators see document names** in the activity log (never contents).
8. **A download that has already started is not interrupted by a revoke.** The check happens at the start of each request.
9. **No malware scanning and no extra encryption of file contents** beyond the hosting provider's. Files live in PostgreSQL.
10. **The demo passwords are public** (they are in the README for the judges). Do not copy this pattern for real accounts.
11. **Small, free infrastructure:** one web process and a free database. There is no backup, and deletion is final by design.
12. **The hosting provider's firewall also filters requests** (it blocked a literal `../../etc/passwd`). I treat that as an extra layer, not as protection I rely on: my own code strips path parts and is tested for it.
13. **Timing differences** between "no such document" and "forbidden" were not measured.

## Verified on the live deployment (5 November 2026)

I attacked my own deployment, https://trustvault-7shr.onrender.com, using the five demo accounts.

- Anonymous requests to `/`, `/activity/`, `/users/` and a document download all redirected to login. A logout POST without a CSRF token was refused (403).
- A viewer, a different owner and the administrator all got "Not found" on documents they had no grant for, on download and edit links, and on a document id with one character changed.
- A viewer opening the upload, activity and users pages got "Not allowed"; an owner opening the activity page also got "Not allowed". `/admin/` does not exist (404).
- After logout, the Back button did not show documents. A revoked viewer was refused on the next request without logging out.
- Uploads rejected: a `.pdf` containing script text, an `.html` file, a file over 5 MB, and an empty file. A document named with `<script>` tags displayed as plain text with no script running.
- Granting access to an administrator, to myself, and to a non-existent user was refused.
- Six failed logins for one username triggered the lockout message.
- The responses carried Content-Security-Policy, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff` and Strict-Transport-Security.
- The admin Activity page showed the audit chain as intact and listed every refused attempt above, with person, time, action, document, reason and IP.
