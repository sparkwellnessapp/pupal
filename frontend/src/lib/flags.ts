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
