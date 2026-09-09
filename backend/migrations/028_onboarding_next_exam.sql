-- 028 — the onboarding "מתי המבחן הבא שלך?" step and the outreach queue it feeds.
--
-- WHY. Between signup and a teacher's first real grading batch there can be
-- weeks, set by the school calendar and not by her motivation. That gap is the
-- churn window. One answered question turns an unusable signup into a scheduled
-- activation event, and the date is also an INSTRUMENT: the distribution of
-- first-exam dates across schools decides when the grading wave actually lands.
-- That is why it lives here and not only in a spreadsheet.
--
-- ONB-3 (DBIsTheRecord): every value in the Google Sheet originates in these
-- columns. No application code ever reads the sheet back, and
-- `app.scripts.rebuild_onboarding_sheet` can rebuild it from this table alone.
--
-- SIX COLUMNS ON `users`, not a new table: this is strictly one-to-one with the
-- user and at this cardinality a side table buys a join and nothing else.
--
-- DELIBERATELY ABSENT — each was proposed and each is a SECOND representation of
-- a fact already present here. Re-adding any of them needs an open decision:
--   * an `unknown` boolean      → it is (answered_at IS NOT NULL AND date IS NULL)
--   * a `reask_due_at`          → it is answered_at + 14 days
--   * a step-completion stamp   → it is answered_at
--   * a `guided_session_date`   → ONB-4: Cal.com owns the booking and she can
--                                 reschedule there, so a mirrored date goes
--                                 silently stale and would be believed.
--
-- Idempotent: re-running this whole file is always the answer (013 convention).

ALTER TABLE public.users
    -- Her stated date. NULL when unknown OR never answered — the two are told
    -- apart by next_exam_answered_at, never by a second flag.
    ADD COLUMN IF NOT EXISTS next_exam_date DATE,
    -- ONB-2 (UnknownIsAnAnswer): "עוד לא יודעת" SETS this with a null date.
    -- NULL here means she never reached the step or skipped it.
    ADD COLUMN IF NOT EXISTS next_exam_answered_at TIMESTAMPTZ,
    -- Idempotency guard for the 14-day re-ask digest.
    ADD COLUMN IF NOT EXISTS next_exam_reask_email_sent_at TIMESTAMPTZ,
    -- Stored AS TYPED. No format validation anywhere: rejecting a teacher's
    -- phone format mid-onboarding is hostility disguised as rigour. Normalised
    -- to E.164 on READ, when a wa.me link is built.
    ADD COLUMN IF NOT EXISTS phone TEXT,
    -- Explicit consent, NEVER defaulted true. This column is the ONLY thing
    -- that may authorise a WhatsApp message: the digest emits a wa.me link only
    -- when it is true, and the sheet carries the state beside the number so a
    -- human working the queue cannot message a teacher who declined.
    ADD COLUMN IF NOT EXISTS whatsapp_opt_in BOOLEAN NOT NULL DEFAULT false,
    -- ONB-4 (OwnedFactsOnly): that she ASKED is ours; when the call ended up
    -- being scheduled for is Cal.com's.
    ADD COLUMN IF NOT EXISTS guided_session_requested_at TIMESTAMPTZ;

-- The re-ask candidate set, and only it: teachers who answered "unknown" and
-- are waiting to be asked again. PARTIAL on purpose — the vast majority of rows
-- either never answered or gave a date, and neither is ever a candidate, so
-- indexing them would be paying for rows the query cannot want.
CREATE INDEX IF NOT EXISTS idx_users_reask_candidates
    ON public.users (next_exam_answered_at)
    WHERE next_exam_date IS NULL;

-- Commit token LAST: this row lands only if every statement above landed.
INSERT INTO public.schema_migrations (version, note)
VALUES ('028', 'onboarding next-exam step: next_exam_date/answered_at/reask_sent_at + phone + whatsapp_opt_in + guided_session_requested_at')
ON CONFLICT DO NOTHING;
