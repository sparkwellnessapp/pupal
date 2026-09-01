"""
P-0 — stable criterion identity (owner ruling 2026-09-01).

`criterion_id` is POSITIONAL: `f"{qid}.{sid}.c{i}"` over `enumerate(...)`.
Insert one criterion and every later id shifts, so anything that references a
criterion durably — a layer-1 ruling anchor, `TeacherOverride.check_id` under
CW-3, the audit key — silently re-attaches to a DIFFERENT criterion. One root
cause under three features.

`uid` is the machine identity: a server-minted UUID4 that survives inserts,
reorders and edits. `criterion_id` is unchanged and remains the display/path
identity — nothing about how a human refers to `q1.ב.c4` changes.

Three rules, and they are the whole design:

  * **The server mints, never the client.** A client-minted id is a
    client-controlled database key. The frontend carries unmodelled wire fields
    verbatim through its `_carry` bag (CLAUDE.md §11), so a carried `uid`
    survives an untouched open→save as structural identity with no editor
    change at all.
  * **Backfill is idempotent.** A criterion arriving without a `uid` gets one at
    save/compile. That is what covers the six existing production rubrics on
    their next compile, with no data migration.
  * **Delete-and-recreate mints a NEW uid.** Re-adding "the same" criterion is a
    new criterion. Silently re-attaching old rulings to it would be the
    positional bug wearing a different hat.
"""
from __future__ import annotations

import uuid
from typing import Iterable, List


def new_uid() -> str:
    return str(uuid.uuid4())


def _walk_criteria(node) -> Iterable:
    """Every criterion and sub-criterion reachable from a question or
    sub-question, at any depth."""
    for criterion in getattr(node, "criteria", None) or []:
        yield criterion
        for sub in (getattr(criterion, "sub_criteria", None) or []):
            yield sub
    for child in getattr(node, "sub_questions", None) or []:
        yield from _walk_criteria(child)


def ensure_uids(questions: List) -> int:
    """Mint a `uid` for every criterion/sub-criterion lacking one, in place.

    Returns how many were minted — 0 on the second call over the same tree,
    which is the idempotence the backfill depends on.

    Called at BOTH save and compile: the draft must carry the identity too, or
    a ruling anchored during review would not survive to the contract.
    """
    minted = 0
    for question in questions or []:
        for node in _walk_criteria(question):
            if not getattr(node, "uid", None):
                node.uid = new_uid()
                minted += 1
    return minted


def uid_map(questions: List) -> dict:
    """`uid -> criterion_id`, for resolving a durable reference to today's path.

    A ruling stores the uid; the editor and every annotation speak
    `criterion_id`. This is the only place the two are related, so a positional
    shift changes the VALUE here and nothing else.
    """
    out = {}
    for question in questions or []:
        for node in _walk_criteria(question):
            key = getattr(node, "uid", None)
            if key:
                out[key] = getattr(node, "criterion_id", None) or getattr(
                    node, "sub_criterion_id", None)
    return out


def duplicate_uids(questions: List) -> List[str]:
    """Uids appearing more than once. A duplicate makes a durable reference
    ambiguous, which is worse than having none — it resolves, to the wrong
    thing."""
    seen, dupes = set(), []
    for question in questions or []:
        for node in _walk_criteria(question):
            key = getattr(node, "uid", None)
            if not key:
                continue
            if key in seen and key not in dupes:
                dupes.append(key)
            seen.add(key)
    return dupes
