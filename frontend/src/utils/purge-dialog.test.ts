import { describe, expect, it } from 'vitest';

import { canConfirmPurge, needsTypedName } from './purge-dialog';

const NAME = 'נועה דוגמה';

describe('the Delete dialog — case selection (Part B §15)', () => {
    it('asks for the typed name whenever anything attributable exists', () => {
        expect(needsTypedName('signed_tests')).toBe(true);
        expect(needsTypedName('data_only')).toBe(true);
    });

    it('asks for a plain confirmation when nothing is attributable', () => {
        expect(needsTypedName('nothing')).toBe(false);
        expect(canConfirmPurge('nothing', '', NAME, 0)).toBe(true);
    });
});

describe('the Delete dialog — the enable rule (M-B3)', () => {
    it.each(['signed_tests', 'data_only'] as const)('%s: enabled only on the exact full name', (c) => {
        expect(canConfirmPurge(c, '', NAME, 0)).toBe(false);
        expect(canConfirmPurge(c, 'נועה', NAME, 0)).toBe(false);          // a prefix is not the name
        expect(canConfirmPurge(c, 'נועה  דוגמה', NAME, 0)).toBe(false);   // nor a near-miss
        expect(canConfirmPurge(c, NAME, NAME, 0)).toBe(true);
        expect(canConfirmPurge(c, `  ${NAME} `, NAME, 0)).toBe(true);     // trimmed equality
    });

    it('a grade in flight disables every case (PRV-5)', () => {
        expect(canConfirmPurge('signed_tests', NAME, NAME, 1)).toBe(false);
        expect(canConfirmPurge('nothing', '', NAME, 2)).toBe(false);
    });

    it('an empty name can never be "typed correctly"', () => {
        expect(canConfirmPurge('data_only', '', '', 0)).toBe(false);
        expect(canConfirmPurge('data_only', '   ', '  ', 0)).toBe(false);
    });
});
