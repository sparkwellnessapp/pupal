/**
 * QM-1 — the form a quote is matched in, for a subject with math notation. A byte-for-byte
 * mirror of `backend/app/services/math_notation/quote_match.py` (+ the canonical rules of
 * `canonical.py` it reuses), pinned to it by `tests/fixtures/math_quote_match_vectors.json`.
 *
 * WHY THE CLIENT NEEDS IT. The server certifies a quote in this form — a fragment of a
 * formula quoted without its `\( \)`, `·` for `\cdot`, `²` for `^{2}` — and the review
 * surface must light the span it certified. Located with the plain rule, such a quote found
 * nothing exact and fell to the fuzzy window, which paints an APPROXIMATE region: the teacher
 * pressed «ציטוט מהתשובה» and was shown a neighbouring formula. So the client places it with
 * the server's own rule, and keeps, for every character of the form, the range of the
 * student's text it came from.
 *
 * Never mathematical equivalence: `e^{-1}` does not find `\frac{1}{e}`.
 */

type Kind = 'cw' | 'cs' | 'ch';
/** kind, value, [start, end) in the source. */
type PToken = readonly [Kind, string, number, number];

const isAsciiLetter = (c: string) => /^[A-Za-z]$/.test(c);
const isSpace = (c: string) => /^\s$/.test(c);

function tokenizeAt(body: string): PToken[] {
    const out: PToken[] = [];
    let i = 0;
    const n = body.length;
    while (i < n) {
        const c = body[i];
        if (c === '\\' && i + 1 < n) {
            let j = i + 1;
            if (isAsciiLetter(body[j])) {
                while (j < n && isAsciiLetter(body[j])) j += 1;
                out.push(['cw', body.slice(i, j), i, j]);
                i = j;
            } else {
                out.push(['cs', body.slice(i, i + 2), i, i + 2]);
                i += 2;
            }
            continue;
        }
        // Python iterates code points; a surrogate pair is ONE character there.
        const cp = body.codePointAt(i)!;
        const width = cp > 0xffff ? 2 : 1;
        out.push(['ch', body.slice(i, i + width), i, i + width]);
        i += width;
    }
    return out;
}

const SPACING_CS = new Set(['\\,', '\\;', '\\:', '\\!', '\\ ', '\\>']);
const DROP_CW = new Set([
    '\\quad', '\\qquad', '\\thinspace', '\\medspace', '\\thickspace', '\\enspace',
    '\\negthinspace', '\\displaystyle', '\\textstyle', '\\scriptstyle',
    '\\left', '\\right', '\\middle',
    '\\big', '\\Big', '\\bigg', '\\Bigg',
    '\\bigl', '\\bigr', '\\Bigl', '\\Bigr', '\\biggl', '\\biggr', '\\Biggl', '\\Biggr',
]);
const SIZERS_WITH_INVISIBLE_DOT = new Set(['\\left', '\\right', '\\middle']);
const SYNONYMS: Record<string, string> = {
    '\\dfrac': '\\frac', '\\tfrac': '\\frac', '\\cfrac': '\\frac',
    '\\le': '\\leq', '\\ge': '\\geq', '\\ne': '\\neq', '\\leqslant': '\\leq',
    '\\geqslant': '\\geq', '\\to': '\\rightarrow', '\\gets': '\\leftarrow',
    '\\lvert': '|', '\\rvert': '|', '\\vert': '|', '\\lVert': '\\|', '\\rVert': '\\|',
    '\\lbrace': '\\{', '\\rbrace': '\\}', '\\land': '\\wedge', '\\lor': '\\vee',
};
const TEXT_CMDS = new Set(['\\text', '\\textrm', '\\mathrm', '\\textit', '\\operatorname', '\\mbox']);
const ARITY: Record<string, number> = {
    '\\frac': 2, '\\binom': 2, '\\sqrt': 1, '\\overline': 1, '\\underline': 1,
    '\\vec': 1, '\\hat': 1, '\\bar': 1, '\\cancel': 1, '\\boxed': 1, '\\overrightarrow': 1,
};

const is = (t: PToken, kind: Kind, val: string) => t[0] === kind && t[1] === val;
const made = (kind: Kind, val: string, like: PToken): PToken => [kind, val, like[2], like[3]];

function groupEnd(toks: readonly PToken[], i: number): [number, boolean] {
    let depth = 0;
    for (let j = i; j < toks.length; j += 1) {
        if (is(toks[j], 'ch', '{')) depth += 1;
        else if (is(toks[j], 'ch', '}')) {
            depth -= 1;
            if (depth === 0) return [j + 1, true];
        }
    }
    return [toks.length, false];
}

function skipWs(toks: readonly PToken[], i: number): number {
    while (i < toks.length && toks[i][0] === 'ch' && isSpace(toks[i][1])) i += 1;
    return i;
}

function canonArg(toks: readonly PToken[], i0: number, out: PToken[]): number {
    const i = skipWs(toks, i0);
    if (i >= toks.length) return i;
    if (is(toks[i], 'ch', '{')) {
        const [end, closed] = groupEnd(toks, i);
        out.push(toks[i]);
        out.push(...canon(closed ? toks.slice(i + 1, end - 1) : toks.slice(i + 1, end)));
        if (closed) out.push(toks[end - 1]);
        return end;
    }
    out.push(made('ch', '{', toks[i]));
    out.push(...canon([toks[i]]));
    out.push(made('ch', '}', toks[i]));
    return i + 1;
}

function canon(toks: readonly PToken[]): PToken[] {
    const out: PToken[] = [];
    let i = 0;
    while (i < toks.length) {
        let tok = toks[i];
        let [kind, val] = tok;
        if (kind === 'cw' && TEXT_CMDS.has(val) && i + 1 < toks.length && is(toks[i + 1], 'ch', '{')) {
            const [end] = groupEnd(toks, i + 1);
            out.push(...toks.slice(i, end));
            i = end;
            continue;
        }
        if (kind === 'ch' && isSpace(val)) { i += 1; continue; }
        if (kind === 'cs' && SPACING_CS.has(val)) { i += 1; continue; }
        if (kind === 'cw' && DROP_CW.has(val)) {
            i += 1;
            if (SIZERS_WITH_INVISIBLE_DOT.has(val) && i < toks.length && is(toks[i], 'ch', '.')) i += 1;
            continue;
        }
        if (kind === 'cw') {
            val = SYNONYMS[val] ?? val;
            kind = val.length === 1 ? 'ch'
                : (val.length === 2 && !/[A-Za-z]/.test(val[1]) ? 'cs' : 'cw');
            tok = made(kind, val, tok);
        }
        if (kind === 'ch' && (val === '^' || val === '_')) {
            out.push(tok);
            i = canonArg(toks, i + 1, out);
            continue;
        }
        if (kind === 'cw' && val in ARITY) {
            out.push(tok);
            i += 1;
            if (val === '\\sqrt') {
                i = skipWs(toks, i);
                if (i < toks.length && is(toks[i], 'ch', '[')) {
                    let j = i;
                    while (j < toks.length && !is(toks[j], 'ch', ']')) j += 1;
                    out.push(...canon(toks.slice(i, j + 1)));
                    i = j + 1;
                }
            }
            for (let k = 0; k < ARITY[val]; k += 1) i = canonArg(toks, i, out);
            continue;
        }
        out.push(tok);
        i += 1;
    }
    return out;
}

const DELIMITERS = new Set(['\\(', '\\)', '\\[', '\\]']);
const GLYPHS: Record<string, [Kind, string]> = {
    '·': ['cw', '\\cdot'], '⋅': ['cw', '\\cdot'], '×': ['cw', '\\times'], '÷': ['cw', '\\div'],
    '≤': ['cw', '\\leq'], '≥': ['cw', '\\geq'], '≠': ['cw', '\\neq'], '≈': ['cw', '\\approx'],
    '±': ['cw', '\\pm'], '∞': ['cw', '\\infty'], '→': ['cw', '\\rightarrow'],
    '⇒': ['cw', '\\Rightarrow'], '⇔': ['cw', '\\Leftrightarrow'], 'π': ['cw', '\\pi'],
    'α': ['cw', '\\alpha'], 'β': ['cw', '\\beta'], '°': ['cw', '\\circ'],
    '−': ['ch', '-'], '∪': ['cw', '\\cup'], '∩': ['cw', '\\cap'],
    '↗': ['cw', '\\nearrow'], '↘': ['cw', '\\searrow'],
};
const SUPERSCRIPTS: Record<string, string> = {
    '⁰': '0', '¹': '1', '²': '2', '³': '3', '⁴': '4', '⁵': '5', '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9',
};

function prepare(text: string): PToken[] {
    const out: PToken[] = [];
    for (const tok of tokenizeAt(text)) {
        const [kind, val, s, e] = tok;
        if (kind === 'cs' && DELIMITERS.has(val)) continue;
        if (kind === 'ch' && val in GLYPHS) {
            const [gk, gv] = GLYPHS[val];
            out.push([gk, gv, s, e]);
            continue;
        }
        if (kind === 'ch' && val in SUPERSCRIPTS) {
            out.push(['ch', '^', s, e], ['ch', SUPERSCRIPTS[val], s, e]);
            continue;
        }
        out.push(tok);
    }
    return out;
}

export interface MatchForm {
    form: string;
    /** `starts[i]` / `ends[i]`: the source range of the token that produced character i. */
    starts: number[];
    ends: number[];
}

/** The QM-1 match form of `text`, with offsets back into it. */
export function matchFormAt(text: string): MatchForm {
    // untokenize, keeping where each character came from
    const chars: string[] = [];
    const st: number[] = [];
    const en: number[] = [];
    let prevCw = false;
    for (const [kind, val, s, e] of canon(prepare(text ?? ''))) {
        if (prevCw && kind === 'ch' && isAsciiLetter(val)) {
            chars.push(' '); st.push(s); en.push(s);
        }
        for (const c of Array.from(val)) { chars.push(c); st.push(s); en.push(e); }
        prevCw = kind === 'cw';
    }
    // fold case; collapse what whitespace survives (only inside \text{…})
    const out: string[] = [];
    const starts: number[] = [];
    const ends: number[] = [];
    let pending = false;
    chars.forEach((c, k) => {
        if (isSpace(c)) { pending = out.length > 0; return; }
        if (pending) { out.push(' '); starts.push(st[k]); ends.push(st[k]); pending = false; }
        for (const low of Array.from(c.toLowerCase())) { out.push(low); starts.push(st[k]); ends.push(en[k]); }
    });
    return { form: out.join(''), starts, ends };
}

export function matchForm(text: string): string {
    return matchFormAt(text).form;
}
