/**
 * PR-6 §2 — THE FINDING MODEL. One card per event, composed from whichever of the
 * three representations exist for it (third consumer of the shared severity family,
 * alongside countFindings and findingSectionsByQuestion).
 *
 * The three sources say different things, and conflating them is what made the
 * mirror lie:
 *   - LIVE VALIDATION is the only thing allowed to assert the PRESENT. It is
 *     recomputed from editor state on every keystroke, so it is the blocker and the
 *     resolution signal both.
 *   - The EXTRACTION annotation describes the ORIGINAL DOCUMENT. Its numbers were
 *     frozen at extraction time, so it renders only as a past-tense residual and
 *     never as a current-state claim.
 *   - The PEDAGOGICAL advisory carries the explanation and the machine-proposed fix.
 *
 * PAIRING: same scope + same EVENT KIND is ONE finding (the q1.א.2 trinity — live
 * blocker + document residual + explanation-with-fix). Distinct event kinds on one
 * node stay distinct findings, so counts are by CARD, never by node.
 *
 * @see finding-severity.ts — isOpenFinding / dedupeOpenFindings (the shared family)
 */

import type { Annotation } from '@/lib/api';
import type { RubricQuestion } from '@/types/rubric';
import type { ValidationIssue } from '@/utils/rubric-validation';
import { safeParseFloat } from '@/utils/rubric-transform';
import { formatPoints } from '@/utils/rubric-display';
import { FIX_STEP_OPS, canApplySteps, type FixStep } from '@/utils/edit-steps';

export type { FixStep } from '@/utils/edit-steps';

// ─────────────────────────────────────────────────────────────────────────────
// Wire shape (the subset we consume; the generated type is wider)
// ─────────────────────────────────────────────────────────────────────────────

export interface PedagogicalMistakeLike {
    mistake_id: string;
    kind: string;
    severity?: string;
    target_id?: string | null;
    explanation: string;
    evidence?: Record<string, unknown> | null;
    suggested_fix?: {
        operation: string;
        description: string;
        params?: Record<string, unknown> | null;
        /** The general edit wire (pipeline ≥ 3.6.0). */
        steps?: Array<Record<string, unknown>> | null;
    } | null;
    requires_teacher_input?: boolean;
    confidence?: number;
    /** D3 — the root mistake whose single fix resolves this shadow too. */
    explained_by?: string | null;
    /** §4 provenance — her decisions are data, and they round-trip. */
    dismissed?: boolean | null;
    dismissed_at?: string | null;
    fix_applied?: boolean | null;
    fix_applied_at?: string | null;
}

// ─────────────────────────────────────────────────────────────────────────────
// §5 — confidence is QUALITATIVE ONLY. No numbers, no meters, one table.
// ─────────────────────────────────────────────────────────────────────────────

export type ConfidenceRegister = 'high' | 'medium' | 'low';

/**
 * The ONE mapping from the numeric field to a register. Thresholds live here and
 * nowhere else so the voice cannot drift between surfaces.
 *
 * Note on today's data: Tier A hard-codes 1.0, so only `high` occurs on
 * deterministic detections; `medium`/`low` appear for Tier-B adjudicated kinds
 * (the adjudicator defaults to 0.8).
 */
export function confidenceRegister(confidence: number | undefined | null): ConfidenceRegister {
    const c = typeof confidence === 'number' ? confidence : 1;
    if (c >= 0.85) return 'high';
    if (c >= 0.6) return 'medium';
    return 'low';
}

/** Hedge a claim to its register: high states it, medium "כנראה", low "ייתכן ש". */
export function hedge(text: string, register: ConfidenceRegister): string {
    if (register === 'high') return text;
    if (register === 'medium') return `כנראה ש${text}`;
    return `ייתכן ש${text}`;
}

// ─────────────────────────────────────────────────────────────────────────────
// The Finding
// ─────────────────────────────────────────────────────────────────────────────

/** The event a finding is ABOUT. Pairing happens on (scope, kind). */
export type FindingKind =
    | 'point_sum'
    | 'selection_normalization'
    | 'structural_mislabel'
    | 'orphan_criterion'
    | 'structure'
    | 'other';

export type FindingStatus = 'open' | 'resolved' | 'dismissed';
export type FindingVariant = 'blocking_fix' | 'advisory_fix' | 'advisory_info';

/**
 * A machine-applicable correction on the GENERAL EDIT WIRE: an ordered list of
 * primitive steps the interpreter applies atomically (edit-steps.ts). The label
 * is the button; the steps are the machine payload and never leak into copy.
 */
export interface FindingFix {
    /** Primary button label, e.g. «העבירי את רכיב PrintLowRatingChannel לסעיף ג'». */
    label: string;
    steps: FixStep[];
    /**
     * The displaced value, for the «בקובץ המקורי מצוין X» residual — present only
     * when the fix is a single declared-value adjustment (a structural plan has
     * no single number the original document "still says").
     */
    displayCurrentValue: number | null;
}

export interface Finding {
    /** Stable identity: scope + kind. Survives recomposition across edits. */
    key: string;
    scopeId: string | null;          // null ⇒ document-level (advisory strip)
    kind: FindingKind;
    status: FindingStatus;
    variant: FindingVariant;
    /** Worst severity across the composed sources (drives accent + rail dot). */
    severity: 'error' | 'warning' | 'info';
    /** True iff live recomputation reports it RIGHT NOW. The only present-tense claim. */
    hasLiveBlocker: boolean;
    /** Present-tense body — ONLY ever from live recomputation. */
    liveMessage: string | null;
    /** Past-tense residual — the original document, never asserting the present. */
    documentResidual: string | null;
    /** The advisory's explanation, already hedged to its confidence register. */
    explanation: string | null;
    confidence: ConfidenceRegister;
    fix: FindingFix | null;
    /**
     * D3 root-cause subordination: set when this finding is a SHADOW of another
     * mistake whose single fix resolves it too. A shadow never offers a local
     * fix — the card points at the root instead.
     */
    explainedBy: { mistakeId: string; scopeId: string | null } | null;
    /** Provenance key (§4) — which mistake records her decision. */
    mistakeId: string | null;
    /** Annotation ids this finding covers — the A4 ack mapping joins on these. */
    annotationIds: string[];
}

// ─────────────────────────────────────────────────────────────────────────────
// Kind mapping — every source entry reduced to ONE vocabulary
// ─────────────────────────────────────────────────────────────────────────────

/** The point-sum FAMILY: INV-R1/R1b/R2/R3 all describe the same event class. */
function kindOfInvariant(invariant: string): FindingKind {
    return invariant === 'INV-R-XOR' ? 'structure' : 'point_sum';
}

function kindOfMistake(kind: string): FindingKind {
    switch (kind) {
        case 'point_sum_mismatch': return 'point_sum';
        case 'selection_normalization': return 'selection_normalization';
        case 'structural_mislabel': return 'structural_mislabel';
        case 'orphan_criterion': return 'orphan_criterion';
        default: return 'other';
    }
}

/**
 * An extraction annotation's event class. `rubric_mismatch` IS the document's
 * record of a point-sum problem, which is what makes it the residual half of the
 * trinity; anything else keeps its own identity rather than being force-paired.
 */
function kindOfAnnotation(a: Annotation): FindingKind {
    if (a.annotation_type === 'rubric_mismatch' || a.annotation_type === 'invariant_violation') return 'point_sum';
    return 'other';
}

/** null and 'rubric' are the same (document) scope — see finding-severity. */
function scopeKey(target: string | null | undefined): string {
    return target && target !== 'rubric' ? target : ' document';
}

const composeKey = (scope: string, kind: FindingKind) => `${scope}::${kind}`;

// ─────────────────────────────────────────────────────────────────────────────
// Fix derivation (A2)
// ─────────────────────────────────────────────────────────────────────────────

function num(v: unknown): number | null {
    if (v === null || v === undefined) return null;
    const n = safeParseFloat(v as string | number);
    return Number.isFinite(n) ? n : null;
}

/** A single declared-value adjustment shows the displaced number as a residual. */
function displacedValueOf(steps: FixStep[]): number | null {
    if (steps.length !== 1) return null;
    const s = steps[0];
    if (s.op !== 'set_points' || s.criterion_index !== null && s.criterion_index !== undefined) return null;
    return num(s.current_value ?? null);
}

function stepsFix(steps: FixStep[], label: string): FindingFix | null {
    if (!steps.length || !label) return null;
    return { label, steps, displayCurrentValue: displacedValueOf(steps) };
}

/** One legacy declared-value adjustment as a modern single-step plan. */
function singleSetPoints(scope: string, newValue: number, currentValue: number | null): FixStep[] {
    return [{
        op: 'set_points', scope, value: String(newValue),
        current_value: currentValue === null ? null : String(currentValue),
    }];
}

/**
 * The one-click proposal, on the GENERAL EDIT WIRE. Three arms, newest first:
 *
 *   1. `steps` (pipeline ≥ 3.6.0) — the detector's own plan, taken verbatim
 *      after an op sanity check. ONE owner of fix semantics.
 *   2. Legacy `adjust_points` params (3.5.0 drafts) — translated into the
 *      equivalent single set_points step at this boundary, so everything
 *      downstream speaks ONE representation.
 *   3. `evidence` (pre-3.5.0 drafts, suggested_fix: null forever) — the numbers
 *      were always there; synthesized the same way.
 */
export function deriveFix(m: PedagogicalMistakeLike): FindingFix | null {
    const sf = m.suggested_fix;

    if (sf?.steps?.length) {
        const steps = sf.steps as unknown as FixStep[];
        if (steps.every((s) => (FIX_STEP_OPS as readonly string[]).includes(s.op) && typeof s.scope === 'string')) {
            return stepsFix(steps, sf.description);
        }
        return null;   // an op we don't know is a plan we must not offer
    }

    if (sf && sf.operation === 'adjust_points' && sf.params) {
        const p = sf.params as Record<string, unknown>;
        const newValue = num(p.new_value);
        const currentValue = num(p.current_value);
        const target = p.target as 'question' | 'sub_question' | 'rubric' | undefined;
        if (newValue !== null && target) {
            const scope = target === 'rubric' ? 'rubric' : (m.target_id ?? '');
            if (!scope) return null;
            return stepsFix(singleSetPoints(scope, newValue, currentValue),
                sf.description || fixLabel(scope, newValue));
        }
    }

    // Compatibility fallback — pre-3.5.0 drafts.
    if (kindOfMistake(m.kind) !== 'point_sum') return null;
    const ev = (m.evidence ?? {}) as Record<string, unknown>;
    const newValue = num(ev.children_sum) ?? num(ev.achievable);
    const currentValue = num(ev.declared) ?? num(ev.declared_total);
    if (newValue === null || currentValue === null) return null;
    const scope = m.target_id ?? 'rubric';
    return stepsFix(singleSetPoints(scope, newValue, currentValue), fixLabel(scope, newValue));
}

function fixLabel(scope: string, newValue: number): string {
    return scope === 'rubric'
        ? `עדכני את סך נקודות המחוון ל-${formatPoints(newValue)}`
        : `עדכני את הניקוד המוצהר ל-${formatPoints(newValue)}`;
}

// ─────────────────────────────────────────────────────────────────────────────
// composeFindings
// ─────────────────────────────────────────────────────────────────────────────

interface Bucket {
    scopeId: string | null;
    kind: FindingKind;
    live: ValidationIssue[];
    annotations: Annotation[];
    mistake: PedagogicalMistakeLike | null;
}

/**
 * Compose the three representations into one card model.
 *
 * `questions` is accepted for label resolution by callers that render; composition
 * itself is label-free so it stays pure and cheap to test.
 */
export function composeFindings(
    extractionAnnotations: Annotation[],
    liveIssues: ValidationIssue[],
    pedagogicalMistakes: PedagogicalMistakeLike[],
    _questions?: RubricQuestion[],
): Finding[] {
    const buckets = new Map<string, Bucket>();

    const bucket = (target: string | null | undefined, kind: FindingKind): Bucket => {
        const scope = scopeKey(target);
        const key = composeKey(scope, kind);
        let b = buckets.get(key);
        if (!b) {
            b = { scopeId: target && target !== 'rubric' ? target : null, kind, live: [], annotations: [], mistake: null };
            buckets.set(key, b);
        }
        return b;
    };

    for (const iss of liveIssues) bucket(iss.target_id, kindOfInvariant(iss.invariant)).live.push(iss);
    for (const a of extractionAnnotations) bucket(a.target_id, kindOfAnnotation(a)).annotations.push(a);
    for (const m of pedagogicalMistakes) {
        const b = bucket(m.target_id, kindOfMistake(m.kind));
        // One advisory per (scope, kind) by construction; keep the first if the
        // detector ever emits two — never silently merge two explanations.
        if (!b.mistake) b.mistake = m;
    }

    // D3 — resolve each shadow's root so its card can point there.
    const rootScopeById = new Map<string, string | null>();
    for (const m of pedagogicalMistakes) rootScopeById.set(m.mistake_id, m.target_id ?? null);

    const out: Finding[] = [];
    buckets.forEach((b, key) => out.push(finish(key, b, rootScopeById, _questions)));
    return out;
}

function finish(
    key: string, b: Bucket,
    rootScopeById: Map<string, string | null>,
    questions?: RubricQuestion[],
): Finding {
    const m = b.mistake;
    const hasLiveBlocker = b.live.length > 0;

    // ── STATUS. Resolution is driven by the live validator recomputing, never by
    // static bookkeeping: if the recomputation is silent, the arithmetic is right
    // NOW, whatever the frozen extraction text still says.
    let status: FindingStatus;
    if (m?.dismissed) {
        status = 'dismissed';
    } else if (hasLiveBlocker) {
        status = 'open';
    } else if (b.kind === 'point_sum' || b.kind === 'structure') {
        // This family HAS a live counterpart, so its silence is meaningful.
        status = 'resolved';
    } else {
        // Advisory kinds have no live counterpart — only her decision closes them.
        status = m?.fix_applied ? 'resolved' : 'open';
    }

    const severity: Finding['severity'] =
        b.live.some((i) => i.severity === 'error') ? 'error'
            : (b.annotations.some((a) => a.severity === 'error') ? 'error'
                : (b.live.length || b.annotations.length || m ? 'warning' : 'info'));

    // D3 — a SHADOW never derives a local fix, not even from the evidence
    // fallback: its root's single fix is the one answer, and a competing local
    // correction ("scale ב's criteria") would be actively wrong.
    const explainedBy = m?.explained_by
        ? { mistakeId: m.explained_by, scopeId: rootScopeById.get(m.explained_by) ?? null }
        : null;
    let fix = m && !explainedBy ? deriveFix(m) : null;
    // Preflight: a plan that no longer applies to the CURRENT tree (she edited
    // structurally since extraction) is withdrawn, never mis-applied.
    if (fix && questions && !canApplySteps(questions, fix.steps)) fix = null;

    const variant: FindingVariant =
        status === 'open' && hasLiveBlocker && fix ? 'blocking_fix'
            : fix ? 'advisory_fix'
                : 'advisory_info';

    const register = confidenceRegister(m?.confidence);

    return {
        key,
        scopeId: b.scopeId,
        kind: b.kind,
        status,
        variant,
        severity,
        hasLiveBlocker,
        // ONLY live text may speak in the present tense.
        liveMessage: b.live.length ? b.live[0].message : null,
        // The frozen extraction text survives ONLY as the original-document residual.
        documentResidual: b.annotations.length ? b.annotations[0].message : null,
        explanation: m ? hedge(m.explanation, register) : null,
        confidence: register,
        fix,
        explainedBy,
        mistakeId: m?.mistake_id ?? null,
        annotationIds: b.annotations.map((a) => a.id).filter(Boolean),
    };
}

// ─────────────────────────────────────────────────────────────────────────────
// §6 — her decisions → the compiler's acknowledgment set
// ─────────────────────────────────────────────────────────────────────────────

/**
 * The acknowledgment ids a save must carry.
 *
 * THE UX CONTRACT IS UNCHANGED — a resolved finding saves silently and is never
 * re-asked. Only the MECHANISM differs from what one might assume: the compiler's
 * ack set is not recomputed, it is literally the WARNING-severity annotations
 * present in the submitted draft (`contract_compiler.compile` step 5). An
 * extraction annotation is STATIC — it survives her fix — so a resolved finding
 * still has a live annotation demanding acknowledgment. Transmitting her decision
 * as an ack is therefore faithful reporting of a choice she actually made, not an
 * auto-ack (R-D): `open` findings are never acked here.
 *
 * ONE OWNER OF THE JOIN: every id is read from the paired annotation's own `id`
 * field, carried through composition. We never rebuild `${type}:${target}` — a
 * string-formatted join key reconstructed in a second place is how join keys
 * drift apart.
 */
export function acknowledgedIdsFor(findings: Finding[]): string[] {
    const ids = new Set<string>();
    for (const f of findings) {
        if (f.status !== 'resolved' && f.status !== 'dismissed') continue;
        for (const id of f.annotationIds) ids.add(id);
    }
    return Array.from(ids);
}

// ─────────────────────────────────────────────────────────────────────────────
// §5 counts — the classes are separated, never summed into one number
// ─────────────────────────────────────────────────────────────────────────────

export interface FindingCounts { blockers: number; advisories: number }

/** Open blockers vs open advisories. Resolved and dismissed count as neither. */
export function countFindingsByClass(findings: Finding[]): FindingCounts {
    let blockers = 0;
    let advisories = 0;
    for (const f of findings) {
        if (f.status !== 'open') continue;
        if (f.severity === 'error' || f.hasLiveBlocker) blockers++;
        else advisories++;
    }
    return { blockers, advisories };
}

/**
 * "ממצא אחד לתיקון · 2 המלצות" — zero cases elide naturally, and the two classes
 * never collapse into one number (a blocker and a suggestion are not the same news).
 */
export function findingsSummaryLine(counts: FindingCounts): string | null {
    const parts: string[] = [];
    if (counts.blockers === 1) parts.push('ממצא אחד לתיקון');
    else if (counts.blockers > 1) parts.push(`${counts.blockers} ממצאים לתיקון`);
    if (counts.advisories === 1) parts.push('המלצה אחת');
    else if (counts.advisories > 1) parts.push(`${counts.advisories} המלצות`);
    return parts.length ? parts.join(' · ') : null;
}

// ─────────────────────────────────────────────────────────────────────────────
// §7 — Tier-B partial-scan honesty
// ─────────────────────────────────────────────────────────────────────────────

export type AdvisoryScan = 'complete' | 'partial' | 'unknown';

/**
 * Read the advisory-scan stamp from the draft's provenance (pipeline ≥ 3.5.0), with
 * the job-result warnings as the in-session source.
 *
 * A draft with NO stamp is `unknown`, never `complete`: absence of advisories must
 * never read as a clean bill of health when we cannot know whether the scan ran.
 */
export function advisoryScanStatus(
    extractionMetadata?: Record<string, unknown> | null,
    jobWarnings?: string[] | null,
): AdvisoryScan {
    const stamped = extractionMetadata?.advisory_scan;
    if (stamped === 'complete' || stamped === 'partial') return stamped;
    if (jobWarnings?.some((w) => w.includes('Tier B skipped')
        || w.includes('Step 2c pedagogical-mistake detection failed'))) return 'partial';
    return extractionMetadata || jobWarnings ? 'unknown' : 'unknown';
}
