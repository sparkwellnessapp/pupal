/**
 * Hydration / Dehydration for rubric types.
 *
 * Hydration  (backend → frontend): string point values → number
 * Dehydration (frontend → backend): number point values → string
 *
 * These functions are the ONLY place numeric coercion happens.
 * Frontend state always stores numbers; the wire format always uses strings.
 *
 * Design rules:
 *  - NO type casts (`as`). Every field is assigned explicitly.
 *  - NO format sniffing (no `criterion_description || description` fallbacks).
 *  - safeParseFloat is the ONLY coercion utility.
 *
 * TWO TYPE FAMILIES, BY DESIGN (PR-4 finding 3). This codec sits between them:
 *   - the WIRE family (string points) — `QuestionOntology`/`SubQuestion`/… here,
 *     and, since PR-4, the codegen'd `api-types.ts` (`components['schemas']['Question']`)
 *     which is the source of truth for `api.ts`'s wire layer;
 *   - the EDITOR family (number points, narrower unions like the `question_type`
 *     literal set) — `RubricQuestion`/… in `types/rubric.ts`.
 * They are NOT interchangeable: the generated wire `Question` is deliberately WIDER
 * (`question_type?: string`, opaque `skill_targets`), so typing these signatures
 * against it would only LOSEN the editor's types. The seam is therefore guarded not
 * by the compiler — TS never errors on IGNORING a wire field, so a silent drop is a
 * type-clean bug — but by the GOLDEN ROUND-TRIP SUITE (rubric-transform.test.ts):
 * `dehydrate(hydrate(x)) ≡ x` over the five benchmarks is the load-bearing check
 * that every wire field survives. That is the division of labor; keep it.
 *
 * @see types/rubric.ts — display-ready types (numbers)
 * @see ontology-types.ts — wire types (strings)
 * @see lib/api-types.ts — codegen'd wire types (PR-4); the drift check pins them
 * @see rubric-transform.test.ts — the golden round-trip suite (the real guard)
 */

import type {
    RubricQuestion,
    RubricSubQuestion,
    RubricCriterion,
    RubricSubCriterion,
    ProposalSet,
    ProposedCriterion,
    EnhancedPointEntry,
} from '@/types/rubric';
import type {
    QuestionOntology,
    CriterionOntology,
    SubQuestion,
} from '@/lib/ontology-types';

// ─────────────────────────────────────────────────────────
// THE ONLY COERCION UTILITY
// ─────────────────────────────────────────────────────────

/**
 * Safely parse any backend value to a number.
 * Handles string (Decimal serialization), number, undefined, null.
 * Returns 0 for garbage input. This is the ONLY numeric coercion
 * function in the codebase. Do not inline parseFloat() elsewhere.
 */
export function safeParseFloat(value: string | number | undefined | null): number {
    if (value === undefined || value === null) return 0;
    const num = typeof value === 'number' ? value : parseFloat(value);
    return isNaN(num) ? 0 : num;
}

// ─────────────────────────────────────────────────────────
// OPAQUE CARRY (B-11) — the codec is now a TOTAL, DISJOINT partition.
//
// Every wire key on a node is either MODELED (read/written by name below) or
// CARRIED (moved verbatim through `_carry`). The two sets are disjoint by the
// MODELED_*_KEYS manifests, so a modeled key can never appear in `_carry` and a
// re-emit can never double-write. This is what makes an untouched open→save a
// structural identity even for pipeline metadata (and future backend fields) the
// editor never touches. Stripping those was the B-11 corruption path.
//
// The lone intentional exception is `proposals` — ephemeral UI state that lives
// between extraction and teacher accept/reject. It is MODELED (so it is excluded
// from `_carry`) but deliberately NOT re-emitted by dehydrate, so it never
// persists. This is the one documented non-identity in the round-trip.
// ─────────────────────────────────────────────────────────

// A key is MODELED (emitted by name by dehydrate) iff the codec TRANSFORMS it
// (points ↔ string, criteria/sub_questions/sub_criteria recursion) or the editor
// EDITS it (text, title, example_solution, …). Non-editable extraction metadata
// (trace_tables, context_tables, code_blocks, extraction_status/error, notes,
// extraction_confidence, evaluation_guidance) is CARRIED — it round-trips through
// `_carry` untouched, and since nothing edits it there is no drift. If a metadata
// field ever becomes editable, promote it to a MODELED set + emit it by name.
//
// `proposals` is MODELED so it is excluded from `_carry`, but is intentionally NOT
// re-emitted (ephemeral) — the one documented non-identity.
const MODELED_QUESTION_KEYS: ReadonlySet<string> = new Set([
    'question_id', 'question_type', 'question_text', 'total_points',
    'allow_multiple_valid_forms', 'skill_targets', 'requirements',
    'criteria', 'sub_questions', 'example_solution', 'proposals',
]);

const MODELED_SUBQUESTION_KEYS: ReadonlySet<string> = new Set([
    'sub_question_id', 'index', 'title', 'text', 'points',
    'criteria', 'sub_questions', 'example_solution', 'proposals',
]);

const MODELED_CRITERION_KEYS: ReadonlySet<string> = new Set([
    'criterion_id', 'index', 'description', 'points',
    'skill_targets', 'requirements', 'sub_criteria',
]);

const MODELED_SUBCRITERION_KEYS: ReadonlySet<string> = new Set([
    'sub_criterion_id', 'index', 'description', 'points',
]);

/** Wire fields NOT modeled by name → the carry bag. `undefined` when nothing is left over. */
function carryOf(
    raw: Record<string, unknown>,
    modeled: ReadonlySet<string>,
): Record<string, unknown> | undefined {
    const carry: Record<string, unknown> = {};
    for (const key of Object.keys(raw)) {
        if (!modeled.has(key)) carry[key] = raw[key];
    }
    return Object.keys(carry).length > 0 ? carry : undefined;
}

/**
 * Re-emit the carry bag under the modeled fields. Carry spreads FIRST so a
 * modeled field always wins (belt-and-suspenders — they are disjoint anyway).
 * This is the single cast the opaque-carry mechanism requires; it is confined
 * here rather than sprinkled through every dehydrate function.
 */
function withCarry<T extends object>(modeled: T, carry?: Record<string, unknown>): T {
    return (carry ? { ...carry, ...modeled } : modeled) as T;
}

// ─────────────────────────────────────────────────────────
// HYDRATION: Backend → Frontend (string → number)
// Called ONCE when data arrives from backend.
// ─────────────────────────────────────────────────────────

export function hydrateQuestions(questions: QuestionOntology[]): RubricQuestion[] {
    return (questions || []).map(hydrateQuestion);
}

function hydrateQuestion(q: QuestionOntology): RubricQuestion {
    // `raw` provides access to fields present on the wire JSON but not declared
    // in the QuestionOntology interface (code_blocks, extraction_status, etc.).
    // Double-cast through `unknown` is the standard TypeScript escape hatch.
    const raw = q as unknown as Record<string, unknown>;

    return {
        question_id: q.question_id,
        question_type: q.question_type,
        question_text: q.question_text,
        total_points: safeParseFloat(q.total_points),
        allow_multiple_valid_forms: q.allow_multiple_valid_forms,
        skill_targets: q.skill_targets,
        requirements: q.requirements,
        criteria: (q.criteria || []).map(hydrateCriterion),
        sub_questions: ((q.sub_questions) || []).map(hydrateSubQuestion),
        // Declared on QuestionOntology — access directly
        example_solution: q.example_solution,
        trace_tables: q.trace_tables,
        context_tables: q.context_tables,
        // Not declared on QuestionOntology — access via raw
        code_blocks: raw.code_blocks as string[] | undefined,
        extraction_status: raw.extraction_status as RubricQuestion['extraction_status'],
        extraction_error: raw.extraction_error as string | null | undefined,
        // Proposals — ephemeral, hydrated from backend but not dehydrated on save
        proposals: hydrateProposalSet(raw.proposals),
        _carry: carryOf(raw, MODELED_QUESTION_KEYS),
    };
}

function hydrateSubQuestion(sq: SubQuestion): RubricSubQuestion {
    // Access extra DOCX fields that may exist on the raw JSON
    const raw = sq as unknown as Record<string, unknown>;

    return {
        sub_question_id: sq.sub_question_id,
        index: sq.index,
        title: (raw.title as string | null | undefined) ?? null,
        text: sq.text,
        points: safeParseFloat(sq.points),
        criteria: (sq.criteria || []).map(hydrateCriterion),
        // B-11: recurse into nested sub-questions (the depth-2 subtree that was
        // silently dropped). A node is a leaf (criteria) XOR a parent (sub_questions).
        sub_questions: (sq.sub_questions || []).map(hydrateSubQuestion),
        // B-11: sub-question worked solution — editable, was dropped on save.
        example_solution: sq.example_solution,
        // DOCX extraction metadata (pass through)
        trace_tables: raw.trace_tables as RubricSubQuestion['trace_tables'],
        extraction_status: raw.extraction_status as RubricSubQuestion['extraction_status'],
        extraction_error: raw.extraction_error as string | null | undefined,
        // Proposals — ephemeral, hydrated from backend but not dehydrated on save
        proposals: hydrateProposalSet(raw.proposals),
        _carry: carryOf(raw, MODELED_SUBQUESTION_KEYS),
    };
}

function hydrateCriterion(c: CriterionOntology): RubricCriterion {
    const raw = c as unknown as Record<string, unknown>;

    const rawSubCriteria = raw.sub_criteria as Array<{
        sub_criterion_id?: string; index?: number; description: string; points: string | number;
    }> | null | undefined;
    const sub_criteria = rawSubCriteria?.length
        ? rawSubCriteria.map((sc, i): RubricSubCriterion => ({
            sub_criterion_id: (sc.sub_criterion_id) || `sc${i}`,
            index: sc.index ?? i,
            description: sc.description,
            points: safeParseFloat(sc.points),
            _carry: carryOf(sc as unknown as Record<string, unknown>, MODELED_SUBCRITERION_KEYS),
        }))
        : null;

    return {
        criterion_id: c.criterion_id,
        index: c.index,
        description: c.description,
        points: safeParseFloat(c.points),
        skill_targets: c.skill_targets,
        requirements: c.requirements,
        extraction_confidence: raw.extraction_confidence as RubricCriterion['extraction_confidence'],
        notes: raw.notes as string | null | undefined,
        sub_criteria,
        // B-11: carries e.g. `evaluation_guidance` (backend-modeled, never typed here)
        // and any future criterion field, so a round-trip preserves them.
        _carry: carryOf(raw, MODELED_CRITERION_KEYS),
    };
}


/**
 * Hydrate proposal data from backend wire format.
 *
 * Proposals are EPHEMERAL — they exist between extraction and teacher decision.
 * They are NOT dehydrated on save (silently dropped).
 *
 * Returns null if no proposals or proposals are empty.
 */
function hydrateProposalSet(raw: unknown): ProposalSet | null {
    if (!raw || typeof raw !== 'object') return null;

    const data = raw as Record<string, unknown>;

    const rawProposed = Array.isArray(data.proposed_criteria) ? data.proposed_criteria : [];
    if (rawProposed.length === 0) return null;

    const proposed_criteria: ProposedCriterion[] = rawProposed.map(
        (pc: Record<string, unknown>, idx: number) => ({
            temp_id: (typeof pc.temp_id === 'string' ? pc.temp_id : null) || `proposed_${Date.now()}_${idx}`,
            description: String(pc.description || ''),
            points: safeParseFloat(pc.points as string | number | undefined),
            explanation: String(pc.explanation || ''),
        })
    );

    const rawDist = Array.isArray(data.enhanced_distribution) ? data.enhanced_distribution : [];
    const enhanced_distribution: EnhancedPointEntry[] = rawDist.map(
        (entry: Record<string, unknown>) => ({
            // Backend now always emits criterion_id (the real frontend key).
            // Do NOT fall back to original_row_idx — that is a backend-internal
            // row sequence number and never matches any criterion_id in the frontend.
            criterion_id: String(entry.criterion_id || ''),
            points: safeParseFloat(entry.points as string | number | undefined),
        })
    );

    return { proposed_criteria, enhanced_distribution, question_purpose: String(data.question_purpose || '') };
}

// ─────────────────────────────────────────────────────────
// DEHYDRATION: Frontend → Backend (number → string)
// Called ONCE when saving to backend.
// Field-by-field construction — NO type casts.
//
// NOTE: `proposals` is intentionally NOT dehydrated. Proposals are
// ephemeral UI state — they exist between extraction and teacher
// accept/reject, then disappear. They are never persisted.
// ─────────────────────────────────────────────────────────

export function dehydrateQuestions(questions: RubricQuestion[]): QuestionOntology[] {
    return questions.map(dehydrateQuestion);
}

function dehydrateQuestion(q: RubricQuestion): QuestionOntology {
    const modeled: QuestionOntology = {
        question_id: q.question_id,
        question_type: q.question_type,
        question_text: q.question_text,
        total_points: String(q.total_points),
        allow_multiple_valid_forms: q.allow_multiple_valid_forms,
        skill_targets: q.skill_targets,
        requirements: q.requirements,
        criteria: q.criteria.map(dehydrateCriterion),
        sub_questions: (q.sub_questions || []).map(dehydrateSubQuestion),
        // B-11: example_solution is editable — was dropped here (a live edit-loss bug).
        example_solution: q.example_solution,
    };
    return withCarry(modeled, q._carry);
}

function dehydrateSubQuestion(sq: RubricSubQuestion): SubQuestion {
    const modeled: SubQuestion = {
        sub_question_id: sq.sub_question_id,
        index: sq.index,
        title: sq.title ?? null,
        text: sq.text,
        points: String(sq.points),
        criteria: sq.criteria.map(dehydrateCriterion),
        // B-11: recurse — nested sub-questions are now first-class, not dropped.
        sub_questions: (sq.sub_questions || []).map(dehydrateSubQuestion),
        example_solution: sq.example_solution,
    };
    return withCarry(modeled, sq._carry);
}

function dehydrateCriterion(c: RubricCriterion): CriterionOntology {
    const modeled: CriterionOntology = {
        criterion_id: c.criterion_id,
        index: c.index,
        description: c.description,
        points: String(c.points),
        skill_targets: c.skill_targets,
        requirements: c.requirements,
        sub_criteria: c.sub_criteria?.map(sc => withCarry({
            sub_criterion_id: sc.sub_criterion_id,
            index: sc.index,
            description: sc.description,
            points: String(sc.points),
        }, sc._carry)) ?? null,
    };
    // _carry brings back evaluation_guidance / notes / extraction_confidence etc.
    return withCarry(modeled, c._carry);
}

// ─────────────────────────────────────────────────────────
// PARENT-FROM-CRITERIA CASCADE
// The ONLY silent correction in the editor. Read the JSDoc.
// ─────────────────────────────────────────────────────────

/**
 * Bottom-up cascade: recompute each structural parent so it equals Σ of its
 * direct children, at ANY nesting depth (B-11 — was depth-1).
 *
 *   - Leaf sub-question (has criteria):   sq.points = Σ sq.criteria.points.
 *   - Parent sub-question (sub_questions): sq.points = Σ children.points,
 *     computed AFTER recursing into the children (bottom-up).
 *   - Question has sub_questions: cascade each; q.total_points is NEVER touched
 *     — INV-R1 surfaces any mismatch.
 *   - Question has direct criteria only: q.total_points = Σ q.criteria.points.
 *
 * The depth-1 version treated every sub-question as a leaf, which would ZERO a
 * parent (Σ of its empty direct-criteria) the moment nesting exists — so the
 * recursion is required, not cosmetic.
 *
 * This is the ONLY silent correction in the editor. Every other consistency
 * check surfaces through rubric-validation.ts as an Annotation that blocks
 * save until the teacher resolves it manually.
 *
 * Call this ONLY after an operation that may change criterion.points
 * (i.e. updateCriterion). Idempotent — safe to call when nothing changed.
 *
 * Do NOT call after:
 *   - structural ops on criteria (add / remove / reorder)
 *       → would mask the gap a removal is supposed to leave behind
 *         (Q1-strict: removed criterion's points are NOT redistributed)
 *   - edits to sq.points, q.total_points, sub_criterion.points
 *       → would re-introduce top-down silent correction
 *
 * Returns a new array (immutable).
 */
function cascadeSubQuestion(sq: RubricSubQuestion): RubricSubQuestion {
    if (sq.sub_questions && sq.sub_questions.length > 0) {
        const children = sq.sub_questions.map(cascadeSubQuestion);
        return {
            ...sq,
            sub_questions: children,
            points: children.reduce((sum, c) => sum + c.points, 0),
        };
    }
    return { ...sq, points: sq.criteria.reduce((sum, c) => sum + c.points, 0) };
}

export function recalculateParentsFromCriteria(
    questions: RubricQuestion[]
): RubricQuestion[] {
    return questions.map((q) => {
        if (q.sub_questions && q.sub_questions.length > 0) {
            // Cascade each sub-question (recursively); q.total_points stays put.
            return { ...q, sub_questions: q.sub_questions.map(cascadeSubQuestion) };
        }
        // Direct-criteria question: cascade straight into q.total_points.
        const directSum = q.criteria.reduce((sum, c) => sum + c.points, 0);
        return { ...q, total_points: directSum };
    });
}

// ─────────────────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────────────────

/** Parse question number from question_id: "q1" → 1, "q12" → 12 */
export function parseQuestionNumber(questionId: string): number {
    const match = questionId.match(/q(\d+)/);
    return match ? parseInt(match[1], 10) : 0;
}

/**
 * Detect whether raw JSON is ontology format or legacy format.
 *
 * Ontology format has `question_id` (string like "q1").
 * Legacy format has `question_number` (number like 1).
 *
 * Returns 'ontology' | 'legacy' | 'unknown'.
 */
export function detectRubricFormat(
    questions: unknown[]
): 'ontology' | 'legacy' | 'unknown' {
    if (!Array.isArray(questions) || questions.length === 0) return 'unknown';
    const first = questions[0] as Record<string, unknown>;
    if (typeof first.question_id === 'string') return 'ontology';
    if (typeof first.question_number === 'number') return 'legacy';
    return 'unknown';
}

// ─────────────────────────────────────────────────────────
// LEGACY HYDRATION ADAPTER
// Converts ExtractedQuestion[] (legacy PDF pipeline) to RubricQuestion[].
// Used to keep the PDF extraction path working during migration.
// ─────────────────────────────────────────────────────────

/**
 * Hydrate from legacy format (ExtractedQuestion[]) to display-ready RubricQuestion[].
 * Handles field renaming: criterion_description → description, total_points → points, etc.
 */
export function hydrateLegacyQuestions(questions: unknown[]): RubricQuestion[] {
    return (questions || []).map((q: any, qi: number) => {
        const criteria = (q.criteria || []).map((c: any, ci: number) =>
            hydrateLegacyCriterion(c, ci)
        );
        const subQuestions = (q.sub_questions || []).map((sq: any, si: number) =>
            hydrateLegacySubQuestion(sq, si)
        );
        return {
            question_id: q.question_id || `q${q.question_number}`,
            question_type: q.question_type,
            question_text: q.question_text ?? undefined,
            total_points: safeParseFloat(q.total_points),
            criteria,
            sub_questions: subQuestions,
            allow_multiple_valid_forms: q.allow_multiple_valid_forms,
            // DOCX-specific (pass through)
            example_solution: q.example_solution,
            code_blocks: q.code_blocks,
            trace_tables: q.trace_tables,
            context_tables: q.context_tables,
            extraction_status: q.extraction_status,
            extraction_error: q.extraction_error,
        } satisfies RubricQuestion;
    });
}

function hydrateLegacyCriterion(c: any, index: number): RubricCriterion {
    const rawSubCriteria = c.sub_criteria as Array<{
        sub_criterion_id?: string; index?: number; description: string; points: string | number;
    }> | null | undefined;
    const sub_criteria = rawSubCriteria?.length
        ? rawSubCriteria.map((sc, i): RubricSubCriterion => ({
            sub_criterion_id: sc.sub_criterion_id || `sc${i}`,
            index: sc.index ?? i,
            description: sc.description,
            points: safeParseFloat(sc.points),
        }))
        : null;

    return {
        criterion_id: c.criterion_id || `c${index}`,
        index: c.index ?? index,
        description: c.criterion_description || c.description || '',
        points: safeParseFloat(c.total_points ?? c.points),
        skill_targets: c.skill_targets,
        requirements: c.requirements,
        extraction_confidence: c.extraction_confidence,
        notes: c.notes,
        sub_criteria,
    };
}

function hydrateLegacySubQuestion(sq: any, index: number): RubricSubQuestion {
    return {
        sub_question_id: sq.sub_question_id || `sq${index}`,
        index: sq.index ?? index,
        title: (sq.title as string | null | undefined) ?? null,
        text: sq.sub_question_text ?? sq.text ?? undefined,
        points: safeParseFloat(sq.total_points ?? sq.points),
        criteria: (sq.criteria || []).map((c: any, ci: number) =>
            hydrateLegacyCriterion(c, ci)
        ),
        trace_tables: sq.trace_tables,
        extraction_status: sq.extraction_status,
        extraction_error: sq.extraction_error,
    };
}

/**
 * Universal hydration: auto-detects format and converts to RubricQuestion[].
 * Use this when you don't know whether data is ontology or legacy format.
 */
export function hydrateAnyQuestions(questions: unknown[]): RubricQuestion[] {
    const format = detectRubricFormat(questions);
    if (format === 'ontology') {
        return hydrateQuestions(questions as QuestionOntology[]);
    }
    // Legacy or unknown — use legacy adapter which handles both gracefully
    return hydrateLegacyQuestions(questions);
}