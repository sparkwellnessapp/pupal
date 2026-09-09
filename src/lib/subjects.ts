/**
 * Subject keys — the client mirror of the backend registry (`app/subjects`).
 *
 * The keys are the seeded `subject_matters.code` values the onboarding picker
 * stores, and the ONLY values the extraction-job submit accepts (422 otherwise).
 * Labels come from the API (`GET /users/subject-matters`, `name_he`) wherever a
 * list is rendered; this file is the type + the fallback labels for a select
 * rendered before that list has loaded.
 *
 * Adding a subject: add it to the backend registry first; then here. There is
 * no subject-specific branch anywhere in shared components (CLAUDE.md §3.3) —
 * only this key and what the backend says about it.
 */
export const SUBJECT_KEYS = ['computer_science', 'english', 'mathematics'] as const;
export type SubjectKey = (typeof SUBJECT_KEYS)[number];

export const SUBJECT_LABEL_HE: Record<SubjectKey, string> = {
  computer_science: 'מדעי המחשב',
  english: 'אנגלית',
  mathematics: 'מתמטיקה',
};

export function isSubjectKey(v: unknown): v is SubjectKey {
  return typeof v === 'string' && (SUBJECT_KEYS as readonly string[]).includes(v);
}
