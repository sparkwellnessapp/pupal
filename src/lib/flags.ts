/**
 * Release flags. Small, documented, greppable.
 *
 * D-1 (PR-5 Sprint 2): the DOCUMENT MIRROR (RubricDocument) replaces RubricEditor
 * as the rubric-review surface. There is NO PDF-rubric flow (upload hard-rejects
 * non-DOCX), so this is a plain boolean kill-switch — NOT a `sourceType` guard,
 * which would defend an unreachable branch and teach a false fact. RubricEditor
 * stays in-tree as the rollback target; flip this to `false` to revert a release.
 */
export const USE_DOCUMENT_MIRROR = true;

/**
 * E1 (closeout, owner-ruled) — the grading lane is SILENT until grading is
 * proven to run end-to-end.
 *
 * The mechanism, verified in code: accepting a transcription inserts a pending
 * `graded_tests` row and enqueues a real grading task. That path is fully
 * wired — the rows are NOT "created and never processed" by design, and
 * deleting the insert would break the accept contract and the revision-retry
 * chain (a P1-era change, correctly out of scope in the last stretch). What is
 * true is narrower and worse: the run has never been verified live in batch,
 * an enqueue failure is swallowed by design, and a pending row is reaped to
 * `failed` after ~90 minutes — so the lane could promise "ויוי בודקת" over work
 * that had already died.
 *
 * Until grading is proven, the lane renders NOTHING regardless of the counts.
 * The component, its copy and its zero-guard all stay — flip this to true and
 * it returns with real numbers.
 */
export const SHOW_GRADING_LANE = false;
