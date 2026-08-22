import { describe, it, expect } from 'vitest';
import type { Annotation } from '@/lib/api';
import {
    isOpenFinding, dedupeOpenFindings, isLiveValidatorAnnotation, visibleAnnotations,
} from './finding-severity';

/**
 * D7 — the LYING WARNING regression suite, pinned to the ROOT CAUSE.
 *
 * Root cause (traced, not guessed): the backend bakes extraction-time numbers into
 * a Hebrew message string (`pipeline.py`: "…ב{scope} הוא {computed} … מצהירה על
 * {declared}…") and `page.tsx` passes that string through FOREVER
 * (`[...extractionAnnotations, ...liveAnnotations]`), while only the live half
 * recomputes. Edit a point and the frozen message asserts a present-tense claim
 * that is false — a warning citing 40/21 next to a header reading 25.
 *
 * These tests pin the two things that must not silently regress: the validator's
 * `inv-r…` key convention (how "live" is recognized) and the suppression rule.
 */

const ann = (over: Partial<Annotation>): Annotation => ({
    id: 'x', annotation_type: 'rubric_mismatch', severity: 'warning',
    message: 'm', target_id: null, ...over,
});

/** The exact shape the backend emits for a persistent Q-level point mismatch. */
const STALE_EXTRACTION = ann({
    id: 'srv-1',
    annotation_type: 'rubric_mismatch',
    severity: 'warning',
    target_id: 'q1',
    message: 'אזהרה: סכום הנקודות של תת-השאלות בQ1 הוא 21 נקודות, אך כותרת השאלה מצהירה על 40 נקודות — ייתכן שמדובר בשגיאה בשאלון המקורי. יש לבדוק ידנית.',
});

/** The live INV-R1 twin on the same node — recomputed from current state. */
const LIVE_TWIN = ann({
    id: 'inv-r1-q1',
    annotation_type: 'invariant_violation',
    severity: 'error',
    target_id: 'q1',
    message: 'סכום הנקודות של שאלה 1 (25 נקודות) שונה מסכום הנקודות של תתי-השאלות שלה (21 נקודות).',
});

describe('isLiveValidatorAnnotation — pins the validator key convention', () => {
    // If rubric-validation.ts ever renames these keys, EVERY live finding would be
    // reclassified as "static" and the suppression rule would invert. Pin them.
    it.each([
        'inv-r1-q1',
        'inv-r1b-q1.א.2',
        'inv-r2-c17',
        'inv-r3-rubric-total',
        'inv-r-xor-q1.א',
    ])('recognizes live key %s', (id) => {
        expect(isLiveValidatorAnnotation(ann({ id }))).toBe(true);
    });

    it('does NOT recognize a backend-minted id as live', () => {
        expect(isLiveValidatorAnnotation(STALE_EXTRACTION)).toBe(false);
        expect(isLiveValidatorAnnotation(ann({ id: 'a1b2c3-uuid' }))).toBe(false);
    });
});

describe('visibleAnnotations — the stale-assertion rule (D7)', () => {
    it('suppresses the static extraction message when a LIVE twin covers the node', () => {
        const out = visibleAnnotations([STALE_EXTRACTION, LIVE_TWIN]);
        expect(out).toHaveLength(1);
        expect(out[0].id).toBe('inv-r1-q1');
        // the frozen "40 / 21" claim never reaches the teacher
        expect(out.some((a) => a.message.includes('מצהירה על 40'))).toBe(false);
    });

    it('KEEPS the extraction message when no live twin exists (it is the only signal)', () => {
        const out = visibleAnnotations([STALE_EXTRACTION]);
        expect(out).toHaveLength(1);
        expect(out[0].id).toBe('srv-1');
    });

    it('only suppresses on the SAME node — a live finding elsewhere is not a twin', () => {
        const elsewhere = ann({ id: 'inv-r1-q2', target_id: 'q2', severity: 'error' });
        const out = visibleAnnotations([STALE_EXTRACTION, elsewhere]);
        expect(out.map((a) => a.id).sort()).toEqual(['inv-r1-q2', 'srv-1']);
    });

    it('pairs the rubric scope across its two spellings (null vs "rubric")', () => {
        const backendGlobal = ann({ id: 'srv-2', target_id: null, message: 'סכום כל השאלות הוא 90 במקום 100' });
        const liveR3 = ann({ id: 'inv-r3-rubric-total', target_id: 'rubric', severity: 'error' });
        const out = visibleAnnotations([backendGlobal, liveR3]);
        expect(out).toHaveLength(1);
        expect(out[0].id).toBe('inv-r3-rubric-total');
    });

    it('is a no-op when nothing is live', () => {
        const all = [STALE_EXTRACTION, ann({ id: 'srv-9', target_id: 'q3' })];
        expect(visibleAnnotations(all)).toHaveLength(2);
    });

    it('never drops a live annotation', () => {
        const out = visibleAnnotations([LIVE_TWIN, STALE_EXTRACTION]);
        expect(out).toContain(LIVE_TWIN);
    });
});

describe('the counting rule still agrees after suppression', () => {
    it('the suppressed pair was already ONE finding for countFindings (flaw-1)', () => {
        const before = dedupeOpenFindings([STALE_EXTRACTION, LIVE_TWIN]);
        const after = dedupeOpenFindings(visibleAnnotations([STALE_EXTRACTION, LIVE_TWIN]));
        expect(before.nodeTargets.size + before.globalCount).toBe(1);
        expect(after.nodeTargets.size + after.globalCount).toBe(1); // unchanged — render now matches the count
    });
    it('isOpenFinding is unchanged (info is not a finding)', () => {
        expect(isOpenFinding(ann({ severity: 'info' }))).toBe(false);
        expect(isOpenFinding(LIVE_TWIN)).toBe(true);
    });
});
