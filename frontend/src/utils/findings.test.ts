import { describe, it, expect } from 'vitest';
import type { Annotation } from '@/lib/api';
import type { ValidationIssue } from '@/utils/rubric-validation';
import {
    composeFindings, confidenceRegister, hedge, deriveFix, acknowledgedIdsFor,
    countFindingsByClass, findingsSummaryLine, advisoryScanStatus,
    type PedagogicalMistakeLike,
} from './findings';

/**
 * PR-6 §9 — the composition matrix. The load-bearing property is that ONE event on
 * ONE node produces ONE card no matter how many of the three sources describe it,
 * while genuinely different events stay separate — counts are by card, never by node.
 */

const ann = (o: Partial<Annotation>): Annotation => ({
    id: 'a', annotation_type: 'rubric_mismatch', severity: 'warning',
    message: 'm', target_id: null, ...o,
});
const live = (o: Partial<ValidationIssue>): ValidationIssue => ({
    key: 'inv-r1b-q1.א.2', invariant: 'INV-R1b', severity: 'error',
    message: 'סכום הנקודות של שאלה 1, סעיף 1.2 (3 נקודות) שונה מסכום הקריטריונים (2 נקודות).',
    target_id: 'q1.א.2', ...o,
} as ValidationIssue);
const mistake = (o: Partial<PedagogicalMistakeLike>): PedagogicalMistakeLike => ({
    mistake_id: 'pts:q1.א.2', kind: 'point_sum_mismatch', target_id: 'q1.א.2',
    explanation: 'רכיבי סעיף 2 מסתכמים ל-2 אך נקודות הסעיף הן 3.',
    evidence: { children_sum: '2.0', declared: '3' },
    suggested_fix: {
        operation: 'adjust_points',
        description: 'עדכני את הניקוד המוצהר ל-2',
        params: { target: 'sub_question', field: 'points', new_value: '2.0', current_value: '3' },
    },
    requires_teacher_input: true, confidence: 1.0, ...o,
});

describe('composeFindings — the q1.א.2 TRINITY is ONE card', () => {
    const findings = composeFindings(
        [ann({ id: 'rubric_mismatch:q1.א.2', target_id: 'q1.א.2', message: 'אזהרה: … מצהירה על 3 …' })],
        [live({})],
        [mistake({})],
    );

    it('composes exactly one finding', () => {
        expect(findings).toHaveLength(1);
    });

    it('is a blocking card WITH a fix', () => {
        expect(findings[0].status).toBe('open');
        expect(findings[0].variant).toBe('blocking_fix');
        expect(findings[0].severity).toBe('error');
        expect(findings[0].hasLiveBlocker).toBe(true);
    });

    it('separates the present-tense claim from the document residual', () => {
        const f = findings[0];
        expect(f.liveMessage).toContain('שונה מסכום');          // live: may assert NOW
        expect(f.documentResidual).toContain('מצהירה על 3');    // extraction: past only
        expect(f.explanation).toBeTruthy();                     // advisory: the why
    });

    it('carries the fix and the provenance + ack keys', () => {
        const f = findings[0];
        // Legacy adjust_points params translate into ONE set_points step at the
        // boundary — everything downstream speaks the general edit wire.
        expect(f.fix).toEqual({
            label: 'עדכני את הניקוד המוצהר ל-2',
            steps: [{ op: 'set_points', scope: 'q1.א.2', value: '2', current_value: '3' }],
            displayCurrentValue: 3,
        });
        expect(f.mistakeId).toBe('pts:q1.א.2');
        expect(f.annotationIds).toEqual(['rubric_mismatch:q1.א.2']);
    });
});

describe('composeFindings — pairing boundaries', () => {
    it('DISTINCT kinds on one node stay distinct cards (count by card, not node)', () => {
        const f = composeFindings(
            [], [live({ target_id: 'q2' })],
            [mistake({ mistake_id: 'pts:q2', target_id: 'q2' }),
             mistake({ mistake_id: 'mis:q2', kind: 'structural_mislabel', target_id: 'q2', suggested_fix: null, evidence: null })],
        );
        expect(f).toHaveLength(2);
        expect(new Set(f.map((x) => x.kind))).toEqual(new Set(['point_sum', 'structural_mislabel']));
    });

    it('a target-less kind becomes a DOCUMENT-level finding (advisory strip)', () => {
        const f = composeFindings([], [], [mistake({
            mistake_id: 'selnorm:sg0', kind: 'selection_normalization', target_id: null,
            suggested_fix: null, evidence: null,
        })]);
        expect(f).toHaveLength(1);
        expect(f[0].scopeId).toBeNull();
        expect(f[0].variant).toBe('advisory_info');   // no mechanical fix exists
    });

    it("null and 'rubric' are the SAME document scope", () => {
        const f = composeFindings(
            [ann({ id: 'x', target_id: null })],
            [live({ key: 'inv-r3-rubric-total', invariant: 'INV-R3', target_id: 'rubric' })],
            [],
        );
        expect(f).toHaveLength(1);
    });
});

describe('lifecycle — resolution is driven by LIVE recomputation, not bookkeeping', () => {
    it('open while the live blocker is present', () => {
        expect(composeFindings([], [live({})], [mistake({})])[0].status).toBe('open');
    });

    it('RESOLVED once live recomputation goes silent — even though the frozen text remains', () => {
        const f = composeFindings(
            [ann({ id: 'rubric_mismatch:q1.א.2', target_id: 'q1.א.2', message: 'עדיין מצוין 3' })],
            [],                       // ← she fixed it; the validator is quiet
            [mistake({})],
        )[0];
        expect(f.status).toBe('resolved');
        expect(f.documentResidual).toContain('3');   // honest residual survives
    });

    it('DISMISSED wins over an open blocker — her judgment is respected', () => {
        const f = composeFindings([], [live({})], [mistake({ dismissed: true })])[0];
        expect(f.status).toBe('dismissed');
    });

    it('an advisory with no live counterpart resolves only via applied fix', () => {
        const base = { mistake_id: 'mis:q2', kind: 'structural_mislabel', target_id: 'q2', suggested_fix: null, evidence: null };
        expect(composeFindings([], [], [mistake(base)])[0].status).toBe('open');
        expect(composeFindings([], [], [mistake({ ...base, fix_applied: true })])[0].status).toBe('resolved');
    });
});

describe('deriveFix — steps first, legacy params, then pre-3.5.0 evidence', () => {
    it('takes a steps payload verbatim (pipeline ≥ 3.6.0 — ONE owner of fix semantics)', () => {
        const modern = mistake({
            mistake_id: 'adj:q2:structural_mislabel', kind: 'structural_mislabel', target_id: 'q2',
            suggested_fix: {
                operation: 'reassign_subquestion',
                description: "העבירי את רכיב PrintLowRatingChannel לסעיף ג'",
                steps: [
                    { op: 'move_text', scope: 'q2.ב', to_scope: 'q2.ג', text: 'ג. כתבו' },
                    { op: 'move_criterion', scope: 'q2.ב', criterion_index: 6, to_scope: 'q2.ג' },
                    { op: 'set_points', scope: 'q2.ג', value: '16' },
                ],
            },
        });
        const fix = deriveFix(modern)!;
        expect(fix.label).toBe("העבירי את רכיב PrintLowRatingChannel לסעיף ג'");
        expect(fix.steps.map((s) => s.op)).toEqual(['move_text', 'move_criterion', 'set_points']);
        expect(fix.displayCurrentValue).toBeNull();   // a structural plan has no single number
    });

    it('REFUSES a plan containing an op it does not know', () => {
        const future = mistake({
            suggested_fix: {
                operation: 'x', description: 'd',
                steps: [{ op: 'delete_question', scope: 'q1' }],
            },
        });
        expect(deriveFix(future)).toBeNull();
    });

    it('translates legacy adjust_points params into one set_points step', () => {
        expect(deriveFix(mistake({}))).toMatchObject({
            steps: [{ op: 'set_points', scope: 'q1.א.2', value: '2', current_value: '3' }],
            displayCurrentValue: 3,
        });
    });

    it('falls back to evidence for drafts saved before the payload existed', () => {
        const legacy = mistake({ suggested_fix: null });
        expect(deriveFix(legacy)).toMatchObject({
            steps: [{ op: 'set_points', scope: 'q1.א.2', value: '2', current_value: '3' }],
            displayCurrentValue: 3,
        });
    });

    it('rubric-level legacy uses achievable vs declared_total', () => {
        const legacy = mistake({
            mistake_id: 'pts:rubric', target_id: null, suggested_fix: null,
            evidence: { achievable: '90', declared_total: '100' },
        });
        expect(deriveFix(legacy)).toMatchObject({
            steps: [{ op: 'set_points', scope: 'rubric', value: '90', current_value: '100' }],
            displayCurrentValue: 100,
        });
    });

    it('proposes NOTHING when there is nothing to propose', () => {
        expect(deriveFix(mistake({ kind: 'selection_normalization', suggested_fix: null, evidence: { choose_k: 1 } }))).toBeNull();
    });
});

describe('the ARRIVAL count — «ממצאים מחכים לאישורך» is blockers + open advisories', () => {
    // The arrival card counts from the SAME composition as the review screen.
    // The regression this pins: an advisory that exists ONLY as a pedagogical
    // mistake — no annotation twin, no live invariant (hobby's structural_mislabel
    // with its reassign proposal) — was invisible to the old annotation-based
    // count: arrival said 2 while review said «2 ממצאים לתיקון · המלצה אחת».
    it('counts the fix-bearing advisory that has no annotation twin', () => {
        const findings = composeFindings(
            [ann({ id: 'rubric_mismatch:q2', target_id: 'q2', message: 'אזהרה: …' })],
            [live({ key: 'a', target_id: 'q2' }), live({ key: 'b', target_id: 'q2.ב' })],
            [
                mistake({ mistake_id: 'pts:q2', target_id: 'q2', suggested_fix: null, explained_by: 'adj:q2:structural_mislabel' }),
                mistake({ mistake_id: 'pts:q2.ב', target_id: 'q2.ב', suggested_fix: null, explained_by: 'adj:q2:structural_mislabel' }),
                mistake({
                    mistake_id: 'adj:q2:structural_mislabel', kind: 'structural_mislabel', target_id: 'q2',
                    suggested_fix: {
                        operation: 'reassign_subquestion', description: 'העבירי',
                        steps: [{ op: 'move_criterion', scope: 'q2.ב', criterion_index: 6, to_scope: 'q2.ג' }],
                    },
                }),
            ],
        );
        const { blockers, advisories } = countFindingsByClass(findings);
        expect(blockers).toBe(2);
        expect(advisories).toBe(1);          // the advisory the arrival card used to miss
        expect(blockers + advisories).toBe(3);
    });

    it('resolved and dismissed findings stay out of the waiting count', () => {
        const findings = composeFindings([], [], [
            mistake({ mistake_id: 'a', kind: 'structural_mislabel', target_id: 'q1', fix_applied: true }),
            mistake({ mistake_id: 'b', kind: 'structural_mislabel', target_id: 'q2', dismissed: true }),
        ]);
        const { blockers, advisories } = countFindingsByClass(findings);
        expect(blockers + advisories).toBe(0);
    });
});

describe('D3 — a shadow points at its root and never offers a local fix', () => {
    const root = mistake({
        mistake_id: 'adj:q2:structural_mislabel', kind: 'structural_mislabel', target_id: 'q2',
        suggested_fix: {
            operation: 'reassign_subquestion', description: 'העבירי',
            steps: [{ op: 'move_criterion', scope: 'q2.ב', criterion_index: 6, to_scope: 'q2.ג' }],
        },
    });
    const shadow = mistake({
        mistake_id: 'pts:q2.ב', target_id: 'q2.ב',
        suggested_fix: null, explained_by: 'adj:q2:structural_mislabel',
    });

    it('the shadow composes fixless with explainedBy resolved to the root scope', () => {
        const f = composeFindings([], [live({ target_id: 'q2.ב' })], [root, shadow]);
        const s = f.find((x) => x.scopeId === 'q2.ב')!;
        expect(s.fix).toBeNull();
        expect(s.explainedBy).toEqual({ mistakeId: 'adj:q2:structural_mislabel', scopeId: 'q2' });
    });

    it('even the evidence fallback cannot resurrect a local fix on a shadow', () => {
        const f = composeFindings([], [], [mistake({
            target_id: 'q2.ב', suggested_fix: null, explained_by: 'adj:q2:structural_mislabel',
        })]);
        expect(f[0].fix).toBeNull();   // evidence held the numbers, and was still refused
    });
});

describe('§5 — confidence is qualitative, and the table lives in one place', () => {
    it.each([[1.0, 'high'], [0.9, 'high'], [0.85, 'high'], [0.8, 'medium'], [0.6, 'medium'], [0.59, 'low'], [0.1, 'low']] as const)(
        'confidence %s ⇒ %s', (c, expected) => expect(confidenceRegister(c)).toBe(expected));

    it('defaults to high when the field is absent', () => {
        expect(confidenceRegister(undefined)).toBe('high');
    });

    it('hedges the register into the voice — never a number or a meter', () => {
        expect(hedge('הרכיב שייך לסעיף ג', 'high')).toBe('הרכיב שייך לסעיף ג');
        expect(hedge('הרכיב שייך לסעיף ג', 'medium')).toContain('כנראה');
        expect(hedge('הרכיב שייך לסעיף ג', 'low')).toContain('ייתכן');
    });
});

describe('§5 — counts separate the classes', () => {
    const open = composeFindings([], [live({})], [mistake({})]);
    const advisory = composeFindings([], [], [mistake({ mistake_id: 'm2', kind: 'structural_mislabel', target_id: 'q2', suggested_fix: null, evidence: null })]);

    it('a blocker and an advisory never collapse into one number', () => {
        expect(countFindingsByClass([...open, ...advisory])).toEqual({ blockers: 1, advisories: 1 });
    });

    it('resolved and dismissed count as neither', () => {
        const resolved = composeFindings([], [], [mistake({})]);
        const dismissed = composeFindings([], [live({})], [mistake({ dismissed: true })]);
        expect(countFindingsByClass([...resolved, ...dismissed])).toEqual({ blockers: 0, advisories: 0 });
    });

    it('renders the summary line, eliding zero cases', () => {
        expect(findingsSummaryLine({ blockers: 1, advisories: 2 })).toBe('ממצא אחד לתיקון · 2 המלצות');
        expect(findingsSummaryLine({ blockers: 0, advisories: 1 })).toBe('המלצה אחת');
        expect(findingsSummaryLine({ blockers: 2, advisories: 0 })).toBe('2 ממצאים לתיקון');
        expect(findingsSummaryLine({ blockers: 0, advisories: 0 })).toBeNull();
    });
});

describe('§7 — advisory-scan honesty', () => {
    it('reads the draft stamp (survives reopen)', () => {
        expect(advisoryScanStatus({ advisory_scan: 'complete' })).toBe('complete');
        expect(advisoryScanStatus({ advisory_scan: 'partial', advisory_scan_reason: 'tier_b_skipped_time_budget' })).toBe('partial');
    });

    it('detects the in-session job warnings by stable substring', () => {
        expect(advisoryScanStatus(null, ['Tier B skipped: time budget — 12s left…'])).toBe('partial');
        expect(advisoryScanStatus(null, ['Step 2c pedagogical-mistake detection failed (non-fatal): boom'])).toBe('partial');
    });

    it('an UNSTAMPED draft is unknown — never silently "complete"', () => {
        expect(advisoryScanStatus({ pipeline_version: '3.4.0' }, [])).toBe('unknown');
        expect(advisoryScanStatus(null, null)).toBe('unknown');
    });
});

describe('§6 — her decisions become the acknowledgment set', () => {
    const paired = (over: Partial<PedagogicalMistakeLike> = {}) => composeFindings(
        [ann({ id: 'rubric_mismatch:q1.א.2', target_id: 'q1.א.2' })],
        over.dismissed ? [live({})] : [],          // dismissed ⇒ blocker still live
        [mistake(over)],
    );

    it('a RESOLVED finding acks its annotation — saved silently, never re-asked', () => {
        // The UX contract is "fixed ⇒ silent save". The MECHANISM is an ack, because
        // the extraction annotation is static and survives her fix.
        expect(acknowledgedIdsFor(paired())).toEqual(['rubric_mismatch:q1.א.2']);
    });

    it('a DISMISSED finding acks too — she answered, so she is not re-asked', () => {
        expect(acknowledgedIdsFor(paired({ dismissed: true }))).toEqual(['rubric_mismatch:q1.א.2']);
    });

    it('an OPEN finding is NEVER acked (that is what keeps the gate meaningful)', () => {
        const open = composeFindings(
            [ann({ id: 'rubric_mismatch:q1.א.2', target_id: 'q1.א.2' })],
            [live({})],
            [mistake({})],
        );
        expect(acknowledgedIdsFor(open)).toEqual([]);
    });

    it('ack ids are READ from the annotation, never rebuilt from type+target', () => {
        // A backend that changes its id scheme must not need a second edit here.
        const odd = composeFindings(
            [ann({ id: 'server-minted-uuid-1234', target_id: 'q1.א.2' })],
            [],
            [mistake({})],
        );
        expect(acknowledgedIdsFor(odd)).toEqual(['server-minted-uuid-1234']);
    });

    it('REOPEN → unrelated edit → save: acks re-derive from the PERSISTED records', () => {
        // An ack is a compile-call parameter, not stored state. On reopen we have the
        // persisted annotations (kept for the residual) and the persisted decision
        // records — and nothing else. The set must rebuild identically.
        const persistedAnnotations = [ann({ id: 'rubric_mismatch:q1.א.2', target_id: 'q1.א.2' })];
        const persistedMistakes = [mistake({ fix_applied: true, fix_applied_at: '2026-07-30T10:00:00Z' })];

        // …an unrelated edit elsewhere leaves this node's live validation quiet.
        const reopened = composeFindings(persistedAnnotations, [], persistedMistakes);
        expect(reopened[0].status).toBe('resolved');
        expect(acknowledgedIdsFor(reopened)).toEqual(['rubric_mismatch:q1.א.2']);   // no re-ask
    });

    it('a dismissal persists across the round trip and still suppresses the re-ask', () => {
        const persisted = [mistake({ dismissed: true, dismissed_at: '2026-07-30T10:00:00Z' })];
        const reopened = composeFindings(
            [ann({ id: 'rubric_mismatch:q1.א.2', target_id: 'q1.א.2' })],
            [live({})],                       // the mismatch is STILL there — she chose that
            persisted,
        );
        expect(reopened[0].status).toBe('dismissed');
        expect(acknowledgedIdsFor(reopened)).toEqual(['rubric_mismatch:q1.א.2']);
    });

    it('deduplicates when several findings share an annotation id', () => {
        const f = composeFindings(
            [ann({ id: 'dup', target_id: 'q2' })],
            [],
            [mistake({ mistake_id: 'pts:q2', target_id: 'q2' })],
        );
        expect(acknowledgedIdsFor([...f, ...f])).toEqual(['dup']);
    });
});
