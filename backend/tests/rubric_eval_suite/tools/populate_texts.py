"""
GT text populator — the deterministic slicer for PR-1 (text-fidelity instrument).

Populates `question_text` / `sq.text` in benchmarks/*.json from the RENDERER
output of the fixture DOCX (`parser_render.render_docx_to_markdown`) — never
hand-typed, never the raw XML walk. Hand-editing of text fields is banned;
GT must equal what a correct extraction of the render looks like.

NORMATIVE CONVENTIONS (§2 of the PR-1 spec; copied verbatim into GT_AUDIT.md):
  1. question_text = render lines from the line AFTER the question header
     (שאלה N ...) up to (exclusive) the first sub-question marker line, or —
     when the question has no sub-questions — up to the first boundary line.
     The header line itself is EXCLUDED.
  2. sq.text = render lines from the sub-question's MARKER LINE (INCLUSIVE)
     up to the next sibling marker, first nested-part marker, or boundary.
     Nested (inner) sub-questions: identical rule one level down.
  3. Boundary set (first hit ends the span): next שאלה N header; a line
     starting מחוון; the start of a rubric table; a color-marked
     solution/scoring line (פתרון/תשובה/ניקוד in red); end of document.
  4. Red ink is excluded from text spans. Fully-red lines are dropped;
     red spans inside black lines have the marked TEXT removed.
  5. Tables inside a question span are question content, encoded as cell
     text: per row, non-empty cell texts joined by single spaces; rows
     joined by newlines; pipe syntax stripped.
  6. [IMAGE] markers are kept verbatim as rendered.
  7. No prose for a node -> text stays null (never empty string).
  8. Color markup tokens are stripped; no Unicode pre-normalization.

RULINGS (uniform, document-level; surfaced as open items in the PR description):
  R1  A line whose visible text begins with פתרון or תשובה is a boundary
      regardless of ink color. §2.3's "in red" describes the common case;
      ownership of solution content is content-based, and hobby_tvshow labels
      its image-only solutions with a BLACK "פתרון:" line. Without R1 those
      solution blocks would leak into the preceding sub-question's text.
  R2  Struck-through spans (~~...~~) are removed like red ink. Precedent: the
      locked strike-resolution convention on the criteria side (csharp Q1
      6->8, 18->20, 4->0-drop) treats struck ink as retracted. Affects
      bagrut q4.ב only (a retracted task sentence whose red replacement is
      excluded by convention 4).
  R3  A Hebrew-letter sub-question marker line ends the running span even when
      the label has NO GT node. GT equals what a correct extraction of the
      render looks like, and the model sees the marker regardless of GT
      structure: in hobby_tvshow q2 the render has a ג. task while GT
      (faithful to the mislabeled rubric table) has only א/ב — without R3,
      ג's task text would be baked into GT ב.text, a span no convention could
      teach the model to produce. The unowned text belongs to no GT node.
      Deliberately NOT extended to numeric markers: digits at line start are
      routinely task list items (bagrut q5.ב's הערות 1./2.), and numeric
      nested parts are delimiters only where GT expects a nested child.

UNRESOLVABLE SPANS are detected (missing markers, ambiguous structure) or
declared in OPEN_RULINGS below; they stay null and are listed in the preview.
Detection cases:
  - GT node whose marker does not exist in the render (e.g. bagrut q1.א has a
    "(1)" nested marker but no "(2)"; q1.ב / q3.ב have no nested markers).
  - GT branch node whose children have no markers: the branch's own span end
    ("first nested-part marker") is unobservable, and populating the branch
    with its children's content would lock a convention PR-2 cannot teach.
  - Question with GT sub-questions but no sub-question markers anywhere
    (foundations_cs q1/q3: tasks are unmarked paragraphs; the only סעיף lines
    are inline-מחוון scoring headers, not task markers).

Default mode: PREVIEW (prints per node: path, source line range, char count,
head/tail, plus all unresolved spans). --write: writes the benchmark JSONs
(only after the preview has been reviewed; only question_text/text fields
are touched). Deterministic and idempotent.

Run: PYTHONPATH=. python tests/rubric_eval_suite/tools/populate_texts.py [--write]
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SUITE = Path(__file__).resolve().parents[1]
FIXTURES = SUITE / "fixtures"
BENCHMARKS = SUITE / "benchmarks"

# Spans that ARE mechanically resolvable under §2 but are ruled OPEN because the
# mechanical result would be wrong-by-inspection and §2 offers no exclusion rule.
# Key: (fixture, node_path). These stay null and are listed in the preview.
OPEN_RULINGS: Dict[Tuple[str, str], str] = {
    ("foundations_cs", "q2"): (
        "span (task prose -> מחוון boundary) contains the full model-solution "
        "code as an unlabeled black 1x1 table; §2 has no exclusion for unlabeled "
        "solution tables — populating would embed the solution in question_text"
    ),
}

_COLOR_TOKEN = re.compile(r"\[\[color:[0-9A-Fa-f]{6}\]\]|\[\[/color\]\]")
_STRIKE = re.compile(r"~~.*?~~")
_Q_HEADER = re.compile(r"^שאלה\s+(\d+)\b")
_TABLE_LABEL = re.compile(r"^\s*\[(?:TABLE \d+|NESTED TABLE)")
_ROW_SEP = re.compile(r"^\s*\|[\s\-|]*\|?\s*$")
_UNESCAPED_PIPE = re.compile(r"(?<!\\)\|")
_HEB_MARKER = re.compile(r"^\s*[א-ת]\s*[.)]\s")   # R3: universal span delimiter


@dataclass
class Line:
    raw: str
    visible: str      # color tokens stripped, all content kept
    black: str        # red-marked content REMOVED (and strikes removed, R2)
    fully_red: bool   # has visible content, none of it black


def analyze(render: str) -> List[Line]:
    """Per-line color analysis with a running open-span state (color spans can
    cross line breaks: the renderer emits <w:br> inside one [[color]] span)."""
    out: List[Line] = []
    in_red = False
    for raw in render.split("\n"):
        segs: List[Tuple[bool, str]] = []
        pos, red = 0, in_red
        for m in _COLOR_TOKEN.finditer(raw):
            if m.start() > pos:
                segs.append((red, raw[pos:m.start()]))
            red = not m.group(0).startswith("[[/")
            pos = m.end()
        if pos < len(raw):
            segs.append((red, raw[pos:]))
        in_red = red
        visible = "".join(t for _, t in segs)
        black = _STRIKE.sub("", "".join(t for r, t in segs if not r))
        fully_red = bool(visible.strip()) and not black.strip()
        out.append(Line(raw=raw, visible=visible, black=black, fully_red=fully_red))
    return out


def is_rubric_table(lines: List[Line], label_idx: int) -> bool:
    """A rubric table's header row names the criterion/points columns
    (רכיב + ניקוד/נקודות/נק'). Context tables (data arrays, interface tables,
    trace scaffolds, code cells) do not."""
    for ln in lines[label_idx + 1:label_idx + 3]:
        s = ln.visible.strip()
        if s.startswith("|"):
            return ("רכיב" in s) and any(t in s for t in ("ניקוד", "נקודות", "נק"))
    return False


def is_boundary(lines: List[Line], i: int) -> bool:
    s = lines[i].visible.strip()
    if s.startswith("מחוון"):
        return True
    if s.startswith("פתרון") or s.startswith("תשובה"):   # R1: any ink color
        return True
    if lines[i].fully_red and s.startswith("ניקוד"):
        return True
    if _TABLE_LABEL.match(lines[i].visible) and is_rubric_table(lines, i):
        return True
    return False


Pos = Tuple[int, int]  # (line index, column in .visible)


def find_marker(lines: List[Line], label: str, start: Pos, end_line: int) -> Optional[Pos]:
    """Locate the marker line for a GT label at/after `start` (prose lines only)."""
    if re.fullmatch(r"\d+", label):
        pats = [re.compile(r"\(\s*" + re.escape(label) + r"\s*\)"),
                re.compile(r"^\s*" + re.escape(label) + r"[.)]\s")]
    else:
        pats = [re.compile(r"^\s*" + re.escape(label) + r"\s*[.)]\s")]
    for i in range(start[0], end_line):
        v = lines[i].visible
        if v.lstrip().startswith(("|", "[")):     # table rows/labels, images, textboxes
            continue
        for p in pats:
            m = p.search(v)
            if m and (i > start[0] or m.start() >= start[1]):
                return (i, m.start())
    return None


def encode_table_row(black_line: str) -> Optional[str]:
    cells = [c.replace("\\|", "|").strip() for c in _UNESCAPED_PIPE.split(black_line)]
    cells = [c for c in cells if c]
    return " ".join(cells) if cells else None


def assemble(lines: List[Line], start: Pos, end: Pos, issues: List[str]) -> Optional[str]:
    """§2.4/5/6/8: red + struck ink out, tables cell-encoded, images verbatim,
    blank lines dropped. `end` is EXCLUSIVE: (line, 0) stops before that line;
    (line, col) slices that line up to col. Partial-line slices are only legal
    on markup-free lines (true throughout the current corpus; asserted)."""
    out: List[str] = []
    last = end[0] if end[1] > 0 else end[0] - 1
    for i in range(start[0], min(last + 1, len(lines))):
        ln = lines[i]
        lo = start[1] if i == start[0] else 0
        hi = end[1] if (i == end[0] and end[1] > 0) else None
        if (lo > 0 or hi is not None) and (
                _COLOR_TOKEN.search(ln.raw) or "~~" in ln.raw):
            issues.append(f"line {i + 1}: partial-line slice on a marked-up line — skipped")
            continue
        text = ln.black[lo:hi] if (lo > 0 or hi is not None) else ln.black
        stripped = text.strip()
        if not stripped:
            continue
        if _TABLE_LABEL.match(text):
            continue                       # table label line: structure, not content
        if stripped.startswith("|"):
            if _ROW_SEP.match(text):
                continue
            row = encode_table_row(stripped)
            if row:
                out.append(row)
            continue
        out.append(stripped)
    joined = "\n".join(out).strip()
    if "[[color:" in joined or "[[/color]]" in joined or "~~" in joined:
        issues.append("markup tokens survived assembly — span left null")
        return None
    return joined or None


@dataclass
class NodeResult:
    path: str
    text: Optional[str] = None
    span: Optional[Tuple[int, int]] = None    # 1-based inclusive line range, for review
    open_reason: Optional[str] = None
    issues: List[str] = field(default_factory=list)


def marker_only(text: Optional[str], label: str) -> bool:
    return bool(text) and re.fullmatch(re.escape(label) + r"\s*[.)]?", text.strip()) is not None


def slice_fixture(name: str, gt: dict, render: str) -> List[NodeResult]:
    lines = analyze(render)
    headers: Dict[int, int] = {}
    for i, ln in enumerate(lines):
        m = _Q_HEADER.match(ln.visible.strip())
        if m:
            headers.setdefault(int(m.group(1)), i)

    results: List[NodeResult] = []
    header_lines = sorted(headers.values())

    for q in gt["questions"]:
        qnum = int(re.sub(r"\D", "", q["question_id"]))
        qpath = q["question_id"]
        if qnum not in headers:
            results.append(NodeResult(qpath, open_reason=f"no 'שאלה {qnum}' header found"))
            continue
        h = headers[qnum]
        region_end = min([hl for hl in header_lines if hl > h], default=len(lines))

        # ---- locate every GT node's marker (order-enforced, depth-first) ----
        markers: Dict[str, Pos] = {}
        unfound: Dict[str, str] = {}

        def locate(children: List[dict], parent_pos: Pos, prefix: str):
            pos = parent_pos
            for sq in children:
                label = sq["sub_question_id"]
                path = f"{prefix}.{label}"
                m = find_marker(lines, label, pos, region_end)
                if m is None:
                    unfound[path] = f"no marker for label '{label}' in render lines {pos[0] + 1}–{region_end}"
                    for inner in sq.get("sub_questions") or []:
                        unfound[f"{path}.{inner['sub_question_id']}"] = "parent marker unresolved"
                    continue
                markers[path] = m
                pos = m
                locate(sq.get("sub_questions") or [], m, path)

        locate(q.get("sub_questions") or [], (h + 1, 0), qpath)
        marker_positions = sorted(markers.values())
        marker_lines = {p[0] for p in marker_positions}   # lines holding a GT marker

        def span_end(start: Pos) -> Pos:
            nxt = [p for p in marker_positions if p > start]
            cand = nxt[0] if nxt else (region_end, 0)
            for i in range(start[0] + 1, cand[0] + 1):
                if i >= region_end:
                    break
                stray = _HEB_MARKER.match(lines[i].visible) and i not in marker_lines
                if (is_boundary(lines, i) or stray) and (i, 0) < cand:
                    cand = (i, 0)
                    break
            return cand

        def emit(path: str, label: Optional[str], start: Pos, is_branch: bool,
                 children: List[dict]) -> NodeResult:
            nr = NodeResult(path)
            if (name, path) in OPEN_RULINGS:
                nr.open_reason = OPEN_RULINGS[(name, path)]
                return nr
            if is_branch:
                child_found = [f"{path}.{c['sub_question_id']}" in markers for c in children]
                if not any(child_found):
                    nr.open_reason = ("branch node: no nested-part markers found — the "
                                      "'first nested-part marker' span end is unobservable")
                    return nr
            end = span_end(start)
            nr.span = (start[0] + 1, end[0] + (1 if end[1] > 0 else 0))
            nr.text = assemble(lines, start, end, nr.issues)
            if label and marker_only(nr.text, label):
                nr.text = None
            return nr

        # ---- question_text (convention 1): header+1 -> first marker/boundary ----
        has_subs = bool(q.get("sub_questions"))
        if (name, qpath) in OPEN_RULINGS:
            results.append(NodeResult(qpath, open_reason=OPEN_RULINGS[(name, qpath)]))
        elif has_subs and not markers:
            results.append(NodeResult(
                qpath, open_reason="question has GT sub-questions but no markers exist in the render"))
        else:
            results.append(emit(qpath, None, (h + 1, 0), False, []))

        # ---- sub-question / nested texts (convention 2) ----
        def walk(children: List[dict], prefix: str):
            for sq in children:
                label = sq["sub_question_id"]
                path = f"{prefix}.{label}"
                inner = sq.get("sub_questions") or []
                if path in unfound:
                    results.append(NodeResult(path, open_reason=unfound[path]))
                else:
                    results.append(emit(path, label, markers[path], bool(inner), inner))
                walk(inner, path)

        walk(q.get("sub_questions") or [], qpath)

        for path, reason in unfound.items():
            if not any(r.path == path for r in results):
                results.append(NodeResult(path, open_reason=reason))

    return results


# ---------------------------------------------------------------------------
# apply / preview
# ---------------------------------------------------------------------------

def apply_to_gt(gt: dict, results: List[NodeResult]) -> None:
    by_path = {r.path: r for r in results}

    def set_sq(node: dict, path: str):
        r = by_path.get(path)
        node["text"] = r.text if r else None
        for inner in node.get("sub_questions") or []:
            set_sq(inner, f"{path}.{inner['sub_question_id']}")

    for q in gt["questions"]:
        r = by_path.get(q["question_id"])
        q["question_text"] = r.text if r else None
        for sq in q.get("sub_questions") or []:
            set_sq(sq, f"{q['question_id']}.{sq['sub_question_id']}")


def preview(name: str, results: List[NodeResult]) -> None:
    print(f"\n=== {name} " + "=" * max(0, 60 - len(name)))
    for r in results:
        if r.open_reason:
            continue
        rng = f"lines {r.span[0]}–{r.span[1]}" if r.span else "—"
        if r.text is None:
            print(f"  {r.path:<14} {rng:<16} NULL (no prose in span)")
        else:
            head = r.text[:60].replace("\n", "⏎")
            tail = r.text[-60:].replace("\n", "⏎")
            print(f"  {r.path:<14} {rng:<16} {len(r.text):>5} chars")
            print(f"      head: {head}")
            if len(r.text) > 60:
                print(f"      tail: {tail}")
        for iss in r.issues:
            print(f"      [issue] {iss}")
    opened = [r for r in results if r.open_reason]
    if opened:
        print(f"  -- OPEN ITEMS ({len(opened)}) — left null --")
        for r in opened:
            print(f"  OPEN {r.path}: {r.open_reason}")


def main():
    ap = argparse.ArgumentParser(description="Populate GT question/sub-question texts from renders")
    ap.add_argument("--write", action="store_true", help="write benchmarks (after preview review)")
    args = ap.parse_args()

    import logging
    logging.disable(logging.CRITICAL)
    from app.services.docx_v3 import parser_render

    total_open = 0
    for gt_path in sorted(BENCHMARKS.glob("*.json")):
        name = gt_path.stem
        docx = FIXTURES / f"{name}.docx"
        if not docx.exists():
            print(f"[skip] {name}: no fixture DOCX")
            continue
        render = parser_render.render_docx_to_markdown(docx.read_bytes())
        gt = json.loads(gt_path.read_text(encoding="utf-8"))
        results = slice_fixture(name, gt, render)
        preview(name, results)
        total_open += sum(1 for r in results if r.open_reason)
        if args.write:
            apply_to_gt(gt, results)
            gt_path.write_text(json.dumps(gt, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
            # the written GT must still be type-valid (schema drift tripwire)
            from app.schemas.ontology_types import ExtractRubricResponse
            ExtractRubricResponse.model_validate_json(gt_path.read_text(encoding="utf-8"))
            print(f"  [written+validated] {gt_path.name}")

    print(f"\n[done] open items across suite: {total_open}"
          + ("" if args.write else "   (preview only — re-run with --write to apply)"))


if __name__ == "__main__":
    main()
