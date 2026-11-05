# PROMPTS.md

How I used AI to build TrustVault, and where it was wrong.

I used **Claude** (Anthropic) as my coding assistant for the whole project. I am a fresher with basic Python and DSA
knowledge and this is the first project of this size I have built, so I worked in a fixed way: I gave the instructions
and the problem statement, Claude produced complete files and explained them, and **I ran, tested and attacked
everything myself**, pasting the real outputs back into the conversation. Every entry below is something that
actually happened, and each one records who noticed it.

## 1. Instructions and context I reused

**Context I gave at the start:** the full TrustVault problem statement and the challenge instructions, pasted into the chat.

**My standing instruction (summary of my own message):** pick the most suitable stack for a fresher who only knows
basic Python; break the project into modules; build only the necessary core features; deploy from day one and commit
every day; I act as the "executer" and Claude gives complete files, exact paths and step-by-step guidance; and Claude
must tell me if I am missing anything.

**Requirements I made Claude design around (taken from the problem statement):** one server-side authorisation
decision, refused attempts audited, revocation effective on the very next request, and a tamper-evident audit trail.

**How I verified Claude's output every time**
1. Ran the automated tests locally (37, later 38) and read any failure.
2. Clicked through the app as each role and checked the result against what was expected.
3. Deployed to Render and repeated the checks on the live site in a private window.
4. Ran 22 attack tests against my own live deployment, then read the admin Activity page to confirm each one was recorded.

## 2. Log of where the AI was wrong

### 2026-11-05: Live login failed after the first deploy (deployment)
- **Asked:** for demo accounts for each role, seeded by the build so the live site would have working logins.
- **AI produced:** a `seed_demo` command run from `build.sh`, on the assumption that Render executes `build.sh` on every deploy.
- **What was wrong:** on the live site every login showed "Invalid username or password". The Render log showed each `POST /accounts/login/` returning 200 (the form re-displayed), so the app worked but the demo users did not exist in the live database.
- **Found by:** me. I tested the live URL, saw the error, and pasted the Render log.
- **What I did instead:** Claude diagnosed it as "the seed never ran on the live database". I ran `migrate` and `seed_demo` from my laptop against the Render database (using the external database URL), after which login worked. Later deploys ran the seed in the build: `owner2_demo`, created by the newer seed, exists on the live site.
- **Commit:** COMMIT_LINK (find it with `git log --oneline -- accounts/management/commands/seed_demo.py`)

### 2026-11-05: A PowerShell command given for a Command Prompt window (tooling)
- **Asked:** how to point my laptop at the live database to run the seed.
- **AI produced:** `$env:DATABASE_URL="..."`, which only works in PowerShell.
- **What was wrong:** I was in Command Prompt, which answered "The filename, directory name, or volume label syntax is incorrect."
- **Found by:** me, from the error message.
- **What I did instead:** Claude gave the Command Prompt form (`set DATABASE_URL=...`), and it worked. I also learned that the connection string contains the database password, so it must never be pasted into a chat or a file, and that a password exposed that way has to be rotated.
- **Commit:** none (command line only, no code change).

### 2026-11-05: Refused attempts on admin-only pages were not audited (authorisation / audit trail)
- **Asked:** for the complete project, including role-based access and an audit trail that records refused attempts.
- **AI produced:** earlier, a `role_required` decorator that answered 403 to the wrong role but wrote nothing to the audit log.
- **What was wrong:** a viewer opening `/activity/` or `/users/` left no trace, which breaks the requirement "you can prove who reached it, including the attempts that were refused".
- **Found by:** Claude, while rebuilding the full project against the problem statement. I confirmed it live: the Activity page shows `forbidden_page` entries for `viewer_demo` on `/activity/` and `/users/` and for `owner_demo` on `/activity/` (entries 40, 41 and 52).
- **What I did instead:** `role_required` now writes a `forbidden_page` / denied audit entry before refusing. Covered by `test_admin_pages_refuse_non_admins_and_log_it`.
- **Commit:** COMMIT_LINK (`git log --oneline -- accounts/decorators.py`)

### 2026-11-05: Audit-tampering tests passed on SQLite but would have failed on PostgreSQL (audit trail)
- **Asked:** for tests proving the audit log cannot be altered.
- **AI produced:** tests that change or delete audit rows with raw SQL and check that the hash chain detects it.
- **What was wrong:** on real PostgreSQL the append-only trigger blocks the raw SQL, so the tests crashed with "audit_auditentry is append-only". On my laptop they passed anyway because SQLite does not run the trigger, so I could not have seen the problem myself.
- **Found by:** Claude, by running the whole suite against a real PostgreSQL database in its own environment.
- **What I did instead:** the tests now work on both: on PostgreSQL they first prove the database refuses the tampering, then disable the trigger to simulate an attacker with database rights and prove the hash chain still detects the change. Lesson for me: a test that passes on a different database from production does not prove the production behaviour.
- **Commit:** COMMIT_LINK (`git log --oneline -- audit/tests.py`)

### 2026-11-05: A public fallback SECRET_KEY in the settings (access control)
- **Asked:** for the deployment settings.
- **AI produced:** `SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-key")`.
- **What was wrong:** if the environment variable were ever missing on Render, the site would silently run with a key that is public in my repository, and anyone could forge session cookies and become any user.
- **Found by:** Claude, while preparing my attack checklist.
- **What I did instead:** the app now refuses to start in production if the key is the default. My first paste had wrong indentation and gave an `IndentationError`, which I fixed; I then confirmed on Render that a real `SECRET_KEY` is set and that the redeploy came up.
- **Commit:** COMMIT_LINK (`git log --oneline -- config/settings.py`, the "Refuse to start in production" commit)

### 2026-11-05: The AI's expected result for a path-traversal upload was wrong (upload validation)
- **Asked:** for attack tests to run on my live site, including uploading a file named `../../etc/passwd`.
- **AI produced:** a checklist that said the upload would be accepted and the name stored as `passwd`.
- **What was wrong:** the live site answered "403 Forbidden: blocked by this site's web application firewall", a page that is not my application's own 403 page. The hosting provider's firewall stopped the request before it reached my code.
- **Found by:** me. I ran the test and pasted the page.
- **What I did instead:** Claude explained that two layers exist (the host's firewall and my code), told me not to try to bypass the firewall, and gave a name that does not trigger it (`reports/2026/passwd`). That upload was accepted and stored as `passwd` (Activity entry 60). The application's own stripping is also covered by `test_path_in_filename_is_stripped`. I recorded both layers in THREATS.md.
- **Commit:** none for the code (it already behaved correctly); documentation only.

### 2026-11-05: Two refused actions were missing from the audit log (audit trail)
- **Asked:** that every refused attempt be recorded.
- **AI produced:** logging for denied document access, forbidden pages, rejected uploads and failed logins.
- **What was wrong:** (1) an empty-file upload was refused by the form before my validation code ran, so it left no entry; (2) login attempts made *while* an account was locked out were refused silently, so someone who kept guessing left no trace.
- **Found by:** Claude, comparing the attack tests I ran with the live Activity page I pasted. Entries 54 to 56 were my `fake.pdf`, `page.html` and `big.pdf` uploads, but nothing was there for `empty.txt`, and only 5 of my 6 lockout attempts appeared.
- **What I did instead:** a form failure on upload or edit now writes a denied entry, and a refused login during lockout writes a `login_locked` entry. Added `test_empty_upload_attempt_is_recorded_in_the_audit_log` and extended the lockout test. After deploying, I repeated the empty upload on the live site and the Activity page showed entry 98, "The submitted file is empty."
- **Commit:** COMMIT_LINK ("Audit empty/invalid uploads and attempts made during login lockout")

### 2026-11-05: The expected result for the script-name test was imprecise (upload validation)
- **Asked:** for a test that a document named `<script>alert(1)</script>` is displayed safely.
- **AI produced:** "the title shows the text `<script>alert(1)</script>` as plain words".
- **What was wrong:** the name is stored as `script>`, because my name cleaner treats `/` as a path separator and the closing tag contains one. It is still safe (no script ran, and the name was shown as plain text), but the stated result was not what the system does.
- **Found by:** Claude, reading the Activity page I pasted (document name `script>` in entries 57 to 65).
- **What I did instead:** corrected my expectation and my THREATS.md wording. I kept the behaviour: stripping path-like parts is the safer outcome.
- **Commit:** none (documentation correction).

### 2026-11-05: A file was promised but never attached (tooling)
- **Asked:** for the patch files for the audit fixes.
- **AI produced:** instructions to "unzip trustvault_patch1.zip" without actually attaching the zip to its message.
- **What was wrong:** the file did not exist for me.
- **Found by:** me ("i did not get any zip folder").
- **What I did instead:** Claude attached the file and I applied it. I now check that anything I am told to use is really in front of me.
- **Commit:** none.

## 3. Experiment I ran to check the tests really test something

The brief says a judge will remove one authorisation check and run my tests. I did the same: in `documents/permissions.py` I changed the last line of `can()` to `return True` and ran `python manage.py test documents`. Result: 16 of the 25 tests in the documents app failed (FAILED (failures=16)). With the check disabled, a user with no grant could open the document page, download it, change its name to “hacked”, and delete it. I then restored the file with `git checkout documents/permissions.py`.
(Claude ran the same experiment in its environment: 16 failures with `can()` always returning True, 1 failure when revoke did not delete the grant, and 2 failures when denials were not logged.)
