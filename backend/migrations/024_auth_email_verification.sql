-- 024: verified email signup + Google sign-in state (auth PR)
--
-- WHY. Signup currently writes a user row for ANY address with no proof of
-- control, and issues a session immediately. That is the pre-account-hijacking
-- precondition: an attacker registers victim@school.org, the victim later signs
-- in with Google, and a naive email match binds both credentials to one row
-- (the shape of Microsoft "nOAuth", 2023, and the Sign in with Apple JWT flaw,
-- 2020). Two columns close it — proof of control, and a linking rule that
-- refuses to trust an account that has none.
--
-- users.google_id ALREADY EXISTS (migration 001, UNIQUE + indexed) and has never
-- been written by any code path. It is untouched here and starts being used.
-- There is deliberately NO auth_provider column: it is derivable from
-- (google_id IS NOT NULL, password_hash IS NOT NULL), and a stored copy would be
-- a second home for one fact (CLAUDE.md §0.4).
--
-- Idempotent: re-running this whole file is always the answer (013 convention).

-- ---------------------------------------------------------------------------
-- 1. Proof that the address belongs to whoever holds the account.
-- ---------------------------------------------------------------------------
ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMPTZ;

-- GRANDFATHER CLAUSE (owner ruling A4). Every row that exists BEFORE this ships
-- was created when signup issued a session with no proof at all. Those accounts
-- are the only ones currently in use; locking them out would be this migration
-- breaking the people it is meant to protect. New signups must verify.
--
-- Idempotent by predicate, not by luck: a re-run stamps nothing, because every
-- row it would touch already has a value.
UPDATE public.users
   SET email_verified_at = created_at
 WHERE email_verified_at IS NULL;

-- ---------------------------------------------------------------------------
-- 2. The verification codes.
-- ---------------------------------------------------------------------------
-- code_hash, never the code: even the database must not hold a recoverable
-- one-time code. attempts/resend_count live HERE, on the row, because Cloud Run
-- runs up to 60 instances — an in-process counter is per-instance, so it would
-- hand an attacker 60x the budget while the logs claimed the limit held.
CREATE TABLE IF NOT EXISTS public.email_verification_codes (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    code_hash    TEXT NOT NULL,
    expires_at   TIMESTAMPTZ NOT NULL,
    consumed_at  TIMESTAMPTZ,
    attempts     INTEGER NOT NULL DEFAULT 0,
    resend_count INTEGER NOT NULL DEFAULT 0,
    last_sent_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ONE active code per user — the RGC-1 / 012 precedent. Enforced by the database
-- rather than by "delete the old one first" application bookkeeping, which is a
-- race and not a rule. A consumed code stays as history and stops constraining.
CREATE UNIQUE INDEX IF NOT EXISTS idx_email_codes_one_active_per_user
    ON public.email_verification_codes (user_id)
    WHERE consumed_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_email_codes_expires_at
    ON public.email_verification_codes (expires_at);

-- ---------------------------------------------------------------------------
-- 3. Sign-in-with-Google nonces (replay protection).
-- ---------------------------------------------------------------------------
-- A stolen Google `credential` is a valid bearer token for its ~1h lifetime. The
-- nonce is what makes it single-use: it is minted here, embedded in the signed
-- ID token by Google, and accepted once.
--
-- This is state, deliberately. A stateless HMAC nonce was considered and
-- declined: it proves WE minted it but cannot prove it has not been used, which
-- is the entire property being bought.
CREATE TABLE IF NOT EXISTS public.auth_nonces (
    nonce_hash  TEXT PRIMARY KEY,          -- sha256(nonce); the nonce itself is never stored
    expires_at  TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_auth_nonces_expires_at
    ON public.auth_nonces (expires_at);

-- Commit token LAST: this row lands only if every statement above landed.
INSERT INTO public.schema_migrations (version, note)
VALUES ('024', 'users.email_verified_at (+grandfather backfill) + email_verification_codes + auth_nonces')
ON CONFLICT DO NOTHING;
