import { describe, expect, it } from 'vitest';

import {
    normalizeSchoolQuery,
    queryExactlyMatches,
    searchSchools,
    type School,
} from './school-search';

// gradeLow/gradeHigh come from the Ministry export and are carried for display
// only — the search never reads them, so a fixed pair keeps these fixtures about
// the thing under test.
const school = (id: string, name: string, city: string): School => ({
    id,
    name,
    city,
    label: `${name}, ${city}`,
    gradeLow: 7,
    gradeHigh: 12,
});

const INDEX: School[] = [
    school('1', 'עירוני א', 'תל אביב'),
    school('2', 'בליך', 'רמת גן'),
    school('3', 'תיכון ע״ש רבין', 'חיפה'),
    school('4', 'הרצוג', 'כפר סבא'),
    school('5', 'בליך', 'חיפה'),
];

describe('normalizeSchoolQuery', () => {
    it('trims and collapses internal whitespace', () => {
        expect(normalizeSchoolQuery('  בליך   הגדול ')).toBe('בליך הגדול');
    });

    it('strips the geresh/gershayim variants so one school is one school', () => {
        expect(normalizeSchoolQuery('ע״ש')).toBe('עש');
        expect(normalizeSchoolQuery('ע"ש')).toBe('עש');
        expect(normalizeSchoolQuery("ע'ש")).toBe('עש');
    });

    it('strips niqqud', () => {
        expect(normalizeSchoolQuery('בְּלִיךְ')).toBe('בליך');
    });

    it('lower-cases latin text', () => {
        expect(normalizeSchoolQuery('Blich HIGH')).toBe('blich high');
    });

    // The three cases the real Ministry export forced (2026-08-31).
    it('drops punctuation, so «ע.ש» and «עש» are one thing', () => {
        expect(normalizeSchoolQuery('ע.ש')).toBe('עש');
        expect(normalizeSchoolQuery('מקיף (ד)')).toBe('מקיף ד');
    });

    it('turns a hyphen into a SPACE, never into nothing', () => {
        // Dropping it would glue the halves into a word no prefix reaches.
        expect(normalizeSchoolQuery('אורט-רוגוזין')).toBe('אורט רוגוזין');
        expect(normalizeSchoolQuery('אורט–רוגוזין')).toBe('אורט רוגוזין');
    });

    it('composes to NFC, so two keyboards produce one key', () => {
        const decomposed = 'שלום'.normalize('NFD');
        expect(normalizeSchoolQuery(decomposed)).toBe(normalizeSchoolQuery('שלום'));
    });
});

describe('searchSchools', () => {
    it('returns NOTHING for an empty query — a dropdown is not a data dump', () => {
        expect(searchSchools(INDEX, '')).toEqual([]);
        expect(searchSchools(INDEX, '   ')).toEqual([]);
    });

    it('matches on a name prefix', () => {
        expect(searchSchools(INDEX, 'בלי').map((s) => s.id).sort()).toEqual(['2', '5']);
    });

    it('matches on the city, so «רמת גן» finds the school there', () => {
        expect(searchSchools(INDEX, 'רמת').map((s) => s.id)).toEqual(['2']);
    });

    it('requires ALL terms, which is how two same-named schools are told apart', () => {
        expect(searchSchools(INDEX, 'בליך חיפה').map((s) => s.id)).toEqual(['5']);
        expect(searchSchools(INDEX, 'בליך רמת').map((s) => s.id)).toEqual(['2']);
    });

    it('matches word starts, not arbitrary substrings', () => {
        // "ליך" sits inside "בליך" but starts no word in it.
        expect(searchSchools(INDEX, 'ליך')).toEqual([]);
    });

    it('finds a quoted name typed without the quote mark', () => {
        expect(searchSchools(INDEX, 'עש רבין').map((s) => s.id)).toEqual(['3']);
    });

    it('respects the limit', () => {
        expect(searchSchools(INDEX, 'א', 2).length).toBeLessThanOrEqual(2);
    });

    it('is deterministic for the same query', () => {
        expect(searchSchools(INDEX, 'בליך')).toEqual(searchSchools(INDEX, 'בליך'));
    });

    it('finds a hyphenated name by either half', () => {
        const idx = [...INDEX, school('9', 'אורט-רוגוזין', 'אשקלון')];
        expect(searchSchools(idx, 'רוגוזין').map((s) => s.id)).toEqual(['9']);
        expect(searchSchools(idx, 'אורט').map((s) => s.id)).toEqual(['9']);
    });

    it('ranks a NAME match above a city-only match', () => {
        // "חיפה" is school 3's city and school 8's name — the name wins.
        const idx = [...INDEX, school('8', 'חיפה הריאלי', 'תל אביב')];
        expect(searchSchools(idx, 'חיפה')[0].id).toBe('8');
    });

    it('ignores niqqud and quote-mark differences between query and data', () => {
        expect(searchSchools(INDEX, 'ע״ש').map((s) => s.id)).toEqual(['3']);
    });
});

describe('queryExactlyMatches', () => {
    it('is true when the typed text already names a result', () => {
        const results = searchSchools(INDEX, 'הרצוג');
        expect(queryExactlyMatches(results, 'הרצוג')).toBe(true);
        expect(queryExactlyMatches(results, 'הרצוג, כפר סבא')).toBe(true);
    });

    it('is false for a partial word, so the free-text offer still shows', () => {
        expect(queryExactlyMatches(searchSchools(INDEX, 'הרצ'), 'הרצ')).toBe(false);
    });

    it('is false when nothing matched at all', () => {
        expect(queryExactlyMatches([], 'בית ספר שלא קיים')).toBe(false);
    });
});

// ── The REAL Ministry export ─────────────────────────────────────────────────
//
// The fixtures above pin the RULES on data this file controls. These pin the
// facts the product depends on in the data it actually ships — read from the
// data module itself, so they cannot drift into testing a stale copy.
describe('the shipped dataset', () => {
    it('has a unique 6-digit Ministry symbol on every row', async () => {
        const { schools } = await import('@/data/israeli-schools');
        expect(schools.length).toBeGreaterThan(2000);
        expect(new Set(schools.map((s) => s.id)).size).toBe(schools.length);
        // The backend refuses anything that is not ^[0-9]{4,12}$ — one unmatched
        // row here is a teacher who cannot finish onboarding. [0-9] and not \d,
        // matching the server: \d is Unicode-aware and would also admit
        // «١٢٣٤٥٦», which renders like «123456» but is a different identity.
        expect(schools.filter((s) => !/^[0-9]{4,12}$/.test(s.id))).toEqual([]);
    });

    it('labels every row as «name, city», which is what the chip shows', async () => {
        const { schools } = await import('@/data/israeli-schools');
        const wrong = schools.filter((s) => s.label !== `${s.name}, ${s.city}`);
        expect(wrong.slice(0, 3)).toEqual([]);
    });

    it('really does contain schools that share a name in one city', async () => {
        // 023's premise, asserted against the data rather than remembered.
        const { schools } = await import('@/data/israeli-schools');
        const seen = new Map<string, string[]>();
        for (const s of schools) {
            const k = `${normalizeSchoolQuery(s.name)}|${s.city}`;
            seen.set(k, [...(seen.get(k) ?? []), s.id]);
        }
        const clashes = [...seen.values()].filter((ids) => ids.length > 1);
        expect(clashes.length).toBeGreaterThan(0);
        // …and their symbols are what tells them apart.
        clashes.forEach((ids) => expect(new Set(ids).size).toBe(ids.length));
    });

    it('finds a real school by name and by city', async () => {
        const { schools } = await import('@/data/israeli-schools');
        const target = schools.find((s) => s.name.includes('בליך'))!;
        expect(target).toBeDefined();
        const byName = searchSchools(schools, 'בליך');
        expect(byName.map((s) => s.id)).toContain(target.id);
        const byBoth = searchSchools(schools, `בליך ${target.city}`);
        expect(byBoth.map((s) => s.id)).toContain(target.id);
    });
});
