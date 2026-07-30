import { describe, it, expect } from 'vitest';
import type { Annotation } from '@/lib/api';
import type { ValidationIssue } from '@/utils/rubric-validation';
import {
    composeFindings, confidenceRegister, hedge, deriveFix,
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
        expect(f.fix).toEqual({ target: 'sub_question', newValue: 2, currentValue: 3, label: 'עדכני את הניקוד המוצהר ל-2' });
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

describe('deriveFix — payload first, evidence as the pre-3.5.0 fallback', () => {
    it('uses the detector payload when present', () => {
        expect(deriveFix(mistake({}))).toMatchObject({ target: 'sub_question', newValue: 2, currentValue: 3 });
    });

    it('falls back to evidence for drafts saved before the payload existed', () => {
        const legacy = mistake({ suggested_fix: null });
        expect(deriveFix(legacy)).toMatchObject({ target: 'sub_question', newValue: 2, currentValue: 3 });
    });

    it('rubric-level legacy uses achievable vs declared_total', () => {
        const legacy = mistake({
            mistake_id: 'pts:rubric', target_id: null, suggested_fix: null,
            evidence: { achievable: '90', declared_total: '100' },
        });
        expect(deriveFix(legacy)).toMatchObject({ target: 'rubric', newValue: 90, currentValue: 100 });
    });

    it('proposes NOTHING when there is nothing to propose', () => {
        expect(deriveFix(mistake({ kind: 'selection_normalization', suggested_fix: null, evidence: { choose_k: 1 } }))).toBeNull();
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
