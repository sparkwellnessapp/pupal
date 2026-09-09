# Google Sign-In + verified email signup — implementation plan

> Status: **IMPLEMENTED 2026-09-01** (not yet deployed). §0–§12 are the approved plan as written
> beforehand; **§13 records where the implementation diverged and why** — read it alongside any
> section it amends. Every "already exists" claim was verified in the working
> tree and every external claim was checked against current Google/Resend/OWASP documentation on
> 2026-09-01 (sources in §12). Owner decisions are in §0 and are the spec; deviating from one is an
> open decision, not an edit (CLAUDE.md §0.2, §0.3).

---

## 0. Owner rulings (the spec)

| # | Decision | Ruling |
|---|---|---|
| A1 | Email delivery | **Resend**, via DNS records on `vivi-assistant.com`. No mailbox, no Workspace seat, no domain-wide delegation. Added as a second `EmailProvider` behind the existing ABC. |
| A2 | Google flow | **ID token** (the GIS "Sign in with Google" button). The browser hands us a signed JWT; we verify it and mint our own existing session JWT. No refresh tokens, no redirect URIs. |
| A3 | Account linking on a matching email | **Link only if the existing account's email is verified.** An unverified pre-existing account is never auto-linked — it must prove mailbox control first. |
| A4 | Unverified email accounts | **Verification completes signup**: no session until the code is entered. The rows that exist today are **grandfathered** by the migration. Google signups are verified by definition. |

**Answering the question you raised:** a business Gmail address is **not needed**. The
`gmail-776@…` service account is only usable by the existing `GmailEmailService`, whose
`credentials.with_subject(sender)` call *is* domain-wide delegation — that requires a paid Workspace
domain and a real mailbox to impersonate. A1 needs neither: Resend authenticates the **domain** via
SPF/DKIM DNS records, which you already control through the `vivi-assistant.com` registrar.

---

## 1. What already exists (verified, do not rebuild)

| Thing | Where | State |
|---|---|---|
| `users.google_id VARCHAR(255) UNIQUE` + `idx_users_google_id` | migration 001 | **Already there. Never written to by any code path.** |
| `users.password_hash` NULLABLE | migration 001, commented "Null if Google auth" | the groundwork for A2 was laid and abandoned |
| `EmailProvider` ABC + `GmailEmailService` | `app/services/email_service.py` | complete, retry logic, Hebrew errors — and **zero callers** |
| `google-auth 2.53.0` with `id_token.verify_oauth2_token` | transitively via `google-api-python-client` | **verified importable in the venv** |
| `httpx 0.28.1` | requirements.txt | Resend needs no SDK; **this PR adds no new dependency** |
| JWT session (HS256, 7-day TTL), `pupal_auth_token` in localStorage | `auth_service.py`, `lib/auth.tsx` | Google sign-in reuses it verbatim — the session model does not change |
| `/login`, `/signup` pages | `src/app/login/`, `src/app/signup/` | both `router.push('/')`; the onboarding gate then routes new users to `/onboarding` |
| `frontend_base_url = https://vivi-assistant.com` | `app/config.py` | the domain whose DNS A1 needs |

**Does not exist anywhere:** any email verification (signup issues a session immediately, to an
address nobody proved); any HTTP rate limiting (the `rate_limit` greps are all LLM-provider
back-off); any CSP headers (`next.config.js` sets none — so GIS's CSP/iframe requirements are not
a blocker today, but adding a CSP later must account for them).

---

## 2. The security model

This is the part worth reading twice. Sign-in is the one surface where a plausible-looking
implementation is a real vulnerability, so each threat below names its control.

### 2.1 Pre-account hijacking — the reason A3 exists

Vivi's signup today writes a user row for **any** address with no proof of control. So an attacker
can pre-register `victim@school.org` with a password of their choosing. If Google sign-in later
linked identities by matching email, the victim's Google login would land on the attacker's row —
and both credentials would open one account. This is the same shape as Microsoft's *nOAuth* (2023)
and the *Sign in with Apple* JWT flaw (2020).

Two controls, and **both are needed**:
* A4 makes an unverified account unusable, shrinking the window.
* A3 refuses to link a Google identity into an account whose email was never proven.

### 2.2 The identity key is `sub`, never the email

Google's guidance is explicit: *"Only use Google ID token `sub` field as identifier … don't use
email address as an identifier because a Google Account can have multiple email addresses at
different points in time."* So `users.google_id` stores `sub`. Email is matched only to *find a
candidate* for linking, and that match alone never authorizes the link (§2.1).

### 2.3 Token verification — what the server checks

`verify_oauth2_token` checks the signature against Google's rotating public keys, `aud`, and `exp`.
On top of that we check explicitly:

| Claim | Rule | Why |
|---|---|---|
| `iss` | ∈ {`accounts.google.com`, `https://accounts.google.com`} | the library does it, we assert it too — one line, and it is the claim that says Google issued this |
| `aud` | == our client ID | a token minted for a *different* app is otherwise a valid Google token |
| `email_verified` | must be `true` | Google itself can hold unverified addresses; treating one as proof re-opens §2.1 |
| `nonce` | matches a nonce **we issued**, unconsumed, unexpired | replay protection (§2.4) |
| `exp` | not passed | library-enforced |

### 2.4 Replay — the nonce, and why it needs a row

A stolen `credential` is a valid bearer token for its lifetime (~1h). The nonce closes that: the
client asks the server for one, GIS embeds it in the signed token, and the server accepts the token
only if the nonce is one it issued and has not seen used.

That requires server-side state. This codebase has no Redis, so it is a small table
(`auth_nonces`) with the same single-use discipline used elsewhere. **The alternative — a stateless
HMAC nonce — was considered and declined:** it proves *we minted it* but cannot prove *it has not
been used*, which is the entire property being bought.

### 2.5 The verification code

Per OWASP/NIST practice: **6 digits**, **10-minute** expiry, **bcrypt-hashed at rest** (the same
hasher the passwords use — never store a recoverable code), **constant-time** comparison, **5
attempts** then the code dies, **60-second resend cooldown**, and **one active code per user**
enforced by a partial unique index rather than by application bookkeeping.

Expiry is checked **before** the hash comparison — bcrypt is deliberately slow, and an expired code
deserves none of that compute.

> ⚠️ **Rate limiting must be DB-backed, not in-process.** Cloud Run runs `--concurrency=4
> --max-instances=60`, so an in-memory counter is per-instance and an attacker simply gets 60×
> the budget while the logs claim the limit held. The counters live on the code row.

### 2.6 Enumeration

`/resend-code` answers **202 with the same body** whether or not the address exists, and the
verify endpoint returns one generic failure for "no such pending signup", "wrong code" and
"expired". Signup itself already leaks existence via its 400 ("email already registered") — that is
**pre-existing behavior this PR does not change**, flagged here rather than silently widened.

### 2.7 Logging

Never log a code, a `credential`, or a nonce. The existing `logger.info(f"User {user.email} …")`
lines stay as they are — an email in a log is not a secret in this system — but nothing new joins
them.

---

## 3. Data model — migration 024

Idempotent throughout; commit token last (§8 convention). `TIMESTAMPTZ` columns are declared
`DateTime(timezone=True)` on the ORM — the 022 lesson: a naive declaration serializes without an
offset on the write path and with one on every read, and a browser parses the offset-less form as
local time.

```sql
-- users: proof-of-control, and the grandfather clause (A4)
ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMPTZ;

-- A4: every row that exists BEFORE this ships keeps working. These accounts were
-- created when signup issued a session with no proof at all; locking them out
-- would be this migration breaking the only people currently using Vivi.
UPDATE public.users
   SET email_verified_at = created_at
 WHERE email_verified_at IS NULL;

CREATE TABLE IF NOT EXISTS public.email_verification_codes (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    code_hash    TEXT NOT NULL,              -- bcrypt; never the code itself
    expires_at   TIMESTAMPTZ NOT NULL,
    consumed_at  TIMESTAMPTZ,
    attempts     INTEGER NOT NULL DEFAULT 0,
    last_sent_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resend_count INTEGER NOT NULL DEFAULT 0,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ONE active code per user — the RGC-1 / 012 precedent. Enforced by the database
-- rather than by "delete the old one first" application bookkeeping, which is a
-- race, not a rule.
CREATE UNIQUE INDEX IF NOT EXISTS idx_email_codes_one_active_per_user
    ON public.email_verification_codes (user_id)
    WHERE consumed_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_email_codes_expires_at
    ON public.email_verification_codes (expires_at);

-- Nonces (§2.4). Single-use, short-lived, swept on a schedule.
CREATE TABLE IF NOT EXISTS public.auth_nonces (
    nonce_hash  TEXT PRIMARY KEY,            -- sha256 of the issued nonce
    expires_at  TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_auth_nonces_expires_at
    ON public.auth_nonces (expires_at);
```

`users.google_id` is **untouched** — it already exists, unique and indexed, and starts being
written for the first time.

No `auth_provider` column: it is derivable (`google_id IS NOT NULL`, `password_hash IS NOT NULL`),
and a stored copy is a second home for one fact (§0.4).

`app/database.py`: add `"024"` to `EXPECTED_MIGRATIONS`, and both partial/lookup indexes that carry
a `WHERE` to `EXPECTED_PARTIAL_INDEXES` — `idx_email_codes_one_active_per_user` states the
one-active rule, and an index recreated without its predicate would still be "present" by name
while guaranteeing nothing (the 023 lesson).

---

## 4. Backend

### 4.1 The linking decision is a PURE function

The security rule (A3) must be testable without mocking Google, so it lives on its own:

```python
# app/services/google_identity.py
class LinkOutcome(str, Enum):
    SIGN_IN_EXISTING_GOOGLE = "sign_in_existing_google"   # google_id already known
    LINK_TO_VERIFIED_EMAIL  = "link_to_verified_email"    # A3: allowed
    REFUSE_UNVERIFIED_EMAIL = "refuse_unverified_email"   # A3: the nOAuth guard
    CREATE_NEW              = "create_new"

def decide_link(by_google_id, by_email, claims) -> LinkOutcome: ...
```

Four inputs → four outcomes, exhaustively tested as a table. Everything about §2.1 is decided
here, in one place a reviewer can read in thirty seconds.

### 4.2 Endpoints (all in `api/v0/auth.py`, the module that owns the session)

| Endpoint | Body | Returns |
|---|---|---|
| `GET /auth/google/nonce` | — | `{nonce}` — issued, stored hashed, 5-min TTL |
| `POST /auth/google` | `{credential, nonce}` | `AuthResponse` (our JWT + profile) |
| `POST /auth/signup` | unchanged | ⚠️ **CHANGED**: `{verification_required: true, email}` — **no session** (A4) |
| `POST /auth/verify-email` | `{email, code}` | `AuthResponse` — the session is issued here now |
| `POST /auth/resend-code` | `{email}` | `202 {ok: true}` always (§2.6) |

`POST /auth/google` in outline:

1. verify the nonce row (exists, unconsumed, unexpired) → consume it, or 401;
2. `verify_oauth2_token(credential, request, settings.google_oauth_client_id)`;
3. assert `iss`, assert `email_verified is True`, read `sub`, `email`, `name`, `picture`;
4. `decide_link(...)` → act:
   * `SIGN_IN_EXISTING_GOOGLE` → sign in,
   * `LINK_TO_VERIFIED_EMAIL` → set `google_id`, sign in,
   * `CREATE_NEW` → create with `google_id`, `password_hash = NULL`,
     `email_verified_at = now()`, `full_name` from the claim,
   * `REFUSE_UNVERIFIED_EMAIL` → **409** with a Hebrew instruction to verify the mailbox first;
5. mint the existing HS256 JWT via `auth_service.create_access_token` — unchanged;
6. answer `AuthResponse` via `build_user_response` (the ONE profile shape).

> **The signup wire change is the riskiest edit in this PR**, so its blast radius was counted
> rather than estimated. `lib/auth.tsx::signup()` reads `data.access_token` and logs the teacher
> straight in; after A4 there is no token to read, so backend and frontend must land together.
>
> Measured call sites: **5 across 4 backend test files** — `tests/api/conftest.py::_signup` plus a
> private `_fresh_user` in each of `test_users_auth.py`, `test_onboarding.py` and
> `test_onboarding_real_dataset.py` (they were deliberately private so onboarding's destructive
> writes could not touch the session-scoped fixtures) — and **exactly one frontend caller**,
> `src/app/signup/page.tsx:63`.
>
> Those three private helpers are the reason this is a stage of its own: each must become
> "sign up → read the code row → verify → return the session". The right move is to promote ONE
> helper into `tests/api/conftest.py` and have the three modules import it, which both fixes them
> and removes a duplication that already existed.

### 4.3 Email

`ResendEmailService(EmailProvider)` — an `httpx.AsyncClient` POST to `https://api.resend.com/emails`
with `Authorization: Bearer $RESEND_API_KEY`, body `{from, to, subject, html}`, and an
`Idempotency-Key` per send so the existing retry loop cannot deliver twice. A factory
(`get_email_provider()`) picks `resend | gmail | console` from `EMAIL_PROVIDER`, defaulting to
`console` in dev so nobody needs a key to run the app.

The Hebrew code template is RTL, states the 10-minute expiry, and says "if you did not request this,
ignore this message" — the standard, and the honest thing for a code someone else may have triggered.

---

## 5. Frontend

```
src/components/auth/GoogleSignInButton.tsx   ← GIS script + nonce fetch + callback
src/components/auth/VerificationCodePanel.tsx ← 6-digit input, resend w/ cooldown
src/app/signup/page.tsx                       ← MODIFIED: two-phase (form → code)
src/app/login/page.tsx                        ← MODIFIED: + the Google button
src/lib/auth.tsx                              ← MODIFIED: signup() no longer sets a session;
                                                 + verifyEmail(), + loginWithGoogle()
src/copy/auth.ts                              ← NEW: every Hebrew string in the flow
```

`GoogleSignInButton` loads `https://accounts.google.com/gsi/client` via `next/script`
(`strategy="afterInteractive"`), calls `google.accounts.id.initialize({client_id, nonce, callback})`
then `renderButton`. **FedCM has been mandatory since August 2025**, so this is the current library
by construction — there is no legacy `gapi.auth2` path to fall into.

The button renders on **both** pages and is the same component; the only difference is the copy
above it. A teacher who "signs up" with Google and already has an account simply signs in — the
server decides, not the page she happened to open.

Both pages already run outside `SidebarLayout` and both `router.push('/')` on success, where the
onboarding gate takes over. **Google's first-time users land in onboarding exactly like email
users** — `onboarding_completed_at` is null for them too.

The pending-verification email is held in `sessionStorage` so a reload during the code step does not
strand her, and `/signup` rehydrates the code panel from it.

---

## 6. Google Cloud Console — exact setup (project `gen-lang-client-0438328890`)

**OAuth consent screen** (APIs & Services → OAuth consent screen):
* User type **External**; app name `Vivi`; support email; app logo optional.
* Authorized domain: `vivi-assistant.com`.
* Scopes: **`openid`, `email`, `profile` only.** These are *non-sensitive*, which is the whole
  reason this is cheap: **an app using only non-sensitive scopes does not need Google's verification
  review.** Adding any Classroom/Drive scope later changes that.
* **Publish to Production.** Testing mode caps at **100 users** — fine now, a wall at launch.

**Credentials → Create credentials → OAuth client ID → Web application:**
* Authorized **JavaScript origins**:
  `https://vivi-assistant.com`, `https://www.vivi-assistant.com`,
  `http://localhost:3000` (dev), `http://localhost:3100` (Playwright harness).
* Authorized **redirect URIs**: **none needed.** The ID-token/button flow does not redirect; that
  field is for the authorization-code flow (A2 declined).
* The **client secret is not used** by this flow — do not create a dependency on one.

The client ID is public by design: `NEXT_PUBLIC_GOOGLE_CLIENT_ID` (Vercel) and
`GOOGLE_OAUTH_CLIENT_ID` (Cloud Run) hold the **same value**; the backend needs it to check `aud`.

**Resend:** create the account, add `vivi-assistant.com`, paste the SPF/DKIM (and DMARC) records at
the registrar, wait for verification, mint an API key → `RESEND_API_KEY` (Cloud Run secret),
`EMAIL_FROM="Vivi <noreply@vivi-assistant.com>"`.

---

## 7. Tests

| File | Pins |
|---|---|
| `tests/services/test_google_identity.py` | the `decide_link` truth table — all four outcomes, incl. **REFUSE on an unverified pre-existing account** (the nOAuth guard), zero mocks |
| `tests/api/test_google_auth.py` | forged signature → 401; wrong `aud` → 401; expired → 401; `email_verified:false` → 401; nonce replay → 401; unknown nonce → 401; happy paths for create / sign-in / link. Google is stubbed at `verify_oauth2_token` only — **never a fake `get_current_user`** (§9) |
| `tests/api/test_email_verification.py` | signup returns **no token**; wrong code; expired code; 5 failed attempts kill the code; resend cooldown; one-active-code index holds under a double submit; verify issues a working session |
| `tests/api/test_users_auth.py` | existing §9 guards must stay green — the new routes are public by design and belong on the documented exception list beside login/signup/refresh |
| `frontend/src/lib/auth.test.ts` | the two-phase signup state machine (pure) |
| `e2e/auth.spec.ts` | route-mocked: the Google button posts a credential and lands on `/onboarding`; signup shows the code panel and does not navigate; a wrong code shows an error and stays |

The e2e stubs `window.google.accounts.id` before the GIS script loads and drives the callback
directly — the third-party script is not under test, our handling of its output is.

---

## 8. Sequencing

* **S1 — schema.** Migration 024 + ledger + models + `EXPECTED_PARTIAL_INDEXES`.
  Gate: `import app.main`, `test_schema_canon`.
* **S2 — the pure core.** `decide_link` + the code generator/verifier. Zero I/O, fully tested.
  Gate: new unit tests green.
* **S3 — email.** `ResendEmailService` + factory + the Hebrew template, `EMAIL_PROVIDER=console`
  everywhere until the domain verifies. Gate: a console send in dev.
* **S4 — Google endpoint.** nonce issue/consume + `POST /auth/google`.
  Gate: `test_google_auth.py`.
* **S5 — signup split.** The wire change, `conftest._signup` helper, verify + resend endpoints.
  Gate: the WHOLE backend suite — this is the stage that can break unrelated tests.
* **S6 — frontend.** Button, code panel, both pages, `auth.tsx`, copy module + gate.
  Gate: `tsc`, vitest, `check:copy`, `e2e/auth.spec.ts`, then the full Playwright suite.

## 9. Non-goals (named so they are not absorbed)

Google API access on the teacher's behalf (Classroom rosters, Drive import) — that needs A2's
declined code flow and a scope that triggers Google verification review. Password reset — it reuses
this PR's code+email machinery and becomes nearly free afterwards, but it is not in scope here.
Account settings for linking/unlinking a Google identity. MFA. General HTTP rate limiting beyond
the two OTP endpoints.

## 10. What only you can do

1. Resend account + `vivi-assistant.com` DNS records (SPF/DKIM/DMARC) + API key.
2. The Console steps in §6, ending with **Publish to Production**.
3. Env: `NEXT_PUBLIC_GOOGLE_CLIENT_ID` (Vercel) · `GOOGLE_OAUTH_CLIENT_ID`, `EMAIL_PROVIDER=resend`,
   `RESEND_API_KEY`, `EMAIL_FROM` (Cloud Run).
4. Apply migration 024 (test + production), and deploy both halves **together** — §4.2's signup
   change is not backward compatible.

## 11. Risk register

| Risk | Handling |
|---|---|
| The signup wire change breaks the suite and the live app | One shared test helper; backend + frontend ship together; called out as S5's own stage |
| DNS/Resend verification takes hours | `EMAIL_PROVIDER=console` keeps every stage buildable and testable meanwhile |
| Consent screen left in Testing | Explicit §6 step; the 100-user cap is a launch wall, not a warning |
| A CSP added later breaks GIS | Noted in §1: none exists today; FedCM has iframe/CSP requirements when one is introduced |
| Nonce table grows | Swept by expiry; the codebase already has the startup-sweep pattern |

## 12. Sources

- [How user authorization works — Google](https://developers.google.com/identity/oauth2/web/guides/how-user-authz-works)
- [Verify the Google ID token on your server side](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token)
- [Migrate to FedCM / FedCM mandatory](https://developers.google.com/identity/gsi/web/guides/fedcm-migration)
- [Sign in with Google JavaScript API reference (nonce)](https://developers.google.com/identity/gsi/web/reference/js-reference)
- [OAuth 2.0 policies & verification (non-sensitive scopes)](https://developers.google.com/identity/protocols/oauth2/policies)
- [Unverified apps / Testing-mode user cap](https://support.google.com/cloud/answer/7454865?hl=en)
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [OWASP Email Validation & Verification Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Email_Validation_and_Verification_Cheat_Sheet.html)
- [OAuth account-linking / pre-account-hijacking](https://www.descope.com/blog/post/5-oauth-misconfigurations)
- [Resend — send email API reference](https://resend.com/docs/api-reference/emails/send-email)

---

## 13. Implementation notes — what actually shipped (2026-09-01)

The plan was followed. Six things came out differently, each because building it surfaced
something the plan had wrong or incomplete.

### 13.1 `/auth/login` had to be closed too — the plan missed half of A4

**Planned:** signup stops issuing a session.
**Shipped:** that, **plus a 403 on `/auth/login` when `email_verified_at IS NULL`.**

**Why:** without it A4 is decorative. An attacker who pre-registers `victim@school.org` simply logs
in with the password he chose, and the account the linking rule is supposed to distrust is one he
is already inside. Caught by `test_an_unverified_account_cannot_log_in`, which I wrote expecting it
to pass and which failed on the first run.

403 rather than 401 is deliberate and load-bearing: her password was RIGHT. The client uses the
distinction to open the verification panel instead of telling her she mistyped it.

### 13.2 Signup became one transaction

`create_user` used to `commit()`. With the code row added afterwards, a failed send would have left
an un-rollback-able account — a teacher holding an address she can neither use nor re-register. It
now `flush()`es and its single caller owns the commit, so the user row and the code land together
or not at all. Pinned by `test_a_failed_send_rolls_the_whole_signup_back`.

### 13.3 The nonce fetch is once-per-mount, and the usual cleanup idiom is WRONG here

React StrictMode double-invokes mount effects. The first version fetched twice: nonce #1 was
already handed to GIS by `initialize()`, while the component then posted nonce #2 — the server
would refuse an entirely legitimate sign-in. A `useRef` guard fixes it.

But the standard `let alive = true; return () => { alive = false }` cleanup **must not** be combined
with that guard: StrictMode runs the effect, tears it down (flipping the flag), then runs it again
where the guard returns early — so the one in-flight fetch resolves into a dead flag, the nonce
never lands, and the button never renders at all. Both states were observed; the e2e caught each.

### 13.4 Test users needed one shared helper

The code is bcrypt-hashed the instant it is minted, so nothing can hand it back. Rather than a back
door in production code (an env var pinning the code, a debug field on the response),
`tests/api/auth_helpers.py` patches the GENERATOR for the duration of the signup call only. The
four private `_fresh_user` copies now delegate to it — the duplication the plan predicted would
make this change expensive, removed as part of making it.

### 13.5 Two gates extended

`check:copy` now treats login/signup/`components/auth`/`copy/auth` as BLOCKING surfaces. It also
skips `src/data` for the imperative scan: the Ministry export contains «מתי"א זבולון-**אשר**», and a
gate that permanently reports a school's name as a copy violation trains the dismissal reflex it
exists to prevent.

`playwright.config.ts` supplies `NEXT_PUBLIC_GOOGLE_CLIENT_ID` — the button renders NOTHING without
one (a dead sign-in button is worse than no button), so the harness must provide a value. The GIS
script is stubbed and never contacted.

### 13.6 Verification actually run

| Gate | Result |
|---|---|
| migration 024 applied to Vivi-Test, then re-applied | idempotent; `SCHEMA OK: head 024, 6 partial indexes` |
| `tests/services/test_google_identity.py` + `test_verification_codes.py` (52, pure, zero mocks) | pass |
| `tests/api/test_google_auth.py` (18) | pass |
| `tests/api/test_email_verification.py` (19) | pass |
| `tests/api/test_users_auth.py` (36 §9 guards, unchanged) | pass |
| full backend suite | **1206 passed, 12 failed — the SAME 12 by name as the pre-auth baseline** |
| frontend unit (912) + `check:copy` + `check:tokens` + `tsc` | pass |
| `e2e/auth.spec.ts` (9 journeys) | pass |

### 13.7 Migration 024 IS applied to production (2026-09-01)

Applied on the owner's instruction after a local backend — which points at the production database —
500'd on `column users.email_verified_at does not exist`. That was the documented mismatch, not a
separate bug: the code assumed 024's DDL and production was still at 023. The boot check had said so
(`SCHEMA MISMATCH: 024 NOT APPLIED`) and, by design, warned rather than crashing.

Verified afterwards: ledger `…023,024`; both tables and the partial unique index present;
`verify_schema_head()` → `SCHEMA OK: migration head 024`; and **6 of 6 production accounts
grandfathered**, so no existing teacher meets the new 403.

The DDL is additive, so the OLD backend still deployed on Cloud Run is unaffected — it simply does
not select the new column. §4.2's signup change remains not backward compatible, so **backend and
frontend must still deploy together**.

### 13.9 The nonce fetch retries (2026-09-05)

Found in live use: the Google button renders ONLY once a nonce lands, so a single failed nonce
request killed Sign in with Google for that whole page load, recoverable only by a manual reload.
Not a rare edge — `uvicorn --reload` restarts on every backend file save, so any page load landing
in that window lost the button.

`fetchNonceWithRetry` now makes up to 3 attempts (400ms / 1200ms backoff) and reports
`GOOGLE_UNAVAILABLE` only once they are spent. A response missing the `nonce` field counts as a
failure rather than being stored, since an undefined nonce renders no button and would be POSTed.

**The retry must stay BEFORE `initialize()` and nowhere later.** A nonce is single-use and is handed
to GIS at initialize; retrying after that leaves Google signing a token carrying nonce #1 while the
client posts nonce #2, and the server refuses a legitimate sign-in — the same defect StrictMode's
double mount produced (§13.3). Pinned by two e2e tests: one that a first-attempt failure still ends
with a rendered button whose posted nonce matches, and one that the retry is bounded and says so.

**Separately, and NOT a bug:** a fresh `The given origin is not allowed for the given client ID`
403 right after editing the Console's authorized origins is Google's own propagation delay, not a
misconfiguration. It clears itself in a minute or two. Expect it on the live site the first time
production origins are added.

### 13.8 The console provider prints the code in dev

Suppressing the body meant a local signup created an account that could never be verified — the
code went nowhere. `ConsoleEmailService` now logs `CODE=NNNNNN` when `is_dev_env()` (the same
predicate that gates `create_all`, so "dev" means one thing here), and logs recipient + subject
only otherwise: selecting this provider in production is a misconfiguration that must not also
become a disclosure.

## 14. Still outstanding for you

1. **Resend**: account, `vivi-assistant.com` DNS (SPF/DKIM/DMARC), API key.
2. **Google Console** (§6), ending with **Publish to Production** — Testing mode caps at 100 users.
3. **Env**: `NEXT_PUBLIC_GOOGLE_CLIENT_ID` (Vercel) · `GOOGLE_OAUTH_CLIENT_ID`,
   `EMAIL_PROVIDER=resend`, `RESEND_API_KEY`, `EMAIL_FROM` (Cloud Run).
   Until the client ID is set the button renders nothing and email/password keeps working, so the
   two halves can be switched on independently.
4. ~~Apply 024 to production~~ — **done 2026-09-01**. Still to do: deploy backend + frontend
   **together** (the signup response change is not backward compatible).
