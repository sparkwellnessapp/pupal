-- 034 — lock down the `public` schema (SEC-1, owner ruling 2026-09-28). PRIVILEGES ONLY: no data touched.
--
-- WHY. Row-level security was OFF on every table in `public` (census C-4 recorded it on
-- 2026-09-27; the owner verified all 26). Supabase's default grants give the `anon` and
-- `authenticated` roles full access to every table created in `public`, and the Data API
-- (PostgREST) serves those roles to anyone holding the project's anon key. Nothing in this
-- codebase uses the Data API (SEC-1 step 1: no supabase-js, no supabase-py, no /rest/v1) —
-- every read and write goes through the backend's own connection — so the grants were pure
-- exposure, with no consumer.
--
-- WHAT. Default deny, three ways, each idempotent (safe to re-run):
--   1. ENABLE ROW LEVEL SECURITY on EVERY public table, found through pg_tables so a table
--      added before this runs cannot be missed. NO policies: every role that is neither the
--      table's owner nor BYPASSRLS sees zero rows. NOT `FORCE` — the owner (the backend's
--      role) keeps its access, which is what makes this safe to apply under a live service.
--   2. REVOKE every privilege anon/authenticated hold on public tables, sequences and
--      functions, and EXECUTE on public functions from PUBLIC.
--   3. The same REVOKEs as DEFAULT PRIVILEGES for objects `postgres` creates later, so a
--      future `CREATE TABLE` does not silently re-grant them. (The convention that every
--      CREATE TABLE in a later migration is followed by ENABLE ROW LEVEL SECURITY lives in
--      CLAUDE.md and is pinned by tests/test_public_schema_lockdown.py.)
--
-- PRECONDITION (checked before applying, SEC-1): the connecting backend role OWNS every public
-- table or has BYPASSRLS — otherwise enabling RLS hides every row from the service itself.
--
-- The anon/authenticated roles exist on Supabase; a plain local Postgres has neither, so
-- each role-specific statement runs only where its role exists.

DO $$
DECLARE
    t record;
BEGIN
    FOR t IN SELECT schemaname, tablename FROM pg_tables WHERE schemaname = 'public' LOOP
        EXECUTE format('ALTER TABLE %I.%I ENABLE ROW LEVEL SECURITY', t.schemaname, t.tablename);
    END LOOP;
END $$;

DO $$
DECLARE
    r text;
BEGIN
    FOREACH r IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
            EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA public FROM %I', r);
            EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM %I', r);
            EXECUTE format('REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM %I', r);
            EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public '
                           'REVOKE ALL ON TABLES FROM %I', r);
            EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public '
                           'REVOKE ALL ON SEQUENCES FROM %I', r);
        END IF;
    END LOOP;
END $$;

REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

-- Commit token LAST: this row lands only if every statement above landed.
INSERT INTO public.schema_migrations (version, note)
VALUES ('034', 'lockdown_public_schema — RLS on every public table, no anon/authenticated grants (SEC-1)')
ON CONFLICT DO NOTHING;
