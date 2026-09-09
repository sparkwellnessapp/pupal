"""Normalized-exact create-or-pick for schools — ONE implementation, two callers.

Extracted verbatim (behavior-preserving) from `users.py::update_me` when
`PUT /users/me/schools` (migration 022, multi-school onboarding) became the
second caller. Two copies of a matching rule that must agree with a UNIQUE INDEX
is the duplicate-schema failure CLAUDE.md §0.4 is about.

Matching is NORMALIZED-EXACT, never fuzzy (the conservative student-match
precedent): two schools differing by one character are two schools. A fuzzy
match would merge real institutions with no way back.
"""
import logging
from typing import List, Optional, Sequence

from sqlalchemy import delete, func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.school import School, user_schools
from ..models.user import User
from .override_attribution import normalize_school_name


logger = logging.getLogger(__name__)


def _normalized_name_column():
    """The SQL half of the identity rule — byte-for-byte migration 018's index
    expression: lower(regexp_replace(btrim(name), '\\s+', ' ', 'g')).

    The lookup is expressed in SQL rather than by scanning every row into Python
    (what the single-school path used to do) for two reasons: it is the same
    expression the UNIQUE INDEX is built on, so the query can USE that index and
    can never disagree with it; and the multi-school write resolves N names per
    request, where an all-rows scan per name is N × the whole table.
    """
    return func.lower(func.regexp_replace(func.btrim(School.name), r"\s+", " ", "g"))


async def resolve_or_create_school(
    db: AsyncSession,
    name: str,
    city: Optional[str] = None,
    ministry_symbol: Optional[str] = None,
) -> School:
    """Return the School this pick refers to, creating it if there is none.

    IDENTITY LADDER (023) — two rules, and which one applies depends only on
    whether the caller could supply a Ministry symbol:

      * SYMBOL PRESENT → the symbol IS the identity. Look it up; create if
        absent. It never falls back to a name match (see below).
      * SYMBOL ABSENT  → normalized-exact NAME, exactly the pre-023 rule. A
        free-text school is all the evidence there is.

    WHY A SYMBOL NEVER ADOPTS A NAME MATCH. It is tempting to stamp the symbol
    onto an existing symbol-less row with the same name — "surely the same
    school". The real Ministry export says otherwise: 82 normalized names are
    shared by 213 institutions, and two «בית אקשטיין» rows share a city
    (320440 and 338384, both פרדס חנה-כרכור). A name match is therefore not
    evidence of identity, and adopting on it would invent precisely the identity
    this column exists to stop guessing at. The honest outcome is two rows — one
    known institution, one "a school someone typed" — rather than one row
    asserting something nobody verified. Reconciling them is an operator
    decision with evidence, never an automatic write.

    The returned School is FLUSHED but not committed — the caller owns the
    transaction (a single commit per request).

    On IntegrityError (a concurrent create) the insert is rolled back to a
    SAVEPOINT and the winner is re-read on whichever key applies. The savepoint
    matters: this function is called in a LOOP by the multi-school writer, and a
    session-wide `db.rollback()` there would silently discard the schools already
    resolved earlier in the same request.

    `city` is only ever used when CREATING. An existing row is never mutated to
    match the caller's spelling — quietly rewriting an institution's city because
    a second teacher typed it differently is exactly the silent-repair this
    product does not do.
    """
    symbol = (ministry_symbol or "").strip() or None
    key = normalize_school_name(name)
    if not key:
        raise ValueError("school name is empty after normalization")

    async def by_symbol() -> Optional[School]:
        return (
            await db.execute(select(School).where(School.ministry_symbol == symbol))
        ).scalar_one_or_none()

    async def by_name() -> Optional[School]:
        return (
            await db.execute(select(School).where(_normalized_name_column() == key))
        ).scalar_one_or_none()

    lookup = by_symbol if symbol else by_name

    existing = await lookup()
    if existing is not None:
        return existing

    # STORED as she typed it (trimmed only). Normalization decides IDENTITY, not
    # spelling: collapsing her internal spacing here would be the extraction
    # rewriting her input to match its own index, which is a different thing
    # from matching on it.
    school = School(name=name.strip(), city=(city or None), ministry_symbol=symbol)
    try:
        async with db.begin_nested():          # SAVEPOINT
            db.add(school)
            await db.flush()
    except IntegrityError:
        # A unique index caught a concurrent create — 023's symbol index, or
        # 018's name index. Re-read on the key that governs this call and use
        # the winner rather than failing a teacher's onboarding on a race.
        logger.info(
            "school create raced (symbol=%r name=%r); re-reading", symbol, key,
        )
        winner = await lookup()
        if winner is None:
            # The index fired but nothing matches under our own rule: the
            # conflict was a DIFFERENT constraint — e.g. a symbol-bearing pick
            # whose name collides with an existing symbol-less row under 018.
            # That collision is real and must be surfaced, not resolved by
            # handing back a row we cannot prove is the same institution.
            raise
        return winner

    return school


async def set_user_schools(
    db: AsyncSession,
    user: User,
    schools: Sequence[School],
) -> None:
    """Replace the teacher's junction rows with `schools`, IN ORDER, and move
    `users.school_id` (the PR-G6 attribution key) to the first of them.

    THE ONE WRITER of both surfaces. They encode one fact at two granularities —
    the junction is the full truth, the column is the single key drawn from it —
    and a second writer that moved one without the other would put a teacher's
    attribution in permanent disagreement with her own profile.

    The junction is written with explicit SQL rather than through the ORM
    relationship because the relationship is viewonly: `position` is a column a
    plain secondary-relationship write cannot populate, and position is what
    makes "schools[0] is the key" TRUE rather than merely usual.

    Does not commit — the caller owns the transaction.
    """
    await db.execute(delete(user_schools).where(user_schools.c.user_id == user.id))

    if schools:
        await db.execute(
            insert(user_schools),
            [
                {"user_id": user.id, "school_id": s.id, "position": i}
                for i, s in enumerate(schools)
            ],
        )

    user.school_id = schools[0].id if schools else None


async def ensure_user_school(db: AsyncSession, user: User, school: School) -> None:
    """Make `school` the attribution key, adding it to the junction if absent.

    A UNION, never a replacement: this serves the single-school endpoint, which
    answers "which school is primary" and is not entitled to infer that every
    OTHER school the teacher listed should be dropped.

    The new school takes position 0 (it IS the key now) and the others shift
    down, so the position column keeps telling the truth about which row the key
    points at.
    """
    rows = (
        await db.execute(
            select(user_schools.c.school_id)
            .where(user_schools.c.user_id == user.id)
            .order_by(user_schools.c.position)
        )
    ).scalars().all()

    ordered: List = [school.id] + [sid for sid in rows if sid != school.id]

    await db.execute(delete(user_schools).where(user_schools.c.user_id == user.id))
    await db.execute(
        insert(user_schools),
        [
            {"user_id": user.id, "school_id": sid, "position": i}
            for i, sid in enumerate(ordered)
        ],
    )

    user.school_id = school.id
