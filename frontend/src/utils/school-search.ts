/**
 * School lookup — the pure half of the schools step.
 *
 * The component imports ONE function and knows nothing about how the index is
 * shaped, so replacing the payload (flat array today, a trie tomorrow) touches
 * this file only.
 *
 * WHY A SCAN AND NOT A TRIE (measured 2026-08-31, decision recorded so it is
 * not re-argued from first principles). A prefix trie over the same data was
 * offered and declined: over the real Ministry export (2,194 schools) this scan
 * costs **1.5ms per keystroke** — the normalized haystacks are memoized per
 * index, so normalization is one pass per session, not one per letter. The trie
 * buys ~1.4ms of that and costs a payload that roughly DOUBLES (328KB → ~640KB)
 * on the one screen where the teacher is waiting for it, plus a generated
 * 19,498-node artifact that has to be regenerated in lockstep with the array —
 * two representations of one dataset (§0.4). If the list ever grows an order of
 * magnitude, this file is the only one that changes; that is the point of the
 * `index` parameter.
 *
 * Matching is a normalized PREFIX match on word starts, never fuzzy — the same
 * discipline as the backend's `normalize_school_name` and the conservative
 * student matcher. Fuzzy matching here would put the wrong institution one
 * careless Enter away, and the pick is what creates or joins a real `schools`
 * row.
 */

export type School = {
  /** Ministry of Education institution symbol (סמל מוסד). Stable identity. */
  id: string;
  name: string;
  city: string;
  /** `${name}, ${city}` - ready to display in a picker. */
  label: string;
  /** Lowest grade taught (0 = kindergarten, negative = pre-kindergarten). */
  gradeLow: number;
  /** Highest grade taught. */
  gradeHigh: number;
};

/**
 * Trim, collapse internal whitespace, drop Hebrew niqqud and the geresh /
 * gershayim variants, lower-case.
 *
 * The quote forms matter in Hebrew school names specifically: the same school
 * is written «תיכון ע"ש רבין», «תיכון ע״ש רבין» and «תיכון עש רבין» by three
 * different people, and a teacher typing one must still find the other.
 * U+05B0–U+05C7 is the niqqud/te'amim block; U+05F3/U+05F4 are the Hebrew
 * punctuation geresh and gershayim.
 */
export function normalizeSchoolQuery(input: string): string {
    return (input ?? '')
        // NFC first: the same Hebrew string can arrive decomposed from one
        // keyboard/OS and composed from another, and the two would not compare
        // equal before this.
        .normalize('NFC')
        .replace(/[֑-ׇ]/g, '')            // niqqud + te'amim
        .replace(/[״׳'"`´]/g, '')         // gershayim / geresh / ASCII quotes
        // Punctuation is DROPPED and hyphens become SPACES, on the evidence of
        // the real Ministry export: «ע.ש», «אורט-רוגוזין», «מקיף (ד)». Dropping
        // a hyphen outright would glue two words into one that no prefix search
        // can reach; turning it into a space makes both halves findable.
        .replace(/[.,;:()[\]{}/\\_]/g, '')
        .replace(/[-–—]/g, ' ')
        .replace(/\s+/g, ' ')
        .trim()
        .toLowerCase();
}

/** A school's searchable text: its name and its city, both normalized. */
function haystack(school: School): string {
    return normalizeSchoolQuery(`${school.name} ${school.city}`);
}

/**
 * The normalized haystacks, computed ONCE per index array.
 *
 * The real payload is every institution in Israel — thousands of rows — and
 * normalizing each of them costs four regex passes. Doing that inside the
 * per-keystroke scan meant tens of thousands of regex passes per typed letter.
 * The index is a module-level constant that never mutates, so keying the cache
 * on the array identity is sound; a WeakMap means a replaced index is collected
 * with its cache rather than pinned forever.
 */
const HAYSTACKS = new WeakMap<School[], string[]>();
/** The normalized NAMES alone — what ranking reads (see searchSchools). */
const NAMES = new WeakMap<School[], string[]>();

function haystacksFor(index: School[]): string[] {
    let cached = HAYSTACKS.get(index);
    if (!cached) {
        cached = index.map(haystack);
        HAYSTACKS.set(index, cached);
    }
    return cached;
}

function namesFor(index: School[]): string[] {
    let cached = NAMES.get(index);
    if (!cached) {
        cached = index.map((s) => normalizeSchoolQuery(s.name));
        NAMES.set(index, cached);
    }
    return cached;
}

/**
 * True when `query` matches at a WORD START of the school's name or city.
 *
 * Word-start rather than "contains": «רמת» should find "Ramat Gan" and «גן»
 * should find it too, but «ן ג» should not. Multi-word queries («בליך רמת»)
 * must match all their terms, so "Blich, Ramat Gan" is findable by name+city
 * together — which is how a teacher who knows two schools with the same name
 * tells them apart.
 */
function matches(hay: string, query: string): boolean {
    const words = hay.split(' ');
    return query
        .split(' ')
        .filter(Boolean)
        .every((term) => words.some((w) => w.startsWith(term)));
}

/**
 * Search the index. An EMPTY query returns NOTHING — deliberately: a dropdown
 * that dumps two thousand schools the moment the field is focused is not a
 * suggestion, it is a scroll.
 *
 * Results are ordered by how early the match sits (a name-start beats a
 * city-start beats a mid-name word), then alphabetically in Hebrew collation,
 * so the ordering is stable for the same query rather than payload-order.
 */
export function searchSchools(
    index: School[],
    query: string,
    limit = 8,
): School[] {
    const q = normalizeSchoolQuery(query);
    if (!q) return [];

    const firstTerm = q.split(' ')[0];
    const hays = haystacksFor(index);
    const names = namesFor(index);
    const scored: { school: School; rank: number }[] = [];

    for (let i = 0; i < index.length; i += 1) {
        if (!matches(hays[i], q)) continue;
        // Rank by WHERE the match lands, not by where it lands in the
        // concatenated haystack: a school whose NAME starts with what she typed
        // is what she meant; a name-word match is next; a city-only match is
        // the weakest ("everything in חיפה") and belongs last.
        const name = names[i];
        const rank = name.startsWith(q)
            ? 0
            : name.split(' ').some((w) => w.startsWith(firstTerm))
              ? 1
              : 2;
        scored.push({ school: index[i], rank });
        // Bail out only after enough candidates to sort meaningfully; a large
        // index must not cost a full scan-and-sort on every keystroke.
        if (scored.length >= limit * 8) break;
    }

    scored.sort(
        (a, b) =>
            a.rank - b.rank ||
            a.school.label.localeCompare(b.school.label, 'he'),
    );

    return scored.slice(0, limit).map((s) => s.school);
}

/**
 * True when the typed text already IS one of the results, under the same
 * normalization. Drives whether the "add it as you typed" affordance shows —
 * offering to create a school she just picked from the list would produce a
 * duplicate-looking row for no reason.
 */
export function queryExactlyMatches(results: School[], query: string): boolean {
    const q = normalizeSchoolQuery(query);
    if (!q) return false;
    return results.some(
        (s) =>
            normalizeSchoolQuery(s.name) === q ||
            normalizeSchoolQuery(s.label) === q,
    );
}
