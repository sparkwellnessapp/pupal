/**
 * Parser for the rendered markdown format produced by the v3 DOCX pipeline.
 *
 * Tables are emitted as:
 *   [TABLE N: RxC]
 *   | header | header |
 *   |---|---|
 *   | cell | cell |
 *     [NESTED TABLE: RxC]        ← 2-space indent
 *     | nested header | ... |
 *     |---|---|
 *     | nested cell  | ... |
 *   | next main row | ... |
 */

export type NestedTableBlock = {
  label: string;
  afterRowIndex: number; // data row index (0-based, excluding header) after which this block appears
  rows: string[][];
};

export type TableSegment = {
  type: 'table';
  label: string;
  rows: string[][];      // first row is the header
  nestedTables: NestedTableBlock[];
  /**
   * The table's OWN direction, as stated by the source document (parser_render
   * reads OOXML `<w:tblPr><w:bidiVisual/>` and writes it into the marker). Cells
   * arrive in LOGICAL order, so this is what decides which end is column 1:
   * `rtl` ⇒ the first cell is the RIGHTMOST, exactly as Word lays it out.
   *
   * `undefined` only for legacy text whose marker predates the token — the
   * renderer then falls back to guessing from content, which is precisely the
   * behaviour this field exists to retire.
   */
  dir?: 'rtl' | 'ltr';
};

export type TextSegment = { type: 'text'; content: string };
export type ParsedSegment = TextSegment | TableSegment;

// The direction token is OPTIONAL so legacy text (markers written before the
// token existed) still parses — it simply arrives with `dir: undefined`.
const MAIN_TABLE_RE   = /^\[TABLE \d+: (\d+x\d+)(?:\s+(rtl|ltr))?\]$/;
const NESTED_TABLE_RE = /^ {2}\[NESTED TABLE: (\d+x\d+)(?:\s+(rtl|ltr))?\]$/;
// Separator lines like |---|---| or  |---|---| (indented)
const SEPARATOR_RE    = /^\s*\|[-\s|]+\|$/;
const MAIN_ROW_RE     = /^\|(.+)\|$/;
const NESTED_ROW_RE   = /^ {2}\|(.+)\|$/;

function parseCells(inner: string): string[] {
  return inner.split('|').map(c => c.trim());
}

function isSeparator(line: string): boolean {
  // A real header separator (|---|---|) contains DASHES. An all-blank pipe row
  // (|  |  |  |) is a data/scaffold row (e.g. an empty trace-table row the student
  // fills in) — it must NOT be swallowed as a separator, or the scaffold collapses
  // to header-only. Require a dash to disambiguate.
  return SEPARATOR_RE.test(line) && line.includes('-');
}

export function parseMarkdownText(text: string): ParsedSegment[] {
  const segments: ParsedSegment[] = [];
  const lines = text.split('\n');

  let textBuf: string[] = [];
  let currentTable: TableSegment | null = null;
  let currentNested: { label: string; rows: string[][] } | null = null;
  let nestedStartDataRowIdx = 0; // data row count when nested block started

  const flushText = () => {
    const content = textBuf.join('\n');
    if (content.trim()) segments.push({ type: 'text', content });
    textBuf = [];
  };

  const flushNested = () => {
    if (currentNested && currentTable) {
      currentTable.nestedTables.push({
        label: currentNested.label,
        afterRowIndex: nestedStartDataRowIdx - 1, // index of last data row before nested block
        rows: currentNested.rows,
      });
      currentNested = null;
    }
  };

  const flushTable = () => {
    flushNested();
    if (currentTable) {
      segments.push(currentTable);
      currentTable = null;
    }
  };

  for (const line of lines) {
    const mainMatch = MAIN_TABLE_RE.exec(line);
    const nestedMatch = NESTED_TABLE_RE.exec(line);

    if (mainMatch) {
      flushText();
      flushTable();
      currentTable = {
        type: 'table', label: mainMatch[1], rows: [], nestedTables: [],
        dir: mainMatch[2] as 'rtl' | 'ltr' | undefined,
      };
      continue;
    }

    if (currentTable) {
      if (nestedMatch) {
        flushNested();
        // data row count = rows.length - 1 (minus header), clamped to 0
        nestedStartDataRowIdx = Math.max(0, currentTable.rows.length - 1);
        currentNested = { label: nestedMatch[1], rows: [] };
        continue;
      }

      if (isSeparator(line)) continue;

      const nestedRowMatch = NESTED_ROW_RE.exec(line);
      if (nestedRowMatch && currentNested) {
        currentNested.rows.push(parseCells(nestedRowMatch[1]));
        continue;
      }

      const mainRowMatch = MAIN_ROW_RE.exec(line);
      if (mainRowMatch) {
        // A non-indented row after a nested block means the nested block ended
        flushNested();
        currentTable.rows.push(parseCells(mainRowMatch[1]));
        continue;
      }

      // Non-table line: end the current table
      flushTable();
      textBuf.push(line);
      continue;
    }

    textBuf.push(line);
  }

  flushText();
  flushTable();

  return segments;
}

/**
 * Detect whether a 2D grid of text is predominantly RTL (Hebrew) or LTR.
 * Mirrors the inferGridDir logic in RubricEditor.tsx.
 */
export function inferGridDir(grid: string[][]): 'rtl' | 'ltr' {
  const hebrewRe = /[֐-׿]/;
  const latinRe  = /[A-Za-z]/;
  for (const row of grid) {
    for (const cell of row) {
      const s = (cell ?? '').trim();
      if (!s) continue;
      if (hebrewRe.test(s)) return 'rtl';
      if (latinRe.test(s))  return 'ltr';
    }
  }
  return 'ltr';
}
