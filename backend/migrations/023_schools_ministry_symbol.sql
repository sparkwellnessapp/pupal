-- 023: schools.ministry_symbol — exact institution identity (owner-ruled 2026-08-31)
--
-- WHY. Until now a school's identity was its NORMALIZED NAME (018's unique
-- index). That is not an identity: measured against the real Ministry export
-- (2,194 institutions), 82 name-groups covering 213 rows share a normalized
-- name — nine different «בית אקשטיין» schools in nine cities, and TWO of them in
-- the SAME city (symbols 320440 and 338384, both פרדס חנה-כרכור). Under
-- name-only identity those two institutions collapse into one row and cannot be
-- told apart even with the city. The Ministry symbol (סמל מוסד) tells them
-- apart, does not move when someone spells the name differently, and survives a
-- refresh of the source list.
--
-- WHAT IT PROTECTS. School is one of PR-G6's five override-attribution keys. A
-- school split across several rows — or two schools merged into one — makes
-- every per-school reading of the override data quietly wrong.
--
-- ⚠️ THE INDEX SWAP IS LOAD-BEARING, NOT HOUSEKEEPING. 018's index is UNIQUE on
-- the normalized name across the WHOLE table, so it forbids a second row named
-- «בית אקשטיין» — it would block the exact case this migration exists to allow,
-- and adding the symbol column alone would achieve nothing. The name rule is
-- therefore narrowed to the rows it can still honestly govern: those with NO
-- symbol, i.e. schools a teacher typed herself. For those, name convergence is
-- preserved exactly as before (two teachers typing the same name still meet on
-- one row). For the rest, the symbol governs.
--
-- Both indexes are PARTIAL, each stating the population it rules:
--     ministry_symbol IS NOT NULL → unique symbol   (one row per institution)
--     ministry_symbol IS NULL     → unique name     (the pre-023 rule, kept)
--
-- Idempotent: re-running this whole file is always the answer (013 convention).

ALTER TABLE public.schools
    ADD COLUMN IF NOT EXISTS ministry_symbol TEXT;

-- One row per real institution.
CREATE UNIQUE INDEX IF NOT EXISTS idx_schools_ministry_symbol
    ON public.schools (ministry_symbol)
    WHERE ministry_symbol IS NOT NULL;

-- Retire 018's whole-table name rule and re-create it over the symbol-less rows.
-- Dropped BEFORE the replacement is created so the two never coexist; both
-- statements are idempotent, so a re-run of this file is a no-op either way.
DROP INDEX IF EXISTS public.idx_schools_normalized_name;

CREATE UNIQUE INDEX IF NOT EXISTS idx_schools_normalized_name_symbolless
    ON public.schools (lower(regexp_replace(btrim(name), '\s+', ' ', 'g')))
    WHERE ministry_symbol IS NULL;

-- Deliberately NO backfill. Existing rows were created by normalized NAME and
-- carry no evidence of which institution they are; stamping a symbol onto them
-- by name match would invent exactly the identity this migration exists to stop
-- guessing at (the two-schools-one-name case above). They stay symbol-less and
-- keep working under the name rule. Reconciling one is an operator decision with
-- evidence, never an automatic UPDATE.

-- Commit token LAST: this row lands only if every statement above landed.
INSERT INTO public.schema_migrations (version, note)
VALUES ('023', 'schools.ministry_symbol + partial unique symbol index; 018 name index narrowed to symbol-less rows')
ON CONFLICT DO NOTHING;
