"""
parsing.py — the ONE defensive parser for VLM JSON output (D2: parse failures
are a v0 metric, so parsing returns an outcome, never raises on bad model text).

exam_spec — the minimal question-structure artifact Phase 2 consumes.
Two sources:
  (a) canonical harness JSON ({"questions":[{"number", "sub_questions",
      "context"}]}), hand-authored or exported;
  (b) best-effort extraction from a rubric draft_json placed at the suite root
      (ExtractRubricResponse-shaped). The adapter is deliberately tolerant and
      FAILS LOUDLY when it cannot find question structure — never guesses.
Phase 1 has no dependency on any of this.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def parse_model_json(text: str, *, required_keys: tuple[str, ...]) -> tuple[bool, dict]:
    """Strip code fences -> json.loads -> top-level shape check.

    Returns (ok, data). Never raises on malformed model output.
    """
    cleaned = _FENCE_RE.sub("", text or "").strip()
    if not cleaned:
        return False, {}
    # Tolerate prose around a JSON object: take the outermost braces span.
    if not cleaned.startswith("{"):
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return False, {}
        cleaned = cleaned[start:end + 1]
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return False, {}
    if not isinstance(data, dict):
        return False, {}
    if any(k not in data for k in required_keys):
        return False, {}
    return True, data


# ---------------------------------------------------------------------------
# Exam spec
# ---------------------------------------------------------------------------

# Caps keep the prompt lean: the question-level context carries class skeletons;
# each sub-question signature names the method it expects (the method name sits at
# the start of the prompt text, well within the cap).
_SIG_CAP = 600
_CONTEXT_CAP = 1500


@dataclass(frozen=True)
class ExamSubQuestion:
    """A sub-question's id PLUS its content signature — the prompt / expected
    method that identifies which transcribed code block answers it (e.g.
    `LowestRateChannel`). P2 routes BY this signature; without it P2 can only
    guess sub-question order, which is the omer Q2.ב↔ג swap / yonatan Q2.ג drop."""
    id: str
    signature: str = ""


@dataclass(frozen=True)
class ExamQuestion:
    number: int
    sub_questions: tuple[ExamSubQuestion, ...]   # may be empty (no sub-questions)
    context: str                                 # free text: identifiers/classes the spec names


def _canonical_subq(s) -> ExamSubQuestion:
    """A canonical sub_question is a bare id string OR an {id, signature} object."""
    if isinstance(s, dict):
        return ExamSubQuestion(
            id=str(s.get("id") or s.get("sub_question_id") or "").strip(),
            signature=str(s.get("signature") or s.get("text") or "").strip()[:_SIG_CAP],
        )
    return ExamSubQuestion(id=str(s), signature="")


# Identifier shapes worth correcting toward: camelCase / PascalCase / any token
# carrying an internal capital, plus Capitalized words >=3 chars. This captures
# graded names (Hobby, TvShow, hobbyName, GetArrShows, LowestRateChannel) and
# deliberately omits short all-lowercase attribute names (name/rate/chl) — those
# collide with common English words and would be a false-fix source; hand-add
# them via the canonical spec's "identifiers" field if a fixture needs them.
_SPEC_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_CSHARP_KW = frozenset({
    "abstract", "as", "base", "bool", "break", "byte", "case", "catch", "char",
    "class", "const", "continue", "decimal", "default", "do", "double", "else",
    "enum", "false", "float", "for", "foreach", "if", "in", "int", "interface",
    "internal", "is", "long", "namespace", "new", "null", "object", "out",
    "override", "private", "protected", "public", "readonly", "ref", "return",
    "sbyte", "sealed", "short", "static", "string", "struct", "switch", "this",
    "throw", "true", "try", "uint", "ulong", "ushort", "using", "var", "virtual",
    "void", "volatile", "while",
})


def _extract_identifiers(*texts: str) -> frozenset[str]:
    """Identifier-shaped tokens from spec text; keywords excluded."""
    out: set[str] = set()
    for text in texts:
        for m in _SPEC_IDENT_RE.finditer(text or ""):
            tok = m.group(0)
            if tok.lower() in _CSHARP_KW or len(tok) < 3:
                continue
            has_internal_cap = any(c.isupper() for c in tok[1:])
            starts_cap = tok[0].isupper()
            if has_internal_cap or starts_cap:
                out.add(tok)
    return frozenset(out)


@dataclass(frozen=True)
class ExamSpec:
    name: str
    questions: tuple[ExamQuestion, ...]
    identifiers: frozenset[str] = frozenset()  # spec-defined names (correction targets)

    def to_prompt_json(self) -> str:
        return json.dumps(
            {
                "questions": [
                    {
                        "number": q.number,
                        "sub_questions": [
                            {"id": sq.id, "signature": sq.signature}
                            for sq in q.sub_questions
                        ],
                        "context": q.context,
                    }
                    for q in self.questions
                ]
            },
            ensure_ascii=False,
            indent=1,
        )


def load_exam_spec(path: str | Path) -> ExamSpec:
    """Load the canonical harness exam-spec JSON."""
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    qs = data.get("questions")
    if not isinstance(qs, list) or not qs:
        raise ValueError(f"{p.name}: no 'questions' list — not a canonical exam spec.")
    questions = tuple(
        ExamQuestion(
            number=int(q["number"]),
            sub_questions=tuple(_canonical_subq(s) for s in q.get("sub_questions", [])),
            context=str(q.get("context", "")),
        )
        for q in qs
    )
    # Explicit "identifiers" field (hand-authored control) unioned with what we
    # can extract from the context strings AND the sub-question signatures.
    explicit = frozenset(str(s) for s in data.get("identifiers", []) or [])
    extracted = _extract_identifiers(
        *(q.context for q in questions),
        *(sq.signature for q in questions for sq in q.sub_questions),
    )
    return ExamSpec(name=p.stem, questions=questions,
                    identifiers=explicit | extracted)


def spec_from_rubric_draft(path: str | Path) -> ExamSpec:
    """Best-effort ExamSpec from a rubric draft_json FILE. See
    spec_from_rubric_draft_data for the shape rules."""
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    return spec_from_rubric_draft_data(data, name=p.stem)


def spec_from_rubric_draft_data(data: dict, *, name: str) -> ExamSpec:
    """Best-effort ExamSpec from a rubric draft_json dict (ExtractRubricResponse-ish).

    Looks for a top-level 'questions' list; per question, a number-like field
    and a sub-question list with id/letter-like fields. Context is assembled
    from name/title/description-ish strings found on the question. Raises
    ValueError (loudly, with what it saw) rather than guessing.
    """
    qs = data.get("questions") if isinstance(data, dict) else None
    if not isinstance(qs, list) or not qs:
        raise ValueError(
            f"{name}: expected a top-level 'questions' list in the rubric "
            f"draft_json; found keys {sorted(data) if isinstance(data, dict) else type(data)}."
        )

    def first_str(d: dict, keys: tuple[str, ...]) -> str:
        for k in keys:
            v = d.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return ""

    questions: list[ExamQuestion] = []
    for i, q in enumerate(qs, start=1):
        if not isinstance(q, dict):
            raise ValueError(f"{name}: question #{i} is not an object.")
        num_raw = q.get("question_number", q.get("number", i))
        try:
            number = int(re.sub(r"\D", "", str(num_raw)) or i)
        except ValueError:
            number = i
        subs: list[ExamSubQuestion] = []
        for sq in q.get("sub_questions") or []:
            if isinstance(sq, dict):
                label = first_str(sq, ("sub_question_id", "id", "letter", "label", "name"))
                if label:
                    # The sub-question's prompt text IS its content signature — it
                    # names the method to implement ("כתבו פעולה בשם LowestRateChannel
                    # ..."). This is the per-sub-question signal P2 needs to route
                    # `ב` vs `ג` by content instead of guessing order.
                    sig = first_str(sq, ("text", "question_text", "description", "name", "title"))
                    subs.append(ExamSubQuestion(id=label, signature=sig[:_SIG_CAP]))
        context = first_str(q, ("name", "title", "question_text", "description"))[:_CONTEXT_CAP]
        questions.append(ExamQuestion(
            number=number,
            sub_questions=tuple(subs),
            context=context,
        ))
    return ExamSpec(
        name=name, questions=tuple(questions),
        identifiers=_extract_identifiers(
            *(q.context for q in questions),
            *(sq.signature for q in questions for sq in q.sub_questions),
        ),
    )
