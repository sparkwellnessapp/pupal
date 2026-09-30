-- A-10 snapshot of Vivi-Test (eqnbojbxsdafwtxvuyuy), schema `public`, at ledger head 034.
-- Generated 2026-09-30 by `python scripts/local_test_db.py snapshot` — do not hand-edit; regenerate.
-- Reversed before dumping (on Vivi-Test, not in this checkout): 035_down_plan_cache_config_hash.sql
--
-- PostgreSQL database dump
--


-- Dumped from database version 17.6
-- Dumped by pg_dump version 17.6

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Data for Name: schema_migrations; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.schema_migrations (version, applied_at, note) FROM stdin;
001	2026-08-22 23:11:49.562593+00	test-db rebuild 2026-08-23
002	2026-08-22 23:11:50.062532+00	test-db rebuild 2026-08-23
003	2026-08-22 23:11:50.569778+00	test-db rebuild 2026-08-23
004	2026-08-22 23:11:51.094277+00	test-db rebuild 2026-08-23
005	2026-08-22 23:11:51.612483+00	test-db rebuild 2026-08-23
006	2026-08-22 23:11:52.121737+00	test-db rebuild 2026-08-23
007	2026-08-22 23:11:52.627842+00	test-db rebuild 2026-08-23
008	2026-08-22 23:11:53.169196+00	test-db rebuild 2026-08-23
009	2026-08-22 23:11:53.658312+00	test-db rebuild 2026-08-23
010	2026-08-22 23:11:54.20228+00	test-db rebuild 2026-08-23
011	2026-08-22 23:11:54.717845+00	test-db rebuild 2026-08-23
012	2026-08-22 23:11:55.267103+00	test-db rebuild 2026-08-23
013	2026-08-22 23:11:55.795823+00	test-db rebuild 2026-08-23
014	2026-08-22 23:11:56.299344+00	test-db rebuild 2026-08-23
015	2026-08-22 23:11:56.806574+00	test-db rebuild 2026-08-23
016	2026-08-22 23:11:57.319726+00	test-db rebuild 2026-08-23
017	2026-08-22 23:11:57.841959+00	test-db rebuild 2026-08-23
018	2026-08-30 13:53:44.053338+00	schools + users.school_id (nullable FK) + normalized-exact unique index — PR-G6 override attribution
019	2026-08-31 10:07:41.898522+00	graded_tests.opened_at — first teacher open (PR-G8)
020	2026-08-31 11:09:34.346985+00	grading_batches.appendix_include_criteria + stamp_position_default (PR-G9)
021	2026-08-31 11:09:35.784023+00	graded_tests.returned_exam_key — returned-exam render cache (PR-G9)
022	2026-08-31 12:04:00.277472+00	users.gender + users.onboarding_completed_at + user_schools junction — onboarding
023	2026-08-31 15:07:55.251978+00	schools.ministry_symbol + partial unique symbol index; 018 name index narrowed to symbol-less rows
024	2026-09-01 08:17:55.460153+00	users.email_verified_at (+grandfather backfill) + email_verification_codes + auth_nonces
025	2026-09-04 09:55:11.984048+00	grading_batches.expected_test_count — upload-stage in-flight fact (Stage A / R9)
026	2026-09-06 04:41:55.477214+00	grading_plans — compiled GradingPlans keyed by contract hash (PLAN COMPILER v2, production wiring)
027	2026-09-08 16:42:57.630429+00	rubrics.subject — the durable subject key (multisubject seam, D-10); backfilled from contract_json
028	2026-09-09 10:50:17.27309+00	onboarding next-exam step: next_exam_date/answered_at/reask_sent_at + phone + whatsapp_opt_in + guided_session_requested_at
029	2026-09-09 13:22:33.277677+00	graded_tests.transcription_contract_version — pin the second half of the grading input (VER-2 symmetry)
030	2026-09-09 20:21:11.560601+00	naive timestamp columns -> timestamptz (batch/session/pdf/raw): the wire was serialising UTC instants with no offset, so browsers parsed them as local time
031	2026-09-23 13:00:13.44165+00	students.notes dropped: the profile is a ledger of facts, not a place for judgements (student-profile PR, OD-3/M-A6)
033	2026-09-23 13:00:19.429274+00	purge_failures — the student purge's ledger of object deletes that failed (M-B2, PRV-3)
032	2026-09-23 13:08:14.877873+00	student-data FKs -> ON DELETE NO ACTION (AM-B1) + tenant constraints (AM-B4): a delete happens only when it is spelled out
034	2026-09-28 15:03:04.613392+00	lockdown_public_schema — RLS on every public table, no anon/authenticated grants (SEC-1)
\.


--
-- PostgreSQL database dump complete
--


