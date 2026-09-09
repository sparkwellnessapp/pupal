/**
 * How to render a student's answer: prose, or a code island (R5).
 *
 * Two modes, and the choice is per-ANSWER, not per-line:
 *   prose  every line is Hebrew-only → RTL, the UI face, right-aligned
 *   code   anything else → a `dir="ltr"` island, Fira Code, left-aligned,
 *          numbered lines
 *
 * Inside a code island the direction is decided per LINE, because a Hebrew
 * comment in C# is still a line of that program: it keeps the code's
 * left-alignment and indentation, and only its text span turns RTL (OD-F2,
 * ruled 2026-08-31 — left, so the indentation stays honest).
 *
 * ⚠ `unicode-bidi: plaintext` IS FALSIFIED AND MUST NOT COME BACK. It resolves
 * paragraph direction from the FIRST STRONG character, so a Hebrew-initial
 * comment (`// תכונות`) goes RTL-base and the `//` migrates to the RIGHT of the
 * Hebrew — the exact defect it was proposed to prevent. The standing guard is
 * the Playwright bounding-box test; run it against any new mechanism before
 * believing a redesign of this (CLAUDE.md §10).
 */

/** Characters that mean "this line is program text, not prose". */
const CODE_CHARS = /[A-Za-z0-9{}();=<>+\-*/[\]]/;
const HEBREW = /[֐-׿]/;
/** A leading line-comment marker, which never decides a line's language. */
const LEADING_COMMENT = /^\s*(?:\/\/|#|--)\s*/;

export type AnswerMode = 'prose' | 'code';

/**
 * Prose only when EVERY line is free of program characters.
 *
 * Deliberately conservative in the code direction: a prose answer shown as code
 * is ugly, but a code answer shown as prose is unreadable — RTL reorders the
 * operators and the indentation collapses. When unsure, render code.
 *
 * This is the COMPUTER-SCIENCE heuristic (any Latin letter or digit ⇒ code). It
 * is untouched; the subject decides whether it runs at all — see
 * `answerRenderPlan`.
 */
export function detectAnswerMode(answer: string): AnswerMode {
    const lines = answer.split('\n');
    return lines.every((line) => !CODE_CHARS.test(line)) ? 'prose' : 'code';
}

export interface AnswerRenderPlan {
    mode: AnswerMode;
    /** Paragraph direction of a PROSE answer (a code island is always ltr). */
    dir: 'rtl' | 'ltr';
}

/**
 * How to render an answer, decided by the rubric's SUBJECT (execution plan
 * Phase 3a, 2026-09-08) — never by guessing from the text for a non-CS subject:
 *   english          → prose, LTR (an essay with a digit is still an essay)
 *   mathematics      → prose, RTL container; the browser's bidi algorithm
 *                      isolates the Latin/digit runs of the linear notation
 *   computer_science → today's heuristic, byte-for-byte (prose RTL | code)
 *   unknown/absent   → the CS heuristic (pre-seam rows carry no subject)
 */
export function answerRenderPlan(answer: string, subject?: string | null): AnswerRenderPlan {
    if (subject === 'english') return { mode: 'prose', dir: 'ltr' };
    // ALPHA-GAP A-2 (D-1): mode 'prose' for mathematics; alpha adds a 'math' mode + <MathText> (KaTeX).
    if (subject === 'mathematics') return { mode: 'prose', dir: 'rtl' };
    const mode = detectAnswerMode(answer);
    return { mode, dir: mode === 'prose' ? 'rtl' : 'ltr' };
}

/**
 * Is this line of a code island Hebrew text (a comment) rather than code?
 *
 * The leading comment marker is stripped BEFORE the test — otherwise `//`
 * counts as a code character and every Hebrew comment reads as code, which is
 * the whole case this exists for.
 */
export function isHebrewLine(line: string): boolean {
    const withoutMarker = line.replace(LEADING_COMMENT, '');
    return HEBREW.test(line) && !CODE_CHARS.test(withoutMarker);
}

export interface AnswerLine {
    /** 1-based, as rendered in the gutter. */
    number: number;
    text: string;
    /** `rtl` only for a Hebrew-only comment line inside a code island. */
    dir: 'ltr' | 'rtl';
}

export function answerLines(answer: string, mode: AnswerMode): AnswerLine[] {
    return answer.split('\n').map((text, index) => ({
        number: index + 1,
        text,
        dir: mode === 'code' && isHebrewLine(text) ? 'rtl' : 'ltr',
    }));
}
