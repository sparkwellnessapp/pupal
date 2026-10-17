-- grader-v6 — the production leg (owner rulings 2026-10-17 §10).
--
-- READ-ONLY. One statement, one cell: run it in the Supabase SQL editor (production,
-- ngkqawsyqqbhqthgdkpk) and paste the cell back. It writes nothing and locks nothing.
--
-- What it compares: the FIRST real v6 batch (the earliest batch holding an approved
-- v6 contract) against every v5 batch already in production. Only SIGNED work counts:
-- approved leaf rows (one per chain, RGC-1) of batches, excluding the purged test
-- domain. Criteria = terminal outcomes of COUNTED scopes (an unchosen "choose k of N"
-- member was never owed, so it is neither a criterion she reviewed nor an override).
--
-- Definitions (decided — pending owner veto):
--   override        a criterion whose FINAL points differ from Vivi's. The same
--                   definition on both sides: v5's own `was_overridden` IS this, while
--                   v6's flag is wider (it also marks a criterion whose check she
--                   re-picked to the same total), so v6's flag is reported beside it as
--                   `touched` and never mixed into the comparison.
--   time-to-sign    approved_at − opened_at per test. `opened_at` is the existing
--                   instrumentation (PR-G8: stamped once, on her first open); nothing
--                   finer exists. A test opened one evening and signed the next reads
--                   long, so the median and p75 are reported, never the mean.
--   K1 behaviour    Vivi awarded > 0 and she set 0 — the production face of the eval's
--                   K1 (GT-ZERO → AI-ZERO). Any such row is reported the same day.
--   quote status    the criterion's primary quote as the validator judged it at grade
--                   time (exact / fuzzy / not_found …); v6 adds each changed check's own.
WITH leaf AS (
    SELECT gt.id, gt.batch_id, gt.created_at, gt.opened_at, gt.approved_at,
           gt.contract_json AS c,
           CASE WHEN jsonb_typeof(gt.contract_json -> 'v6') = 'object' THEN 'v6'
                WHEN gt.contract_json ->> 'prompt_version' LIKE 'grader-v5%' THEN 'v5'
           END AS arch
    FROM graded_tests gt
    JOIN users u ON u.id = gt.user_id
    WHERE gt.status = 'approved'
      AND gt.regraded_to_id IS NULL
      AND gt.batch_id IS NOT NULL
      AND u.email NOT LIKE '%@s2test.com'
),
first_v6 AS (
    SELECT batch_id FROM leaf WHERE arch = 'v6'
    GROUP BY batch_id ORDER BY min(created_at) LIMIT 1
),
cohort AS (
    SELECT l.*,
           CASE WHEN l.batch_id = (SELECT batch_id FROM first_v6) THEN 'v6_first_batch'
                WHEN l.arch = 'v5' THEN 'v5_batches'
           END AS cohort
    FROM leaf l
),
term AS (
    SELECT co.cohort, co.id AS test_id, co.batch_id,
           t ->> 'terminal_id' AS terminal_id,
           t ->> 'description' AS description,
           (t ->> 'points_possible')::numeric AS possible,
           (t ->> 'ai_points_awarded')::numeric AS ai,
           (t ->> 'final_points_awarded')::numeric AS final,
           COALESCE((t ->> 'was_overridden')::boolean, false) AS flagged,
           t -> 'ai_evidence_quote' ->> 'validation_status' AS quote_status,
           t ->> 'teacher_comment' AS comment
    FROM cohort co
    CROSS JOIN LATERAL jsonb_array_elements(co.c -> 'scope_outcomes') s
    CROSS JOIN LATERAL jsonb_array_elements(s -> 'terminal_outcomes') t
    WHERE co.cohort IS NOT NULL
      AND COALESCE((s ->> 'counted_in_total')::boolean, true)
),
per_test AS (
    SELECT cohort, test_id, batch_id,
           count(*) AS criteria,
           count(*) FILTER (WHERE final <> ai) AS overridden,
           count(*) FILTER (WHERE flagged) AS touched
    FROM term GROUP BY cohort, test_id, batch_id
),
signing AS (
    SELECT cohort, EXTRACT(EPOCH FROM (approved_at - opened_at)) / 60.0 AS minutes
    FROM cohort
    WHERE cohort IS NOT NULL AND opened_at IS NOT NULL AND approved_at >= opened_at
),
summary AS (
    SELECT p.cohort,
           count(*) AS tests,
           count(DISTINCT p.batch_id) AS batches,
           sum(p.criteria) AS criteria,
           sum(p.overridden) AS criteria_overridden,
           round(avg(p.overridden), 2) AS overrides_per_test,
           round(100.0 * sum(p.overridden) / NULLIF(sum(p.criteria), 0), 1) AS pct_criteria_overridden,
           round(100.0 * count(*) FILTER (WHERE p.overridden = 0) / count(*), 1) AS pct_tests_signed_unedited,
           sum(p.touched) AS touched,
           (SELECT count(*) FROM signing s WHERE s.cohort = p.cohort) AS timed_tests,
           (SELECT round(percentile_cont(0.5) WITHIN GROUP (ORDER BY minutes)::numeric, 1)
              FROM signing s WHERE s.cohort = p.cohort) AS median_min_to_sign,
           (SELECT round(percentile_cont(0.75) WITHIN GROUP (ORDER BY minutes)::numeric, 1)
              FROM signing s WHERE s.cohort = p.cohort) AS p75_min_to_sign,
           (SELECT count(*) FROM term x WHERE x.cohort = p.cohort AND x.ai > 0 AND x.final = 0)
               AS k1_behaviour_overrides
    FROM per_test p GROUP BY p.cohort
),
v6_check AS (                                   -- the checks she changed, per criterion
    SELECT co.id AS test_id, k ->> 'priced_terminal_id' AS terminal_id,
           jsonb_agg(jsonb_build_object(
               'check', k ->> 'check_id',
               'what', k ->> 'description_he',
               'vivi_option', k ->> 'model_option_id',
               'her_option', k ->> 'effective_option_id',
               'her_label', k ->> 'effective_label_he',
               'quote_status', k ->> 'quote_status') ORDER BY k ->> 'check_id') AS checks
    FROM cohort co
    CROSS JOIN LATERAL jsonb_array_elements(co.c -> 'v6' -> 'checks') k
    WHERE co.cohort = 'v6_first_batch' AND (k ->> 'was_overridden')::boolean
    GROUP BY co.id, k ->> 'priced_terminal_id'
)
SELECT jsonb_pretty(jsonb_build_object(
    'first_v6_batch', (SELECT batch_id FROM first_v6),
    'summary', (SELECT jsonb_agg(to_jsonb(s) ORDER BY s.cohort) FROM summary s),
    'v6_overrides', (
        SELECT jsonb_agg(jsonb_build_object(
                   'test', t.test_id,
                   'criterion', t.terminal_id,
                   'text', left(t.description, 120),
                   'vivi_to_her', concat(t.ai, ' → ', t.final, ' / ', t.possible),
                   'k1_behaviour', (t.ai > 0 AND t.final = 0),
                   'quote_status', t.quote_status,
                   'comment', t.comment,
                   'checks_changed', vc.checks)
               ORDER BY (t.ai > 0 AND t.final = 0) DESC, t.test_id, t.terminal_id)
        FROM term t
        LEFT JOIN v6_check vc ON vc.test_id = t.test_id AND vc.terminal_id = t.terminal_id
        WHERE t.cohort = 'v6_first_batch' AND t.final <> t.ai)
)) AS v6_production_leg;
