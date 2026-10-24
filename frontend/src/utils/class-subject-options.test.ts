import { describe, expect, it } from 'vitest';

import { classSubjectOptions } from './class-subject-options';
import type { SubjectMatterOption } from '@/types/classroom';

const sm = (id: number, code: string, name_he: string): SubjectMatterOption =>
    ({ id, code, name_he, name_en: code });

const CS = sm(1, 'computer_science', 'מדעי המחשב');
const EN = sm(2, 'english', 'אנגלית');
const MATH = sm(3, 'mathematics', 'מתמטיקה');
const BIO = sm(4, 'biology', 'ביולוגיה');
const HIST = sm(5, 'history', 'היסטוריה');
const ALL = [BIO, HIST, EN, MATH, CS];

describe('classSubjectOptions', () => {
    it('offers only her own subjects when her profile has any', () => {
        expect(classSubjectOptions(ALL, [BIO, CS])).toEqual([BIO, CS]);
    });

    it('falls back to the launch set (CS, English, Math) when she has none', () => {
        const ids = classSubjectOptions(ALL, []).map(s => s.id).sort();
        expect(ids).toEqual([CS.id, EN.id, MATH.id].sort());
    });

    it('keeps a class\'s current subject offered even when it is not hers', () => {
        expect(classSubjectOptions(ALL, [CS], HIST.id)).toEqual([CS, HIST]);
        expect(classSubjectOptions(ALL, [], HIST.id).map(s => s.id)).toContain(HIST.id);
    });

    it('does not duplicate a current subject that is already offered', () => {
        expect(classSubjectOptions(ALL, [CS, BIO], CS.id)).toEqual([CS, BIO]);
    });

    it('ignores a current id that no longer exists', () => {
        expect(classSubjectOptions(ALL, [CS], 999)).toEqual([CS]);
    });
});
