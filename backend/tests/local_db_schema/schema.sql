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
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA public;


--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA public IS 'standard public schema';


--
-- Name: share_permission; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.share_permission AS ENUM (
    'view',
    'edit'
);


--
-- Name: subscription_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.subscription_status AS ENUM (
    'trial',
    'active',
    'expired',
    'cancelled'
);


--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = timezone('utc'::text, now());
    RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: auth_nonces; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_nonces (
    nonce_hash text NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    consumed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: class_memberships; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.class_memberships (
    class_id uuid NOT NULL,
    student_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE class_memberships; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.class_memberships IS 'M:N join between classes and students. Per Phase 0c §3.';


--
-- Name: classes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.classes (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    name character varying(255) NOT NULL,
    subject_matter_id integer,
    school_year character varying(20),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE classes; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.classes IS 'Teacher-defined groupings of students. Per-teacher scoped. Per Phase 0c §2.';


--
-- Name: email_verification_codes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.email_verification_codes (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    code_hash text NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    consumed_at timestamp with time zone,
    attempts integer DEFAULT 0 NOT NULL,
    resend_count integer DEFAULT 0 NOT NULL,
    last_sent_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: graded_test_pdfs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.graded_test_pdfs (
    id uuid NOT NULL,
    graded_test_id uuid NOT NULL,
    rubric_id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    gcs_uri character varying(500) NOT NULL,
    gcs_bucket character varying(255) NOT NULL,
    gcs_object_path character varying(500) NOT NULL,
    filename character varying(255) NOT NULL,
    file_size_bytes double precision,
    content_type character varying(100)
);


--
-- Name: graded_tests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.graded_tests (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    rubric_id uuid NOT NULL,
    transcription_id uuid NOT NULL,
    student_id uuid NOT NULL,
    batch_id uuid,
    rubric_contract_version character varying(50) NOT NULL,
    student_name character varying(255) NOT NULL,
    filename character varying(500),
    draft_json jsonb,
    draft_created_at timestamp with time zone,
    contract_json jsonb,
    approved_at timestamp with time zone,
    regraded_from_id uuid,
    regraded_to_id uuid,
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    error_message text,
    total_score numeric(10,2),
    total_possible numeric(10,2),
    percentage numeric(5,2),
    llm_calls_count integer DEFAULT 0 NOT NULL,
    grading_duration_ms integer DEFAULT 0 NOT NULL,
    model_version character varying(50),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    grading_started_at timestamp with time zone,
    total_input_tokens integer,
    total_output_tokens integer,
    total_cost_usd numeric(10,4),
    prompt_version character varying(50),
    opened_at timestamp with time zone,
    returned_exam_key text,
    transcription_contract_version text,
    CONSTRAINT graded_tests_status_check CHECK (((status)::text = ANY (ARRAY[('pending'::character varying)::text, ('grading'::character varying)::text, ('draft'::character varying)::text, ('approved'::character varying)::text, ('failed'::character varying)::text]))),
    CONSTRAINT graded_tests_status_consistency CHECK (((((status)::text = 'pending'::text) AND (draft_json IS NULL) AND (contract_json IS NULL)) OR (((status)::text = 'grading'::text) AND (draft_json IS NULL) AND (contract_json IS NULL)) OR (((status)::text = 'draft'::text) AND (draft_json IS NOT NULL) AND (contract_json IS NULL)) OR (((status)::text = 'approved'::text) AND (draft_json IS NOT NULL) AND (contract_json IS NOT NULL) AND (approved_at IS NOT NULL)) OR (((status)::text = 'failed'::text) AND (error_message IS NOT NULL))))
);


--
-- Name: TABLE graded_tests; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.graded_tests IS 'GradedTest Draft+Contract. Per (transcription, rubric version, grading pass) triple. Per Phase 0c §5.';


--
-- Name: COLUMN graded_tests.draft_json; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.graded_tests.draft_json IS 'GradedTestDraft Pydantic model. Agent outcomes + teacher_overrides overlay.';


--
-- Name: COLUMN graded_tests.contract_json; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.graded_tests.contract_json IS 'GradedTestContract Pydantic model. Frozen on approval. contract_version inside JSONB.';


--
-- Name: COLUMN graded_tests.regraded_from_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.graded_tests.regraded_from_id IS 'Revision chain: the row this row replaces. NULL for first grade in a chain.';


--
-- Name: COLUMN graded_tests.regraded_to_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.graded_tests.regraded_to_id IS 'Revision chain: the row that replaces this row. NULL for the current leaf.';


--
-- Name: COLUMN graded_tests.transcription_contract_version; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.graded_tests.transcription_contract_version IS 'The TranscriptionContract.contract_version consumed at grade time (029). NULL = the row predates the pin; never back-filled, because a guessed provenance is worse than a recorded absence.';


--
-- Name: grading_batches; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.grading_batches (
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone,
    user_id uuid NOT NULL,
    rubric_id uuid NOT NULL,
    contract_version character varying(50),
    name character varying(255),
    status character varying(30) NOT NULL,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    class_id uuid,
    rubric_contract_version character varying(50),
    test_count integer DEFAULT 0 NOT NULL,
    transcription_failures jsonb DEFAULT '[]'::jsonb NOT NULL,
    stamp_position_default jsonb,
    appendix_include_criteria boolean DEFAULT false NOT NULL,
    expected_test_count integer,
    CONSTRAINT grading_batches_status_check CHECK (((status)::text = ANY (ARRAY[('pending'::character varying)::text, ('in_progress'::character varying)::text, ('completed'::character varying)::text, ('partially_completed'::character varying)::text, ('failed'::character varying)::text])))
);


--
-- Name: TABLE grading_batches; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.grading_batches IS 'Teacher-defined groupings of grading operations. Counts derived from graded_tests. Per Phase 0c §6.';


--
-- Name: grading_plans; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.grading_plans (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    rubric_id uuid,
    contract_version text NOT NULL,
    contract_sha256 text NOT NULL,
    status text NOT NULL,
    plan_version text,
    plan_json jsonb,
    skeleton_json jsonb,
    compiler_version text,
    segmenter_model text,
    router_model text,
    wording_source text,
    cost_usd numeric(10,4) DEFAULT 0 NOT NULL,
    error_message text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    built_at timestamp with time zone,
    CONSTRAINT grading_plans_status_check CHECK ((status = ANY (ARRAY['queued'::text, 'building'::text, 'ready'::text, 'failed'::text, 'superseded'::text]))),
    CONSTRAINT grading_plans_status_consistency CHECK ((((status = 'ready'::text) AND (plan_json IS NOT NULL) AND (plan_version IS NOT NULL) AND (built_at IS NOT NULL) AND (wording_source IS NOT NULL)) OR ((status = 'superseded'::text) AND (plan_json IS NOT NULL)) OR ((status = 'failed'::text) AND (error_message IS NOT NULL)) OR (status = ANY (ARRAY['queued'::text, 'building'::text])))),
    CONSTRAINT grading_plans_wording_source_check CHECK ((wording_source = ANY (ARRAY['segmented'::text, 'placeholder'::text])))
);


--
-- Name: grading_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.grading_sessions (
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone,
    teacher_id uuid,
    rubric_id uuid NOT NULL,
    batch_id uuid,
    contract_version character varying(50) NOT NULL,
    student_name character varying(255) NOT NULL,
    filename character varying(500),
    student_answer_document_id uuid,
    status character varying(20) NOT NULL,
    total_questions integer NOT NULL,
    total_criteria integer NOT NULL,
    completed_criteria integer NOT NULL,
    current_question_idx integer NOT NULL,
    current_criterion_idx integer NOT NULL,
    state_snapshot json,
    graded_test_draft_id uuid,
    graded_test_draft_json json,
    error_message text,
    warnings json,
    skipped_criteria json,
    flagged_outcomes json,
    total_rules_evaluated integer NOT NULL,
    rules_with_valid_quotes integer NOT NULL,
    rules_flagged_for_review integer NOT NULL,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    llm_calls_count integer NOT NULL,
    total_llm_latency_ms integer NOT NULL,
    model_version character varying(50)
);


--
-- Name: purge_failures; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.purge_failures (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    student_id uuid NOT NULL,
    bucket text NOT NULL,
    object_name text NOT NULL,
    error text NOT NULL,
    attempts integer DEFAULT 1 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    last_attempt_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: raw_graded_tests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.raw_graded_tests (
    id uuid NOT NULL,
    user_id uuid,
    rubric_id uuid,
    created_at timestamp with time zone NOT NULL,
    student_name character varying(255) NOT NULL,
    filename character varying(255),
    graded_json json NOT NULL,
    total_score double precision NOT NULL,
    total_possible double precision NOT NULL,
    percentage double precision NOT NULL,
    student_answers_json json,
    grading_model character varying(100),
    grading_duration_ms integer,
    transcription_model character varying(100),
    transcription_duration_ms integer
);


--
-- Name: raw_rubrics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.raw_rubrics (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    user_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    rubric_json jsonb NOT NULL,
    name character varying(255),
    description text,
    total_points double precision,
    source_filename character varying(255),
    extraction_model character varying(100),
    extraction_duration_ms integer
);


--
-- Name: rubric_extraction_jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rubric_extraction_jobs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    status character varying(20) DEFAULT 'queued'::character varying NOT NULL,
    source_gcs_uri text NOT NULL,
    source_filename character varying(255) NOT NULL,
    source_sha256 character(64) NOT NULL,
    request_params jsonb DEFAULT '{}'::jsonb NOT NULL,
    result_json jsonb,
    warnings jsonb DEFAULT '[]'::jsonb NOT NULL,
    errors jsonb DEFAULT '[]'::jsonb NOT NULL,
    requires_review boolean,
    prompt_version character varying(50),
    pipeline_version character varying(50),
    llm_model character varying(100),
    input_tokens integer,
    output_tokens integer,
    retry_count integer,
    finish_reason character varying(50),
    duration_ms integer,
    llm_config jsonb,
    progress_stage character varying(30),
    progress_detail text,
    error_message text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    started_at timestamp with time zone,
    finished_at timestamp with time zone,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT rubric_extraction_jobs_status_check CHECK (((status)::text = ANY (ARRAY[('queued'::character varying)::text, ('extracting'::character varying)::text, ('completed'::character varying)::text, ('failed'::character varying)::text]))),
    CONSTRAINT rubric_extraction_jobs_status_consistency CHECK (((((status)::text = 'queued'::text) AND (result_json IS NULL) AND (started_at IS NULL) AND (finished_at IS NULL)) OR (((status)::text = 'extracting'::text) AND (result_json IS NULL) AND (started_at IS NOT NULL) AND (finished_at IS NULL)) OR (((status)::text = 'completed'::text) AND (result_json IS NOT NULL) AND (finished_at IS NOT NULL)) OR (((status)::text = 'failed'::text) AND (error_message IS NOT NULL) AND (finished_at IS NOT NULL))))
);


--
-- Name: rubric_share_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rubric_share_history (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    rubric_id uuid NOT NULL,
    sender_user_id uuid,
    recipient_email character varying(255) NOT NULL,
    shared_at timestamp with time zone DEFAULT now() NOT NULL,
    accepted_at timestamp with time zone,
    revoked_at timestamp with time zone,
    share_token_id uuid
);


--
-- Name: rubric_share_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rubric_share_tokens (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    token character varying(64) NOT NULL,
    rubric_id uuid NOT NULL,
    sender_user_id uuid,
    recipient_email character varying(255) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    accepted_at timestamp with time zone,
    generated_pdf_gcs_path character varying(500),
    copied_rubric_id uuid
);


--
-- Name: rubric_shares; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rubric_shares (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    rubric_id uuid NOT NULL,
    owner_user_id uuid NOT NULL,
    shared_with_user_id uuid NOT NULL,
    permission public.share_permission DEFAULT 'view'::public.share_permission NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: rubrics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rubrics (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, now()),
    name character varying(255),
    description text,
    total_points double precision,
    user_id uuid,
    raw_rubric_id uuid,
    draft_json jsonb,
    contract_json jsonb,
    contract_version character varying(50),
    last_compiled_at timestamp with time zone,
    needs_recompilation boolean DEFAULT false,
    acknowledged_warnings jsonb DEFAULT '[]'::jsonb,
    compilation_attempts integer DEFAULT 0,
    legacy_rubric_json_backup jsonb,
    extraction_job_id uuid,
    subject text DEFAULT 'computer_science'::text NOT NULL
);


--
-- Name: COLUMN rubrics.draft_json; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.rubrics.draft_json IS 'Teacher-editable ExtractRubricResponse from ontology_types. Teachers review and edit this before compilation.';


--
-- Name: COLUMN rubrics.contract_json; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.rubrics.contract_json IS 'Frozen GradingRubricContract used by grading agent. Immutable after compilation. Closed-world semantics.';


--
-- Name: COLUMN rubrics.contract_version; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.rubrics.contract_version IS 'UUID version of the compiled contract. Increments on each successful compilation.';


--
-- Name: COLUMN rubrics.last_compiled_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.rubrics.last_compiled_at IS 'When the contract was last compiled. NULL if never compiled.';


--
-- Name: COLUMN rubrics.needs_recompilation; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.rubrics.needs_recompilation IS 'TRUE if draft_json was edited after last compilation. Blocks grading until recompiled.';


--
-- Name: COLUMN rubrics.acknowledged_warnings; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.rubrics.acknowledged_warnings IS 'Array of warning annotation IDs that teacher acknowledged during compilation.';


--
-- Name: COLUMN rubrics.compilation_attempts; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.rubrics.compilation_attempts IS 'Number of compilation attempts. High values (>3) indicate UX or validation issues.';


--
-- Name: schema_migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.schema_migrations (
    version character varying(10) NOT NULL,
    applied_at timestamp with time zone DEFAULT now() NOT NULL,
    note text
);


--
-- Name: TABLE schema_migrations; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.schema_migrations IS 'Applied-migration ledger. Each migration INSERTs its version as its LAST statement, so the row is a commit token: partial application leaves no row. Checked at boot against EXPECTED_MIGRATIONS in app/database.py.';


--
-- Name: schools; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.schools (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name text NOT NULL,
    city text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    ministry_symbol text
);


--
-- Name: students; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.students (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    full_name character varying(255) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE students; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.students IS 'Persistent identity for a learner. Per-teacher scoped. Per Phase 0c §1.';


--
-- Name: subject_matters; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.subject_matters (
    id integer NOT NULL,
    code character varying(50) NOT NULL,
    name_en character varying(100) NOT NULL,
    name_he character varying(100) NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: subject_matters_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.subject_matters_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: subject_matters_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.subject_matters_id_seq OWNED BY public.subject_matters.id;


--
-- Name: transcription_jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transcription_jobs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    batch_id uuid NOT NULL,
    rubric_id uuid NOT NULL,
    status character varying(20) DEFAULT 'queued'::character varying NOT NULL,
    source_gcs_object_path text NOT NULL,
    source_filename character varying(500),
    doc_priority integer DEFAULT 0 NOT NULL,
    transcription_id uuid,
    error_message text,
    net_verdict character varying(30),
    attempt_count integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    started_at timestamp with time zone,
    finished_at timestamp with time zone,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    client_file_id uuid,
    CONSTRAINT transcription_jobs_status_check CHECK (((status)::text = ANY (ARRAY[('queued'::character varying)::text, ('running'::character varying)::text, ('completed'::character varying)::text, ('failed'::character varying)::text]))),
    CONSTRAINT transcription_jobs_status_consistency CHECK (((((status)::text = ANY (ARRAY[('queued'::character varying)::text, ('running'::character varying)::text])) AND (finished_at IS NULL) AND (error_message IS NULL)) OR (((status)::text = 'completed'::text) AND (finished_at IS NOT NULL) AND (error_message IS NULL)) OR (((status)::text = 'failed'::text) AND (finished_at IS NOT NULL) AND (error_message IS NOT NULL))))
);


--
-- Name: transcriptions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transcriptions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    rubric_id uuid NOT NULL,
    student_id uuid,
    student_name character varying(255),
    gcs_uri character varying(500) NOT NULL,
    gcs_bucket character varying(255) NOT NULL,
    gcs_object_path character varying(500) NOT NULL,
    filename character varying(500),
    draft_json jsonb NOT NULL,
    contract_json jsonb,
    approved_at timestamp with time zone,
    status character varying(20) DEFAULT 'transcribed'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    batch_id uuid,
    review_json jsonb,
    CONSTRAINT transcriptions_approval_consistency CHECK (((((status)::text = 'transcribed'::text) AND (contract_json IS NULL) AND (approved_at IS NULL) AND (student_id IS NULL)) OR (((status)::text = 'approved'::text) AND (contract_json IS NOT NULL) AND (approved_at IS NOT NULL) AND (student_id IS NOT NULL)))),
    CONSTRAINT transcriptions_status_check CHECK (((status)::text = ANY (ARRAY[('transcribed'::character varying)::text, ('approved'::character varying)::text])))
);


--
-- Name: TABLE transcriptions; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.transcriptions IS 'Draft+Contract artifact for one student handwritten test. Per Phase 0c §4.';


--
-- Name: COLUMN transcriptions.draft_json; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.transcriptions.draft_json IS 'TranscriptionDraft Pydantic model. VLM output, immutable from INSERT onward.';


--
-- Name: COLUMN transcriptions.contract_json; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.transcriptions.contract_json IS 'TranscriptionContract Pydantic model. Teacher-approved answers. contract_version inside JSONB.';


--
-- Name: user_schools; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_schools (
    user_id uuid NOT NULL,
    school_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    "position" integer DEFAULT 0 NOT NULL
);


--
-- Name: user_subject_matters; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_subject_matters (
    user_id uuid NOT NULL,
    subject_matter_id integer NOT NULL
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    email character varying(255) NOT NULL,
    password_hash character varying(255),
    google_id character varying(255),
    full_name character varying(255) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    subscription_status public.subscription_status DEFAULT 'trial'::public.subscription_status NOT NULL,
    started_trial_at timestamp with time zone DEFAULT now(),
    started_pro_at timestamp with time zone,
    tranzila_customer_id character varying(255),
    tranzila_token character varying(255),
    tranzila_transaction_id character varying(255),
    card_mask character varying(10),
    last_payment_at timestamp with time zone,
    next_payment_at timestamp with time zone,
    school_id uuid,
    gender text,
    onboarding_completed_at timestamp with time zone,
    email_verified_at timestamp with time zone,
    next_exam_date date,
    next_exam_answered_at timestamp with time zone,
    next_exam_reask_email_sent_at timestamp with time zone,
    phone text,
    whatsapp_opt_in boolean DEFAULT false NOT NULL,
    guided_session_requested_at timestamp with time zone,
    CONSTRAINT users_gender_valid CHECK (((gender IS NULL) OR (gender = ANY (ARRAY['female'::text, 'male'::text, 'unspecified'::text]))))
);


--
-- Name: subject_matters id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.subject_matters ALTER COLUMN id SET DEFAULT nextval('public.subject_matters_id_seq'::regclass);


--
-- Name: auth_nonces auth_nonces_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_nonces
    ADD CONSTRAINT auth_nonces_pkey PRIMARY KEY (nonce_hash);


--
-- Name: class_memberships class_memberships_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.class_memberships
    ADD CONSTRAINT class_memberships_pkey PRIMARY KEY (class_id, student_id);


--
-- Name: classes classes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.classes
    ADD CONSTRAINT classes_pkey PRIMARY KEY (id);


--
-- Name: classes classes_unique_name_per_user; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.classes
    ADD CONSTRAINT classes_unique_name_per_user UNIQUE (user_id, name);


--
-- Name: email_verification_codes email_verification_codes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.email_verification_codes
    ADD CONSTRAINT email_verification_codes_pkey PRIMARY KEY (id);


--
-- Name: graded_test_pdfs graded_test_pdfs_graded_test_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.graded_test_pdfs
    ADD CONSTRAINT graded_test_pdfs_graded_test_id_key UNIQUE (graded_test_id);


--
-- Name: graded_test_pdfs graded_test_pdfs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.graded_test_pdfs
    ADD CONSTRAINT graded_test_pdfs_pkey PRIMARY KEY (id);


--
-- Name: graded_tests graded_tests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.graded_tests
    ADD CONSTRAINT graded_tests_pkey PRIMARY KEY (id);


--
-- Name: grading_batches grading_batches_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.grading_batches
    ADD CONSTRAINT grading_batches_pkey PRIMARY KEY (id);


--
-- Name: grading_plans grading_plans_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.grading_plans
    ADD CONSTRAINT grading_plans_pkey PRIMARY KEY (id);


--
-- Name: grading_sessions grading_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.grading_sessions
    ADD CONSTRAINT grading_sessions_pkey PRIMARY KEY (id);


--
-- Name: purge_failures purge_failures_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purge_failures
    ADD CONSTRAINT purge_failures_pkey PRIMARY KEY (id);


--
-- Name: raw_graded_tests raw_graded_tests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.raw_graded_tests
    ADD CONSTRAINT raw_graded_tests_pkey PRIMARY KEY (id);


--
-- Name: raw_rubrics raw_rubrics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.raw_rubrics
    ADD CONSTRAINT raw_rubrics_pkey PRIMARY KEY (id);


--
-- Name: rubric_extraction_jobs rubric_extraction_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rubric_extraction_jobs
    ADD CONSTRAINT rubric_extraction_jobs_pkey PRIMARY KEY (id);


--
-- Name: rubric_share_history rubric_share_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rubric_share_history
    ADD CONSTRAINT rubric_share_history_pkey PRIMARY KEY (id);


--
-- Name: rubric_share_tokens rubric_share_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rubric_share_tokens
    ADD CONSTRAINT rubric_share_tokens_pkey PRIMARY KEY (id);


--
-- Name: rubric_share_tokens rubric_share_tokens_token_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rubric_share_tokens
    ADD CONSTRAINT rubric_share_tokens_token_key UNIQUE (token);


--
-- Name: rubric_shares rubric_shares_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rubric_shares
    ADD CONSTRAINT rubric_shares_pkey PRIMARY KEY (id);


--
-- Name: rubric_shares rubric_shares_rubric_id_shared_with_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rubric_shares
    ADD CONSTRAINT rubric_shares_rubric_id_shared_with_user_id_key UNIQUE (rubric_id, shared_with_user_id);


--
-- Name: rubrics rubrics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rubrics
    ADD CONSTRAINT rubrics_pkey PRIMARY KEY (id);


--
-- Name: rubrics rubrics_raw_rubric_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rubrics
    ADD CONSTRAINT rubrics_raw_rubric_id_key UNIQUE (raw_rubric_id);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: schools schools_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schools
    ADD CONSTRAINT schools_pkey PRIMARY KEY (id);


--
-- Name: students students_id_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.students
    ADD CONSTRAINT students_id_user_id_key UNIQUE (id, user_id);


--
-- Name: students students_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.students
    ADD CONSTRAINT students_pkey PRIMARY KEY (id);


--
-- Name: students students_unique_name_per_user; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.students
    ADD CONSTRAINT students_unique_name_per_user UNIQUE (user_id, full_name);


--
-- Name: subject_matters subject_matters_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.subject_matters
    ADD CONSTRAINT subject_matters_code_key UNIQUE (code);


--
-- Name: subject_matters subject_matters_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.subject_matters
    ADD CONSTRAINT subject_matters_pkey PRIMARY KEY (id);


--
-- Name: transcription_jobs transcription_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transcription_jobs
    ADD CONSTRAINT transcription_jobs_pkey PRIMARY KEY (id);


--
-- Name: transcriptions transcriptions_id_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transcriptions
    ADD CONSTRAINT transcriptions_id_user_id_key UNIQUE (id, user_id);


--
-- Name: transcriptions transcriptions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transcriptions
    ADD CONSTRAINT transcriptions_pkey PRIMARY KEY (id);


--
-- Name: user_schools user_schools_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_schools
    ADD CONSTRAINT user_schools_pkey PRIMARY KEY (user_id, school_id);


--
-- Name: user_subject_matters user_subject_matters_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_subject_matters
    ADD CONSTRAINT user_subject_matters_pkey PRIMARY KEY (user_id, subject_matter_id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_google_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_google_id_key UNIQUE (google_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: idx_auth_nonces_expires_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_auth_nonces_expires_at ON public.auth_nonces USING btree (expires_at);


--
-- Name: idx_class_memberships_student; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_class_memberships_student ON public.class_memberships USING btree (student_id);


--
-- Name: idx_classes_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_classes_user ON public.classes USING btree (user_id);


--
-- Name: idx_email_codes_expires_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_email_codes_expires_at ON public.email_verification_codes USING btree (expires_at);


--
-- Name: idx_email_codes_one_active_per_user; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_email_codes_one_active_per_user ON public.email_verification_codes USING btree (user_id) WHERE (consumed_at IS NULL);


--
-- Name: idx_extraction_jobs_one_active_per_source; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_extraction_jobs_one_active_per_source ON public.rubric_extraction_jobs USING btree (user_id, source_sha256) WHERE ((status)::text = ANY (ARRAY[('queued'::character varying)::text, ('extracting'::character varying)::text]));


--
-- Name: idx_extraction_jobs_user_recent; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_extraction_jobs_user_recent ON public.rubric_extraction_jobs USING btree (user_id, created_at DESC);


--
-- Name: idx_graded_tests_batch; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_graded_tests_batch ON public.graded_tests USING btree (batch_id) WHERE (batch_id IS NOT NULL);


--
-- Name: idx_graded_tests_one_leaf_per_chain; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_graded_tests_one_leaf_per_chain ON public.graded_tests USING btree (transcription_id, rubric_id) WHERE (regraded_to_id IS NULL);


--
-- Name: idx_graded_tests_regraded_from; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_graded_tests_regraded_from ON public.graded_tests USING btree (regraded_from_id) WHERE (regraded_from_id IS NOT NULL);


--
-- Name: idx_graded_tests_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_graded_tests_status ON public.graded_tests USING btree (status);


--
-- Name: idx_graded_tests_transcription; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_graded_tests_transcription ON public.graded_tests USING btree (transcription_id);


--
-- Name: idx_graded_tests_user_rubric; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_graded_tests_user_rubric ON public.graded_tests USING btree (user_id, rubric_id);


--
-- Name: idx_graded_tests_user_student; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_graded_tests_user_student ON public.graded_tests USING btree (user_id, student_id);


--
-- Name: idx_grading_batches_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_grading_batches_user ON public.grading_batches USING btree (user_id);


--
-- Name: idx_grading_plans_one_live_per_contract; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_grading_plans_one_live_per_contract ON public.grading_plans USING btree (contract_sha256) WHERE (status = ANY (ARRAY['queued'::text, 'building'::text, 'ready'::text]));


--
-- Name: idx_grading_plans_rubric; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_grading_plans_rubric ON public.grading_plans USING btree (rubric_id, created_at DESC);


--
-- Name: idx_purge_failures_object; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_purge_failures_object ON public.purge_failures USING btree (bucket, object_name);


--
-- Name: idx_purge_failures_student; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_purge_failures_student ON public.purge_failures USING btree (student_id);


--
-- Name: idx_raw_rubrics_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_raw_rubrics_user_id ON public.raw_rubrics USING btree (user_id);


--
-- Name: idx_rubric_share_history_rubric_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rubric_share_history_rubric_id ON public.rubric_share_history USING btree (rubric_id);


--
-- Name: idx_rubric_share_tokens_rubric_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rubric_share_tokens_rubric_id ON public.rubric_share_tokens USING btree (rubric_id);


--
-- Name: idx_rubric_share_tokens_token; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rubric_share_tokens_token ON public.rubric_share_tokens USING btree (token);


--
-- Name: idx_rubric_shares_owner; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rubric_shares_owner ON public.rubric_shares USING btree (owner_user_id);


--
-- Name: idx_rubric_shares_rubric_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rubric_shares_rubric_id ON public.rubric_shares USING btree (rubric_id);


--
-- Name: idx_rubric_shares_shared_with; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rubric_shares_shared_with ON public.rubric_shares USING btree (shared_with_user_id);


--
-- Name: idx_rubrics_compilation_attempts; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rubrics_compilation_attempts ON public.rubrics USING btree (compilation_attempts) WHERE (compilation_attempts > 3);


--
-- Name: idx_rubrics_contract_version; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rubrics_contract_version ON public.rubrics USING btree (contract_version) WHERE (contract_version IS NOT NULL);


--
-- Name: idx_rubrics_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rubrics_created_at ON public.rubrics USING btree (created_at DESC);


--
-- Name: idx_rubrics_needs_recompilation; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rubrics_needs_recompilation ON public.rubrics USING btree (needs_recompilation) WHERE (needs_recompilation = true);


--
-- Name: idx_rubrics_subject; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rubrics_subject ON public.rubrics USING btree (subject);


--
-- Name: idx_rubrics_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rubrics_user_id ON public.rubrics USING btree (user_id);


--
-- Name: idx_schools_ministry_symbol; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_schools_ministry_symbol ON public.schools USING btree (ministry_symbol) WHERE (ministry_symbol IS NOT NULL);


--
-- Name: idx_schools_normalized_name_symbolless; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_schools_normalized_name_symbolless ON public.schools USING btree (lower(regexp_replace(btrim(name), '\s+'::text, ' '::text, 'g'::text))) WHERE (ministry_symbol IS NULL);


--
-- Name: idx_students_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_students_user ON public.students USING btree (user_id);


--
-- Name: idx_transcription_jobs_batch_client_file; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_transcription_jobs_batch_client_file ON public.transcription_jobs USING btree (batch_id, client_file_id) WHERE (client_file_id IS NOT NULL);


--
-- Name: idx_transcription_jobs_batch_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_transcription_jobs_batch_status ON public.transcription_jobs USING btree (batch_id, status);


--
-- Name: idx_transcriptions_batch; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_transcriptions_batch ON public.transcriptions USING btree (batch_id) WHERE (batch_id IS NOT NULL);


--
-- Name: idx_transcriptions_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_transcriptions_status ON public.transcriptions USING btree (status);


--
-- Name: idx_transcriptions_user_rubric; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_transcriptions_user_rubric ON public.transcriptions USING btree (user_id, rubric_id);


--
-- Name: idx_transcriptions_user_student; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_transcriptions_user_student ON public.transcriptions USING btree (user_id, student_id) WHERE (student_id IS NOT NULL);


--
-- Name: idx_user_schools_school_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_schools_school_id ON public.user_schools USING btree (school_id);


--
-- Name: idx_users_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_email ON public.users USING btree (email);


--
-- Name: idx_users_google_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_google_id ON public.users USING btree (google_id);


--
-- Name: idx_users_reask_candidates; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_reask_candidates ON public.users USING btree (next_exam_answered_at) WHERE (next_exam_date IS NULL);


--
-- Name: idx_users_school_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_school_id ON public.users USING btree (school_id) WHERE (school_id IS NOT NULL);


--
-- Name: ix_grading_batches_rubric_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_grading_batches_rubric_id ON public.grading_batches USING btree (rubric_id);


--
-- Name: ix_grading_batches_teacher_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_grading_batches_teacher_id ON public.grading_batches USING btree (user_id);


--
-- Name: ix_grading_sessions_batch_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_grading_sessions_batch_id ON public.grading_sessions USING btree (batch_id);


--
-- Name: ix_grading_sessions_contract_version; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_grading_sessions_contract_version ON public.grading_sessions USING btree (contract_version);


--
-- Name: ix_grading_sessions_rubric_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_grading_sessions_rubric_id ON public.grading_sessions USING btree (rubric_id);


--
-- Name: ix_grading_sessions_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_grading_sessions_status ON public.grading_sessions USING btree (status);


--
-- Name: ix_grading_sessions_teacher_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_grading_sessions_teacher_id ON public.grading_sessions USING btree (teacher_id);


--
-- Name: rubrics update_rubrics_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_rubrics_updated_at BEFORE UPDATE ON public.rubrics FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: class_memberships class_memberships_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.class_memberships
    ADD CONSTRAINT class_memberships_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(id) ON DELETE CASCADE;


--
-- Name: class_memberships class_memberships_student_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.class_memberships
    ADD CONSTRAINT class_memberships_student_id_fkey FOREIGN KEY (student_id) REFERENCES public.students(id) ON DELETE CASCADE;


--
-- Name: classes classes_subject_matter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.classes
    ADD CONSTRAINT classes_subject_matter_id_fkey FOREIGN KEY (subject_matter_id) REFERENCES public.subject_matters(id) ON DELETE SET NULL;


--
-- Name: classes classes_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.classes
    ADD CONSTRAINT classes_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: email_verification_codes email_verification_codes_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.email_verification_codes
    ADD CONSTRAINT email_verification_codes_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: graded_test_pdfs graded_test_pdfs_graded_test_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.graded_test_pdfs
    ADD CONSTRAINT graded_test_pdfs_graded_test_id_fkey FOREIGN KEY (graded_test_id) REFERENCES public.graded_tests(id);


--
-- Name: graded_test_pdfs graded_test_pdfs_rubric_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.graded_test_pdfs
    ADD CONSTRAINT graded_test_pdfs_rubric_id_fkey FOREIGN KEY (rubric_id) REFERENCES public.rubrics(id);


--
-- Name: graded_tests graded_tests_batch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.graded_tests
    ADD CONSTRAINT graded_tests_batch_id_fkey FOREIGN KEY (batch_id) REFERENCES public.grading_batches(id);


--
-- Name: graded_tests graded_tests_regraded_from_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.graded_tests
    ADD CONSTRAINT graded_tests_regraded_from_id_fkey FOREIGN KEY (regraded_from_id) REFERENCES public.graded_tests(id);


--
-- Name: graded_tests graded_tests_regraded_to_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.graded_tests
    ADD CONSTRAINT graded_tests_regraded_to_id_fkey FOREIGN KEY (regraded_to_id) REFERENCES public.graded_tests(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: graded_tests graded_tests_rubric_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.graded_tests
    ADD CONSTRAINT graded_tests_rubric_id_fkey FOREIGN KEY (rubric_id) REFERENCES public.rubrics(id);


--
-- Name: graded_tests graded_tests_student_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.graded_tests
    ADD CONSTRAINT graded_tests_student_id_fkey FOREIGN KEY (student_id) REFERENCES public.students(id);


--
-- Name: graded_tests graded_tests_student_tenant_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.graded_tests
    ADD CONSTRAINT graded_tests_student_tenant_fkey FOREIGN KEY (student_id, user_id) REFERENCES public.students(id, user_id);


--
-- Name: graded_tests graded_tests_transcription_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.graded_tests
    ADD CONSTRAINT graded_tests_transcription_id_fkey FOREIGN KEY (transcription_id) REFERENCES public.transcriptions(id);


--
-- Name: graded_tests graded_tests_transcription_tenant_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.graded_tests
    ADD CONSTRAINT graded_tests_transcription_tenant_fkey FOREIGN KEY (transcription_id, user_id) REFERENCES public.transcriptions(id, user_id);


--
-- Name: graded_tests graded_tests_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.graded_tests
    ADD CONSTRAINT graded_tests_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: grading_batches grading_batches_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.grading_batches
    ADD CONSTRAINT grading_batches_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(id) ON DELETE SET NULL;


--
-- Name: grading_batches grading_batches_rubric_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.grading_batches
    ADD CONSTRAINT grading_batches_rubric_id_fkey FOREIGN KEY (rubric_id) REFERENCES public.rubrics(id) ON DELETE CASCADE;


--
-- Name: grading_batches grading_batches_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.grading_batches
    ADD CONSTRAINT grading_batches_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: grading_plans grading_plans_rubric_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.grading_plans
    ADD CONSTRAINT grading_plans_rubric_id_fkey FOREIGN KEY (rubric_id) REFERENCES public.rubrics(id) ON DELETE SET NULL;


--
-- Name: grading_sessions grading_sessions_batch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.grading_sessions
    ADD CONSTRAINT grading_sessions_batch_id_fkey FOREIGN KEY (batch_id) REFERENCES public.grading_batches(id) ON DELETE SET NULL;


--
-- Name: grading_sessions grading_sessions_rubric_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.grading_sessions
    ADD CONSTRAINT grading_sessions_rubric_id_fkey FOREIGN KEY (rubric_id) REFERENCES public.rubrics(id) ON DELETE CASCADE;


--
-- Name: grading_sessions grading_sessions_teacher_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.grading_sessions
    ADD CONSTRAINT grading_sessions_teacher_id_fkey FOREIGN KEY (teacher_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: purge_failures purge_failures_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.purge_failures
    ADD CONSTRAINT purge_failures_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: raw_graded_tests raw_graded_tests_rubric_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.raw_graded_tests
    ADD CONSTRAINT raw_graded_tests_rubric_id_fkey FOREIGN KEY (rubric_id) REFERENCES public.rubrics(id) ON DELETE SET NULL;


--
-- Name: raw_graded_tests raw_graded_tests_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.raw_graded_tests
    ADD CONSTRAINT raw_graded_tests_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: raw_rubrics raw_rubrics_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.raw_rubrics
    ADD CONSTRAINT raw_rubrics_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: rubric_extraction_jobs rubric_extraction_jobs_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rubric_extraction_jobs
    ADD CONSTRAINT rubric_extraction_jobs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: rubric_share_history rubric_share_history_rubric_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rubric_share_history
    ADD CONSTRAINT rubric_share_history_rubric_id_fkey FOREIGN KEY (rubric_id) REFERENCES public.rubrics(id) ON DELETE CASCADE;


--
-- Name: rubric_share_history rubric_share_history_sender_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rubric_share_history
    ADD CONSTRAINT rubric_share_history_sender_user_id_fkey FOREIGN KEY (sender_user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: rubric_share_history rubric_share_history_share_token_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rubric_share_history
    ADD CONSTRAINT rubric_share_history_share_token_id_fkey FOREIGN KEY (share_token_id) REFERENCES public.rubric_share_tokens(id) ON DELETE SET NULL;


--
-- Name: rubric_share_tokens rubric_share_tokens_copied_rubric_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rubric_share_tokens
    ADD CONSTRAINT rubric_share_tokens_copied_rubric_id_fkey FOREIGN KEY (copied_rubric_id) REFERENCES public.rubrics(id) ON DELETE SET NULL;


--
-- Name: rubric_share_tokens rubric_share_tokens_rubric_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rubric_share_tokens
    ADD CONSTRAINT rubric_share_tokens_rubric_id_fkey FOREIGN KEY (rubric_id) REFERENCES public.rubrics(id) ON DELETE CASCADE;


--
-- Name: rubric_share_tokens rubric_share_tokens_sender_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rubric_share_tokens
    ADD CONSTRAINT rubric_share_tokens_sender_user_id_fkey FOREIGN KEY (sender_user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: rubric_shares rubric_shares_owner_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rubric_shares
    ADD CONSTRAINT rubric_shares_owner_user_id_fkey FOREIGN KEY (owner_user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: rubric_shares rubric_shares_rubric_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rubric_shares
    ADD CONSTRAINT rubric_shares_rubric_id_fkey FOREIGN KEY (rubric_id) REFERENCES public.rubrics(id) ON DELETE CASCADE;


--
-- Name: rubric_shares rubric_shares_shared_with_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rubric_shares
    ADD CONSTRAINT rubric_shares_shared_with_user_id_fkey FOREIGN KEY (shared_with_user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: rubrics rubrics_extraction_job_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rubrics
    ADD CONSTRAINT rubrics_extraction_job_id_fkey FOREIGN KEY (extraction_job_id) REFERENCES public.rubric_extraction_jobs(id) ON DELETE SET NULL;


--
-- Name: rubrics rubrics_raw_rubric_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rubrics
    ADD CONSTRAINT rubrics_raw_rubric_id_fkey FOREIGN KEY (raw_rubric_id) REFERENCES public.raw_rubrics(id) ON DELETE SET NULL;


--
-- Name: rubrics rubrics_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rubrics
    ADD CONSTRAINT rubrics_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: students students_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.students
    ADD CONSTRAINT students_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: transcription_jobs transcription_jobs_batch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transcription_jobs
    ADD CONSTRAINT transcription_jobs_batch_id_fkey FOREIGN KEY (batch_id) REFERENCES public.grading_batches(id);


--
-- Name: transcription_jobs transcription_jobs_rubric_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transcription_jobs
    ADD CONSTRAINT transcription_jobs_rubric_id_fkey FOREIGN KEY (rubric_id) REFERENCES public.rubrics(id);


--
-- Name: transcription_jobs transcription_jobs_transcription_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transcription_jobs
    ADD CONSTRAINT transcription_jobs_transcription_id_fkey FOREIGN KEY (transcription_id) REFERENCES public.transcriptions(id);


--
-- Name: transcription_jobs transcription_jobs_transcription_tenant_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transcription_jobs
    ADD CONSTRAINT transcription_jobs_transcription_tenant_fkey FOREIGN KEY (transcription_id, user_id) REFERENCES public.transcriptions(id, user_id);


--
-- Name: transcription_jobs transcription_jobs_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transcription_jobs
    ADD CONSTRAINT transcription_jobs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: transcriptions transcriptions_batch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transcriptions
    ADD CONSTRAINT transcriptions_batch_id_fkey FOREIGN KEY (batch_id) REFERENCES public.grading_batches(id);


--
-- Name: transcriptions transcriptions_rubric_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transcriptions
    ADD CONSTRAINT transcriptions_rubric_id_fkey FOREIGN KEY (rubric_id) REFERENCES public.rubrics(id);


--
-- Name: transcriptions transcriptions_student_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transcriptions
    ADD CONSTRAINT transcriptions_student_id_fkey FOREIGN KEY (student_id) REFERENCES public.students(id);


--
-- Name: transcriptions transcriptions_student_tenant_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transcriptions
    ADD CONSTRAINT transcriptions_student_tenant_fkey FOREIGN KEY (student_id, user_id) REFERENCES public.students(id, user_id);


--
-- Name: transcriptions transcriptions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transcriptions
    ADD CONSTRAINT transcriptions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: user_schools user_schools_school_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_schools
    ADD CONSTRAINT user_schools_school_id_fkey FOREIGN KEY (school_id) REFERENCES public.schools(id) ON DELETE CASCADE;


--
-- Name: user_schools user_schools_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_schools
    ADD CONSTRAINT user_schools_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_subject_matters user_subject_matters_subject_matter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_subject_matters
    ADD CONSTRAINT user_subject_matters_subject_matter_id_fkey FOREIGN KEY (subject_matter_id) REFERENCES public.subject_matters(id) ON DELETE CASCADE;


--
-- Name: user_subject_matters user_subject_matters_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_subject_matters
    ADD CONSTRAINT user_subject_matters_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: users users_school_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_school_id_fkey FOREIGN KEY (school_id) REFERENCES public.schools(id);


--
-- Name: auth_nonces; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.auth_nonces ENABLE ROW LEVEL SECURITY;

--
-- Name: class_memberships; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.class_memberships ENABLE ROW LEVEL SECURITY;

--
-- Name: classes; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.classes ENABLE ROW LEVEL SECURITY;

--
-- Name: email_verification_codes; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.email_verification_codes ENABLE ROW LEVEL SECURITY;

--
-- Name: graded_test_pdfs; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.graded_test_pdfs ENABLE ROW LEVEL SECURITY;

--
-- Name: graded_tests; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.graded_tests ENABLE ROW LEVEL SECURITY;

--
-- Name: grading_batches; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.grading_batches ENABLE ROW LEVEL SECURITY;

--
-- Name: grading_plans; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.grading_plans ENABLE ROW LEVEL SECURITY;

--
-- Name: grading_sessions; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.grading_sessions ENABLE ROW LEVEL SECURITY;

--
-- Name: purge_failures; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.purge_failures ENABLE ROW LEVEL SECURITY;

--
-- Name: raw_graded_tests; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.raw_graded_tests ENABLE ROW LEVEL SECURITY;

--
-- Name: raw_rubrics; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.raw_rubrics ENABLE ROW LEVEL SECURITY;

--
-- Name: rubric_extraction_jobs; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.rubric_extraction_jobs ENABLE ROW LEVEL SECURITY;

--
-- Name: rubric_share_history; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.rubric_share_history ENABLE ROW LEVEL SECURITY;

--
-- Name: rubric_share_tokens; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.rubric_share_tokens ENABLE ROW LEVEL SECURITY;

--
-- Name: rubric_shares; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.rubric_shares ENABLE ROW LEVEL SECURITY;

--
-- Name: rubrics; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.rubrics ENABLE ROW LEVEL SECURITY;

--
-- Name: schema_migrations; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.schema_migrations ENABLE ROW LEVEL SECURITY;

--
-- Name: schools; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.schools ENABLE ROW LEVEL SECURITY;

--
-- Name: students; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.students ENABLE ROW LEVEL SECURITY;

--
-- Name: subject_matters; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.subject_matters ENABLE ROW LEVEL SECURITY;

--
-- Name: transcription_jobs; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.transcription_jobs ENABLE ROW LEVEL SECURITY;

--
-- Name: transcriptions; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.transcriptions ENABLE ROW LEVEL SECURITY;

--
-- Name: user_schools; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.user_schools ENABLE ROW LEVEL SECURITY;

--
-- Name: user_subject_matters; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.user_subject_matters ENABLE ROW LEVEL SECURITY;

--
-- Name: users; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

--
-- PostgreSQL database dump complete
--


