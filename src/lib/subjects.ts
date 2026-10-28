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

/**
 * The CAPABILITY that changes how an answer is drawn (MATH_RENDERING_PLAN §4, OD-M1):
 * the client mirror of the backend profile's `math_notation` modality. Surfaces ask THIS,
 * never `subject === 'mathematics'` — a future subject with formulas (physics) turns it on
 * here and every surface follows.
 *
 * It says "spans MAY be present", not "they are": a draft written under the linear
 * fragment has no `\(` and renders exactly as prose did.
 */
const MATH_NOTATION: Readonly<Record<SubjectKey, boolean>> = {
  computer_science: false,
  english: false,
  mathematics: true,
};

export function hasMathNotation(subject?: string | null): boolean {
  return isSubjectKey(subject) && MATH_NOTATION[subject];
}
