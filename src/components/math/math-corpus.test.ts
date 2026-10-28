import katex from 'katex';
import { validateLatex } from 'mathlive';
import { describe, expect, it } from 'vitest';

/**
 * WHAT RENDERS IS WHAT EDITS (MATH_RENDERING_PLAN §4, "Editing"). A span the review screen
 * typesets with KaTeX must also open in the MathLive field she edits it in — otherwise a
 * formula she can see is a formula she cannot fix. This corpus is every construct the
 * conventions prescribe (TRANSCRIPTION_GT_CONVENTIONS_MATH.md) plus the shapes production pro
 * actually wrote in probe v3, and each must parse in BOTH engines.
 */
const CORPUS: string[] = [
    // convention 1 — the student's form
    '\\sqrt{e}', 'e^{1/2}', '\\frac{1}{e}', 'e^{-1}', '0.5', '23.259',
    // ordinary working
    "f(x) = (\\ln x)^2 - \\ln x - 2", "f'(x) = \\frac{2\\ln x}{x} - \\frac{1}{x}",
    '\\ln x = \\frac{1}{2}', 'y = (\\ln \\sqrt{e})^2 - \\ln \\sqrt{e} - 2 = -2.25',
    'S_{10} = 1.875 S_5', 'S_n = \\frac{a_1 \\cdot q^n}{q - 1}', '3152.5 = a_1(1.5^8 - 1)',
    '\\log_{2} 8 = 3', 'x \\to \\infty', 'x \\le 0', 'x \\geq \\sqrt{e}', 'a \\neq b',
    '2 \\cdot 3 = 5', '6 \\times 4', '\\pm 2', '(3, \\infty)', '[3, \\infty)', '|x - 2|',
    '\\left( \\frac{1}{e}, 0 \\right)', '30\\%', '45^\\circ', '\\angle ABC', '\\overline{AB}',
    'c^2 = a^2 + b^2', 'c = \\sqrt{3.6^2 + 4.8^2} = 6', '\\sqrt[3]{x + 1}',
    // convention 3 — a brace system
    '\\begin{cases} a_{10} = a_1 - 90 \\\\ a_{10} = a_1 + 9d \\end{cases}',
    // conventions 4 and 5 — framed answers and cancellations
    '\\boxed{x > 0}', '\\boxed{\\min(\\sqrt{e}, -2.25)}', '\\cancel{a_1} - 90 = \\cancel{a_1} + 9d',
    '(2a_1 + 9d) \\frac{\\cancel{10}}{\\cancel{2}} = 1.875 \\cdot (2a_1 + 4d) \\cdot \\frac{5}{2}',
    // convention 7 — sign-table marks
    '\\nearrow', '\\searrow', '\\cup', '\\cap',
];

describe('every prescribed construct renders in KaTeX AND opens in MathLive', () => {
    for (const body of CORPUS) {
        it(body, () => {
            expect(() => katex.renderToString(body, { throwOnError: true, strict: 'ignore' })).not.toThrow();
            expect(validateLatex(body)).toEqual([]);
        });
    }
});

/**
 * The engines do NOT agree on a broken span, and the design does not need them to: KaTeX
 * refuses an unclosed brace (the screen shows it raw, with a marker, and the backend
 * validator files an INFO), while MathLive opens it and closes the brace itself. Opening it
 * writes nothing (the editor compares against what the field reported at open — Δ14); only
 * an edit she makes is saved. Pinned so a future MathLive that starts refusing these is
 * noticed rather than discovered by a teacher.
 */
describe('a broken span: KaTeX refuses, MathLive tolerates', () => {
    for (const body of ['\\frac{1}{', 'x^{2', '\\sqrt{e']) {
        it(body, () => {
            expect(() => katex.renderToString(body, { throwOnError: true })).toThrow();
            expect(validateLatex(body)).toEqual([]);
        });
    }
});
