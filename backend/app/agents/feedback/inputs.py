"""
What the feedback writer is told about each scope, and the basis its text is
stamped with — ONE place, for the first write (`attach_feedback`, at grade time)
and every rewrite (`POST /feedback/regenerate`), on v5 and v6 drafts alike.

There used to be two: the runner described a v6 scope from its own block while
the regenerate endpoint described every draft through the v5 renderer, which
reads checks a v6 envelope does not carry — so a v6 rewrite told the model
«אין בדיקות לסעיף זה» for every question and got generic prose back.

THE BASIS (staleness is derived, never a remembered flag — OD-G4.1):
  * v5 — the ordered effective verdict vector (`staleness.basis_hash`).
  * v6 — the hash of the scope's priced description itself (`render_scope_v6`):
    the label of the option that priced each check, the evidence, the charged
    faults. It is exactly what the text was written from, so the text is stale
    precisely when what it describes has moved under her decisions.

Her criterion notes go INTO the model's input (so the prose never repeats or
contradicts them) but NOT into the basis: they are printed beside the feedback,
and writing a note does not make the description of the work out of date.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from app.agents.feedback.prompt import render_scope_for_feedback, render_scope_v6
from app.agents.feedback.staleness import basis_hash, flatten_checks

# What a v6 text was stamped with before v6 had a basis of its own: the v5 hash
# of an empty verdict vector (a v6 envelope carries no checks). A text carrying
# it was written at grade time from VIVI's price — that is the only writer that
# ever produced it — so its basis is recoverable exactly, never guessed.
LEGACY_V6_BASIS = basis_hash([])


@dataclass(frozen=True)
class ScopeInput:
    scope_id: str
    rendered: str           # the model's input for this scope
    basis: str              # what the text written from it is stamped with


def scope_id_of(scope_outcome) -> str:
    return (scope_outcome.question_id if scope_outcome.sub_question_id is None
            else f"{scope_outcome.question_id}.{scope_outcome.sub_question_id}")


def written_scopes(draft) -> List[Tuple[str, object]]:
    """The scopes feedback is written for: only those the LLM graded have
    verdicts to describe, and [D-6] never one a selection group excluded."""
    return [(scope_id_of(so), so) for so in draft.scope_outcomes if so.graded_by == "llm"]


def v6_basis(described: str) -> str:
    return hashlib.sha256(described.encode("utf-8")).hexdigest()


def _criterion_descriptions(draft) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for so in draft.scope_outcomes:
        for co in so.criterion_outcomes:
            if co.sub_criterion_outcomes:
                for sub in co.sub_criterion_outcomes:
                    out[sub.sub_criterion_id] = sub.description or ""
            else:
                out[co.criterion_id] = co.description or ""
    return out


def _notes_block(notes: List[Tuple[str, str]]) -> str:
    if not notes:
        return ""
    lines = ["", "הערות שהמורה כתב/ה לתלמיד/ה על הסעיף (יודפסו לתלמיד/ה בנפרד, "
                 "ליד המשוב — אין לחזור עליהן ואין לסתור אותן):"]
    lines += [f"- «{description}»: {note}" if description else f"- {note}"
              for description, note in notes]
    return "\n".join(lines)


def feedback_inputs(draft, overrides=None) -> List[ScopeInput]:
    """[(scope, model input, basis)] for every written scope, in document order,
    described under HER current decisions (`overrides`). At grade time there are
    none, so the description is Vivi's own price."""
    from app.schemas.graded_test_draft_v6 import v6_content
    content = v6_content(draft)
    scopes = written_scopes(draft)
    if content is None:
        return [ScopeInput(sid, render_scope_for_feedback(so), basis_hash(list(flatten_checks(so))))
                for sid, so in scopes]

    from app.services.pricing_v6 import price
    from app.services.v6_review import criterion_notes, overlay_of
    overlay = overlay_of(overrides)
    priced = price(content.to_view(), overlay)
    notes = criterion_notes(content, overlay)
    described = _criterion_descriptions(draft) if notes else {}
    out = []
    for sid, so in scopes:
        key = (so.question_id, so.sub_question_id)
        in_scope = {t.terminal_id for t in content.view_terminals
                    if (t.question_id, t.sub_question_id) == key}
        text = render_scope_v6(content, priced, key)
        mine = [(described.get(t.terminal_id, ""), notes[t.terminal_id])
                for t in content.terminals if t.terminal_id in in_scope and t.terminal_id in notes]
        out.append(ScopeInput(sid, text + _notes_block(mine), v6_basis(text)))
    return out


def stale_feedback_scopes(draft, overrides) -> List[str]:
    """[v6] the scopes whose Vivi-written feedback no longer describes the grade
    under her decisions. Her own words are not judged here (the surface never
    calls them stale); a scope with no Vivi text has nothing to be stale.

    Returns [] for a v5 draft — its surface derives staleness itself."""
    from app.schemas.graded_test_draft_v6 import v6_content
    content = v6_content(draft)
    block = draft.feedback
    if content is None or block is None:
        return []
    current = {i.scope_id: i.basis for i in feedback_inputs(draft, overrides)}
    vivi: Optional[Dict[str, str]] = None
    out = []
    for sid, basis in current.items():
        text = block.scopes.get(sid)
        if text is None or not text.text.strip():
            continue
        stored = text.basis_hash
        if not stored or stored == LEGACY_V6_BASIS:
            if vivi is None:
                vivi = {i.scope_id: i.basis for i in feedback_inputs(draft, None)}
            stored = vivi.get(sid, stored)
        if stored != basis:
            out.append(sid)
    return out
