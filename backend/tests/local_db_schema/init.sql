-- A-10 — the roles Supabase provides and the Vivi schema assumes, for the LOCAL test
-- cluster only (scripts/local_test_db.py runs this as the cluster superuser; idempotent).
--
--   anon, authenticated — the Data API's roles. NOLOGIN, exactly as on Supabase. They
--     own nothing and hold nothing; tests/test_public_schema_lockdown.py proves that
--     against whatever database the suite runs on, so they must EXIST for that proof
--     to mean anything (034 revokes only where its role exists).
--   postgres — the role the app connects as. On Supabase it is NOT a superuser: it owns
--     the public schema and has BYPASSRLS. Same shape here, so a test that would need
--     superuser powers fails locally exactly as it would on Vivi-Test.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        CREATE ROLE anon NOLOGIN NOINHERIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        CREATE ROLE authenticated NOLOGIN NOINHERIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'postgres') THEN
        CREATE ROLE postgres LOGIN NOSUPERUSER BYPASSRLS CREATEDB CREATEROLE;
    END IF;
END $$;
