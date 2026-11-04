\# PROMPTS.md



How I used AI to build TrustVault, and where it was wrong.



\## 1. How I worked



I am a fresher with basic Python and DSA knowledge, and this is my first project of this size. I used Claude as a coding assistant in a fixed way:



1\. I gave Claude the problem statement and asked it to propose a stack, modules and a daily plan.

2\. Claude gave code in full files. I typed or pasted each one, ran it, and ran the tests.

3\. For every security-relevant piece I asked "why", and answered a checkpoint question in my own words before moving on.

4\. When something broke or looked wrong, I recorded it in the log below with the fix and the commit.



Rules I held myself to:

\- No file goes in the repo unless I can explain it line by line.

\- Authorisation logic is written once (`can()`) and every route calls it. I check that by reading each route, not by trusting the AI.

\- A test that cannot fail is not a test. I remove an authorisation check and confirm the tests go red.



\## 2. Context I reused every session



Pasted at the start of each new chat:



```text

You are my coding assistant for TrustVault, a secure document-sharing app

(Django + PostgreSQL on Render). I am a beginner and the executer; you give

complete files with exact paths and explain why.

Rules:

1\. All document access decisions go through one function, can(user, document, action).

&#x20;  Never suggest checking permissions in templates or only in the UI.

2\. Unauthorised access returns 404, not 403, so document existence is not leaked.

3\. Every access attempt, including refused ones, is written to the audit log.

4\. Revocation must take effect on the very next request: no cached permissions.

5\. Never trust client input for role, owner, or file type.

6\. After each module, ask me a checkpoint question and list what could still be wrong.

7\. If you are not sure something is correct, say so instead of guessing.

```



\## 3. How I verify AI output



| Area | What I check before accepting it |

|---|---|

| Authorisation | Every route touching a document calls `can()`; I list all URLs and tick them off |

| Audit trail | Refused attempts are logged too; nothing in the app can update or delete log rows |

| Revocation | A test revokes access and the next request is refused |

| Uploads | Type is checked from file content, not just the extension; size is limited |

| Tests | I remove one check and confirm at least one test fails |



\## 4. Log of AI mistakes



\### 2026-11-04: Wrong date in the project plan

\- \*\*Asked:\*\* For a plan for the remaining days of the challenge, after pasting the challenge email.

\- \*\*AI produced:\*\* A schedule that said today was Tuesday 3 November, with a day count based on that.

\- \*\*What was wrong:\*\* Today was Wednesday 4 November, so the schedule was one day too generous. For a hard deadline (Saturday 7 November, 6 PM IST) that matters.

\- \*\*What I did instead:\*\* I checked the real date, corrected it with Claude, and re-planned: M0 and M1 on Wednesday; documents, grants and audit on Thursday; search, admin view and tests on Friday; documentation and final checks on Saturday morning.

\- \*\*Commit:\*\* none (planning error, no code affected).



\### <date>: <title> (authorisation / access control / audit trail)

\- \*\*Asked:\*\* 

\- \*\*AI produced:\*\* 

\- \*\*What was wrong:\*\* 

\- \*\*What I did instead:\*\* 

\- \*\*Commit:\*\* 



\### <date>: <title> (authorisation / access control / audit trail)

\- \*\*Asked:\*\* 

\- \*\*AI produced:\*\* 

\- \*\*What was wrong:\*\* 

\- \*\*What I did instead:\*\* 

\- \*\*Commit:\*\* 



\### <date>: <title>

\- \*\*Asked:\*\* 

\- \*\*AI produced:\*\* 

\- \*\*What was wrong:\*\* 

\- \*\*What I did instead:\*\* 

\- \*\*Commit:\*\* 



\### <date>: <title>

\- \*\*Asked:\*\* 

\- \*\*AI produced:\*\* 

\- \*\*What was wrong:\*\* 

\- \*\*What I did instead:\*\* 

\- \*\*Commit:\*\*

