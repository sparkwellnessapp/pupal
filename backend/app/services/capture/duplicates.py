"""
Duplicate submissions — DERIVED, never stored (SCN-13, owner-ruled 2026-11-01).

Two saved submissions in one batch that claim the same student are ONE
decision for the teacher: which set of photos to keep. The pairing used to be
a sticky `student_state='conflict'` on the LATER submission, re-matched at
read time by "same student id, or same typed name" — and the two halves of
that match could drift apart. Approving the earlier one's typed name moved it
from a NAME claim to an ID claim, the later one kept its name claim, and the
pair split: the resolve dialog showed one photo, and «keep this one» answered
422 because the half it held had no student (production, 2026-10-30/31).

So the group is a pure function of what the batch holds NOW:

  * submissions with the same student id are one group;
  * submissions with the same typed name (no student yet) are one group.

A typed name is never matched to a STUDENT here (OD-B6: never on a name
match): a typed name joins a student's sets only when the teacher links it
to that student, and the group is then formed by her decision.

Only saved, non-discarded submissions are claims (an opened-and-abandoned
draft is not one — the 2026-10-24 rule). A group of one is no group.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.capture import CaptureSubmission
from ..batch_triage import normalize_name


@dataclass(frozen=True)
class Claim:
    submission_id: UUID
    student_id: Optional[UUID]
    #: what was typed on the link — a claim only while there is no student
    pending_name: Optional[str]


def duplicate_groups(claims: Sequence[Claim]) -> dict[UUID, tuple[UUID, ...]]:
    """submission id → its group (ids sorted), for every submission in a group
    of two or more. Absent ⇒ not a duplicate."""
    parent = {c.submission_id: c.submission_id for c in claims}

    def find(x: UUID) -> UUID:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: UUID, b: UUID) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    by_claim: dict[tuple[str, object], list[UUID]] = {}
    for c in claims:
        if c.student_id is not None:
            key: tuple[str, object] = ("student", c.student_id)
        elif c.pending_name and normalize_name(c.pending_name):
            key = ("typed", normalize_name(c.pending_name))
        else:
            continue                              # claims no one
        by_claim.setdefault(key, []).append(c.submission_id)
    for ids in by_claim.values():
        for other in ids[1:]:
            union(ids[0], other)

    members: dict[UUID, list[UUID]] = {}
    for c in claims:
        members.setdefault(find(c.submission_id), []).append(c.submission_id)
    out: dict[UUID, tuple[UUID, ...]] = {}
    for ids in members.values():
        if len(ids) > 1:
            group = tuple(sorted(ids))
            for i in ids:
                out[i] = group
    return out


def claimant_count(claims: Sequence[Claim]) -> int:
    """How many STUDENTS the saved submissions stand for: a group is one."""
    groups = duplicate_groups(claims)
    return len({groups.get(c.submission_id, (c.submission_id,)) for c in claims})


async def batch_claims(db: AsyncSession, batch_ids: Iterable[UUID]) -> dict[UUID, list[Claim]]:
    """batch id → every saved, non-discarded submission of it, as a claim.
    ONE statement, however many batches."""
    ids = list(set(batch_ids))
    if not ids:
        return {}
    rows = (await db.execute(
        select(CaptureSubmission.id, CaptureSubmission.batch_id, CaptureSubmission.student_id,
               CaptureSubmission.pending_student_name)
        .where(CaptureSubmission.batch_id.in_(ids), CaptureSubmission.status == "saved")
        .order_by(CaptureSubmission.id)
    )).all()
    out: dict[UUID, list[Claim]] = {}
    for sid, batch_id, student_id, pending in rows:
        out.setdefault(batch_id, []).append(Claim(
            submission_id=sid, student_id=student_id, pending_name=pending))
    return out


async def groups_in(db: AsyncSession, batch_ids: Iterable[UUID]) -> dict[UUID, tuple[UUID, ...]]:
    """The unresolved duplicate groups of these batches. Groups never cross a
    batch: a submission's claims are judged within its own batch only."""
    out: dict[UUID, tuple[UUID, ...]] = {}
    for claims in (await batch_claims(db, batch_ids)).values():
        out.update(duplicate_groups(claims))
    return out
