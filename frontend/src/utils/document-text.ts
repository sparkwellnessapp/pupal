/**
 * PR-5 Design Recovery — pure text-shaping for the document mirror (Phases 2.1–2.3).
 *
 * The production pipeline (`parser_render.py`) emits markers into question text:
 *   [TABLE N: RxC] + markdown pipe rows   → parsed by markdown-parser.ts (reused)
 *   [IMAGE: filename]                      → an unreadable-image placeholder
 *   [[color:RRGGBB]]text[[/color]]         → teacher ink; markers stripped (color
 *                                            discipline: red is reserved for blocking)
 * plus embedded code and Latin runs inside Hebrew prose. This module owns the PURE
 * decisions (marker stripping, code-run grouping, image detection); the React
 * renderer (DocumentText.tsx) composes them with the existing parseMarkdownText.
 *
 * Everything here is pure and unit-tested. NEVER mutates input.
 */

const COLOR_OPEN_RE = /\[\[color:[0-9A-Fa-f]{6}\]\]/g;
const COLOR_CLOSE_RE = /\[\[\/color\]\]/g;
const HL_OPEN_RE = /\[\[hl:[^\]]*\]\]/g;
const HL_CLOSE_RE = /\[\[\/hl\]\]/g;
const IMAGE_LINE_RE = /^\s*\[IMAGE:\s*(.*?)\]\s*$/;

/**
 * Strip teacher-ink markers — `[[color:RRGGBB]]…[[/color]]` AND `[[hl:name]]…[[/hl]]`
 * — keeping the inner text verbatim. Both are parser_render annotations for
 * teacher-touched ink (contrasting-color pen, highlighter); the tokens must never
 * reach a rendered cell, but the value they wrap is real content and is kept.
 */
export function stripColorMarkers(text: string): string {
    return text
        .replace(COLOR_OPEN_RE, '').replace(COLOR_CLOSE_RE, '')
        .replace(HL_OPEN_RE, '').replace(HL_CLOSE_RE, '');
}

/** If a line is exactly an `[IMAGE: name]` marker, return the name; else null. */
export function imageMarkerName(line: string): string | null {
    const m = IMAGE_LINE_RE.exec(line);
    return m ? (m[1].trim() || 'תמונה') : null;
}

const HEBREW_RE = /[֐-׿]/;
const CODE_KEYWORD_RE = /^(public|private|protected|internal|static|void|int|bool|boolean|string|double|float|char|long|var|for|foreach|while|do|if|else|switch|case|return|class|struct|interface|new|using|namespace|import|def|function|const|let)\b/;

/** A line whose content STARTS as a comment — it belongs to the code around it. */
const COMMENT_LINE_RE = /^(?:\/\/|\/\*|\*\/|\*\s)/;

/**
 * The EXECUTABLE skeleton of a line: comments and string literals removed.
 *
 * This is the load-bearing idea behind `isCodeLine`. Hebrew inside a `//` comment
 * or inside a "…" literal is ANNOTATION or DATA — it says nothing about whether
 * the line is code. Teachers write Hebrew comments in their answer keys constantly
 * (`private TvShow [] arrShows;   // כל תוכניות הטלויזיה`), and judging such a line
 * by "does it contain Hebrew anywhere" tore their class bodies in half.
 *
 * String literals collapse to an EMPTY pair rather than vanishing, so the line
 * keeps its syntactic shape: `Console.WriteLine("שלום");` → `Console.WriteLine("");`
 * still ends in `;` and still looks like a statement.
 *
 * Order matters: block comments, then strings, then the `//` tail — so a `//` living
 * inside a string ("http://…") is consumed as a string and cannot truncate the line.
 *
 * Only `//` and `/* *\/` are treated as comment syntax (C#/Java/C++, the subjects we
 * ship). `#` is deliberately NOT, because Hebrew prose says "בשפת #C" constantly.
 */
function codeSkeleton(line: string): string {
    return line
        .replace(/\/\*[\s\S]*?\*\//g, ' ')
        .replace(/"(?:[^"\\]|\\.)*"/g, '""')
        .replace(/'(?:[^'\\]|\\.)*'/g, "''")
        .replace(/\/\/.*$/, '')
        .trim();
}

/**
 * Is this line code (not Hebrew prose)? Strong signals on its SKELETON: a
 * brace-only line, a trailing `;`, a leading language keyword, or symbol density —
 * and no Hebrew in the executable part. Blank lines are NOT code (the grouper
 * treats them as run continuation).
 *
 * A comment-only line counts as code so a Hebrew `// בנאי` cannot split a class
 * body. That is safe against false positives because `groupTextBlocks` demotes any
 * code run shorter than two non-blank lines back to prose — so a lone Hebrew
 * remark floating in real prose still renders as prose.
 */
export function isCodeLine(line: string): boolean {
    const t = line.trim();
    if (!t) return false;
    if (COMMENT_LINE_RE.test(t)) return true;        // a comment belongs to its code
    const c = codeSkeleton(t);
    if (!c) return false;
    if (HEBREW_RE.test(c)) return false;             // Hebrew in the CODE ⇒ prose
    if (/^[{}()[\]]+$/.test(c)) return true;         // structural brace/paren line
    if (/;\s*$/.test(c)) return true;                // statement terminator
    if (CODE_KEYWORD_RE.test(c)) return true;        // language keyword
    const symbols = (c.match(/[(){}\[\];=<>+\-*/%&|]/g) ?? []).length;
    return symbols >= 3;                             // symbol-dense Latin line
}

/**
 * BLOCK-level code detection for a whole text run.
 *
 * Unlike `isCodeLine`, this deliberately TOLERATES Hebrew: a C# answer key
 * routinely carries Hebrew `//` comments, and it must render as ONE LTR code
 * block rather than fragmenting into alternating code/prose islands. So the
 * decision is made over the run as a whole — count the lines carrying a code
 * signal (brace-only, statement terminator, comment marker, leading keyword) and
 * ask whether they dominate.
 *
 * Two lines of signal, or 40% of the run, is enough: a real solution has many;
 * Hebrew prose ("תשובה: הפעולה מקבלת מערך…") has none.
 */
const CODE_SIGNAL_RE = /^[{}()[\]]+$|;\s*$/;

export function looksLikeCode(text: string): boolean {
    const lines = text.split('\n').map((l) => l.trim()).filter(Boolean);
    if (lines.length === 0) return false;
    // Same skeleton rule as isCodeLine, so the two agree about what "code" means:
    // a Hebrew comment tail must not hide the `;` that makes a line a statement.
    const signals = lines.filter((l) => {
        if (COMMENT_LINE_RE.test(l)) return true;
        const c = codeSkeleton(l);
        return !!c && (CODE_SIGNAL_RE.test(c) || CODE_KEYWORD_RE.test(c));
    }).length;
    return signals >= 2 || signals / lines.length >= 0.4;
}

export type TextBlock =
    | { kind: 'code'; text: string }
    | { kind: 'image'; name: string }
    | { kind: 'prose'; text: string };

/**
 * Group a text segment's lines into ordered blocks: consecutive code lines fuse
 * into ONE code block (killing the airy line-per-paragraph rendering), `[IMAGE]`
 * lines become image blocks, everything else is prose. A code run of fewer than
 * two non-blank lines is demoted to prose (a lone Latin line isn't a code block) —
 * precision-biased, like the table parser.
 */
export function groupTextBlocks(text: string): TextBlock[] {
    const lines = text.split('\n');
    const raw: TextBlock[] = [];
    let mode: 'code' | 'prose' | null = null;
    let buf: string[] = [];

    const flush = () => {
        if (buf.length === 0) return;
        // trim trailing blank lines off a block
        while (buf.length && !buf[buf.length - 1].trim()) buf.pop();
        if (buf.length) raw.push({ kind: mode === 'code' ? 'code' : 'prose', text: buf.join('\n') });
        buf = [];
    };

    for (const line of lines) {
        const img = imageMarkerName(line);
        if (img !== null) { flush(); mode = null; raw.push({ kind: 'image', name: img }); continue; }

        const blank = !line.trim();
        if (blank) { buf.push(line); continue; }   // blank extends the current run

        const want: 'code' | 'prose' = isCodeLine(line) ? 'code' : 'prose';
        if (mode !== null && mode !== want) flush();
        mode = want;
        buf.push(line);
    }
    flush();

    // Demote weak code blocks (< 2 non-blank lines) back to prose.
    return raw.map((b) => {
        if (b.kind !== 'code') return b;
        const nonBlank = b.text.split('\n').filter((l) => l.trim()).length;
        return nonBlank >= 2 ? b : { kind: 'prose', text: b.text };
    });
}

/**
 * Split a string into alternating Hebrew and Latin/code runs, so a renderer can
 * wrap the Latin runs in a bidi-isolating element (`<bdi dir="ltr">`) — killing
 * the "Check (arr, 6)B" mangling class where RTL reorders code internals.
 * Returns runs in order; `latin: true` marks the ones to isolate.
 */
export function bidiRuns(text: string): Array<{ text: string; latin: boolean }> {
    // An LTR run starts at a Latin letter OR A DIGIT and extends through following
    // code-ish chars (digits, brackets, operators, dots) so identifiers, calls AND
    // arithmetic stay intact.
    //
    // Digits matter as much as letters here: a line like "0 + 8 + 4 + 15 = 76" has
    // NO strong character at all, so inside an RTL paragraph the bidi algorithm
    // lays its neutrals out right-to-left and the teacher's arithmetic renders
    // BACKWARDS ("76 = 15 + 4 + 8 + 0"). Isolating it as one LTR run preserves the
    // order she wrote while the paragraph keeps its RTL alignment.
    //
    // The trailing `(?:\s+[…]+)*` lets a run span the spaces INSIDE an expression
    // ("0 + 8") but never past a Hebrew word — the group needs a code-ish char
    // after the space, which Hebrew is not. So "הפעולה Check מחזירה" still yields
    // the bare run "Check", with no trailing space.
    const CODEISH = "[A-Za-z0-9_.,:;!?'\"()\\[\\]{}<>+\\-*/%=&|]";
    const re = new RegExp(`[A-Za-z0-9]${CODEISH}*(?:\\s+${CODEISH}+)*`, 'g');
    const runs: Array<{ text: string; latin: boolean }> = [];
    let last = 0;
    let m: RegExpExecArray | null;
    while ((m = re.exec(text))) {
        if (m.index > last) runs.push({ text: text.slice(last, m.index), latin: false });
        runs.push({ text: m[0], latin: true });
        last = m.index + m[0].length;
    }
    if (last < text.length) runs.push({ text: text.slice(last), latin: false });
    return runs;
}
