"""The structural check on a math answer (MATH_RENDERING_PLAN §4, "Validation after P1").

Pure and deterministic. It reports; it never repairs. A finding becomes ONE INFO
annotation on the answer (the engine adapter words it), and the review surface shows a
span the renderer cannot draw as raw text with a marker — no text is ever dropped.

It is NOT a triage reason. `code_lint` showed what a check that fires on most documents
does to trust (owner ruling 2026-09-06): it becomes one only after its false-flag rate
is measured on real documents.

What it checks, per the conventions (docs/math-rendering/TRANSCRIPTION_GT_CONVENTIONS_MATH.md):
  unclosed_span        a `\\(` that never closes
  stray_close          a `\\)` with no open span
  unbalanced_braces    `{`/`}` that do not pair inside a span (`\\{`, `\\}` excluded)
  env_mismatch         `\\begin{x}` closed by `\\end{y}`, or left open
  forbidden_env        `aligned`, `align`, `gather`, … — they merge written lines into
                       one, which breaks P2's line slicing and the one-line rule (§4.3)
  display_math         `\\[ … \\]` or `$$` — the convention is `\\( … \\)` only
  command_outside_span a LaTeX command in the prose, outside any span
  hebrew_in_span       Hebrew inside a span — it reverses in every renderer (render test)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple

from .spans import split_math
from .tokens import tokenize

FORBIDDEN_ENVS = frozenset({
    "aligned", "align", "align*", "alignat", "alignat*", "gather", "gather*", "gathered",
    "eqnarray", "eqnarray*", "multline", "multline*", "split", "flalign", "flalign*",
})

_HEBREW = re.compile(r"[֐-׿]")
# A command in prose: backslash + letters. `\(` / `\)` are delimiters, not commands, and
# never reach here because only text segments are scanned.
_COMMAND = re.compile(r"\\[A-Za-z]+")
_DISPLAY = re.compile(r"\\\[|\\\]|\$\$")


@dataclass(frozen=True)
class Issue:
    code: str
    offset: int        # into the answer string
    detail: str = ""


def _env_issues(body: str, base: int) -> List[Issue]:
    issues: List[Issue] = []
    stack: List[Tuple[str, int]] = []
    toks = tokenize(body)
    pos = 0
    offsets = []
    for _, val in toks:
        offsets.append(pos)
        pos += len(val)
    for i, (kind, val) in enumerate(toks):
        if kind != "cw" or val not in ("\\begin", "\\end"):
            continue
        # read the `{name}` that follows
        j = i + 1
        name = ""
        if j < len(toks) and toks[j] == ("ch", "{"):
            j += 1
            while j < len(toks) and toks[j] != ("ch", "}"):
                name += toks[j][1]
                j += 1
        name = name.strip()
        at = base + offsets[i]
        if val == "\\begin":
            if name in FORBIDDEN_ENVS:
                issues.append(Issue("forbidden_env", at, name))
            stack.append((name, at))
        else:
            if not stack or stack[-1][0] != name:
                issues.append(Issue("env_mismatch", at, name))
                if stack:
                    stack.pop()
            else:
                stack.pop()
    for name, at in stack:
        issues.append(Issue("env_mismatch", at, name))
    return issues


def _brace_issue(body: str, base: int) -> List[Issue]:
    depth = 0
    for kind, val in tokenize(body):
        if kind != "ch":
            continue          # `\{` and `\}` are control symbols: literal braces
        if val == "{":
            depth += 1
        elif val == "}":
            depth -= 1
            if depth < 0:
                return [Issue("unbalanced_braces", base, "-1")]
    return [Issue("unbalanced_braces", base, f"+{depth}")] if depth else []


def check_math_answer(text: str) -> List[Issue]:
    """Every structural problem in one answer, in order of position."""
    text = text or ""
    res = split_math(text)
    issues: List[Issue] = [Issue("unclosed_span", at) for at in res.unclosed_at]
    issues += [Issue("stray_close", at) for at in res.stray_close_at]
    for seg in res.segments:
        if seg.kind == "math":
            body = seg.body(text)
            issues += _brace_issue(body, seg.start)
            issues += _env_issues(body, seg.body_start)
            m = _HEBREW.search(body)
            if m:
                issues.append(Issue("hebrew_in_span", seg.body_start + m.start()))
        else:
            chunk = text[seg.start:seg.end]
            for m in _DISPLAY.finditer(chunk):
                issues.append(Issue("display_math", seg.start + m.start(), m.group(0)))
            # Inside an unclosed span the "prose" is really math; its commands are already
            # reported once, as the unclosed span — do not report them again.
            if any(seg.start <= at < seg.end for at in res.unclosed_at):
                continue
            for m in _COMMAND.finditer(chunk):
                issues.append(Issue("command_outside_span", seg.start + m.start(), m.group(0)))
    return sorted(issues, key=lambda i: i.offset)
