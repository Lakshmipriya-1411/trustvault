# TrustVault: short write-up

## What I built
A document-sharing web app (Django + PostgreSQL, deployed on Render) where a document can be reached only by someone
who was granted it, every attempt (including refused ones) is recorded in a tamper-evident audit trail, and taking
access away works on the very next request. Roles: administrator, document owner, viewer. Owners upload, edit, delete,
and share documents with named people as `read` or `edit`, and can revoke at any time. Search by name, owner,
category and date. Administrators manage users and see all activity, permission changes and refused attempts, plus an
integrity check of the audit chain. 38 automated tests, including the ones showing one user cannot reach another's documents.

## Permission model, in my own words
Access is per document. A grant row says "this person has read or edit on this document". The owner can do
everything to their own documents; an edit grantee can read, download and edit; a read grantee can read and
download. Only owners share or delete. Administrators never read documents, even if a grant row somehow existed.
One function, `can()` in `documents/permissions.py`, makes every decision, and every document route reaches it
through `authorize()`. Nothing is cached: the grant table is read on each request, so revocation is immediate.
People without access get a 404, which looks the same as a document that does not exist.

## How the audit trail is protected
It is append-only in the application code, append-only in the PostgreSQL database (triggers reject update, delete
and truncate), and hash-chained (each entry's hash covers the previous one) so editing or removing history is
detectable. The admin page re-verifies the chain and shows the latest hash.

## What I deliberately did not build
Groups and folder inheritance, external sharing links, file versions and recovery, retention rules, password change
and reset, MFA, and the optional AI sharing suggestions. I preferred a small permission model I could prove over a large
one with a hole in it.

## How I used AI, and where it was wrong
I built this with Claude as a coding assistant while I ran, tested and attacked everything myself. `PROMPTS.md` lists
nine real corrections. The most important: an admin-only decorator that did not log refused attempts, audit tests that
passed on SQLite but would have failed on PostgreSQL, a public fallback secret key, two refused actions missing from
the audit log (found by comparing my live attack tests with the Activity page), and several wrong expectations about
how the live site would respond.

## What is unfinished or weak
No MFA and no password change screen. The audit chain can be rebuilt by someone who controls the database and
recomputes every hash, and deleting the newest entries is not detectable without an external copy of the latest hash.
Lockout is per username, so it can be abused to lock someone out, and there is no per-IP throttle. No malware scanning.
Files are stored in the database with a 5 MB limit. Full list with reasons in `THREATS.md`.
