"""
P-0 — stable criterion identity (owner ruling 2026-09-01).

`criterion_id` is positional: `f"{qid}.{sid}.c{i}"` over `enumerate(...)`.
Insert one criterion and every later id shifts, so a durable reference — a
layer-1 ruling anchor, `TeacherOverride.check_id` under CW-3, the audit key —
silently re-attaches to a DIFFERENT criterion. One root cause under three
features, which is why it is fixed once, here.

These tests are the identity-preservation set the ruling names. Each asserts a
property of the IDENTITY, never of the path: `criterion_id` is expected to move.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.schemas.ontology_types import Criterion, Question, QuestionType, SubCriterion
from app.services.criterion_identity import (
    duplicate_uids, ensure_uids, new_uid, uid_map)


def _criterion(cid, points="2", subs=None):
    return Criterion(
        criterion_id=cid, index=0, description=f"desc {cid}",
        points=Decimal(points),
        sub_criteria=[
            SubCriterion(sub_criterion_id=f"{cid}.sc{i}", index=i,
                         description=f"sub {i}", points=Decimal(p))
            for i, p in enumerate(subs)
        ] if subs else None)


def _question(criteria):
    return Question(question_id="q1", question_type=QuestionType.CODING_TASK,
                    total_points=sum(c.points for c in criteria),
                    criteria=criteria, sub_questions=[])


# ---------------------------------------------------------------------------
# uid-is-unique-within-a-rubric
# ---------------------------------------------------------------------------

def test_uids_are_unique_within_a_rubric():
    q = _question([_criterion("q1.c0"), _criterion("q1.c1", subs=["1", "1"])])
    ensure_uids([q])
    assert not duplicate_uids([q])

    everything = [q.criteria[0].uid, q.criteria[1].uid,
                  *[s.uid for s in q.criteria[1].sub_criteria]]
    assert len(set(everything)) == 4, "sub-criteria must get their own identity"


def test_a_duplicate_uid_is_reported_not_repaired():
    """Ambiguous is worse than absent: a duplicate RESOLVES, to the wrong
    criterion. The compiler refuses rather than picking one."""
    q = _question([_criterion("q1.c0"), _criterion("q1.c1")])
    ensure_uids([q])
    q.criteria[1].uid = q.criteria[0].uid
    assert duplicate_uids([q]) == [q.criteria[0].uid]


# ---------------------------------------------------------------------------
# backfill-is-idempotent
# ---------------------------------------------------------------------------

def test_backfill_is_idempotent():
    """The six production rubrics predate uids and are backfilled on their next
    compile. Compiling twice must mint nothing the second time, or every
    recompile would orphan every ruling."""
    q = _question([_criterion("q1.c0"), _criterion("q1.c1", subs=["1", "1"])])

    assert ensure_uids([q]) == 4, "first pass mints for criteria AND sub-criteria"
    before = uid_map([q])
    assert ensure_uids([q]) == 0, "second pass minted again — not idempotent"
    assert uid_map([q]) == before


def test_backfill_only_fills_the_gaps():
    q = _question([_criterion("q1.c0"), _criterion("q1.c1")])
    q.criteria[0].uid = "already-here"
    assert ensure_uids([q]) == 1
    assert q.criteria[0].uid == "already-here", "an existing identity was replaced"


# ---------------------------------------------------------------------------
# reorder-preserves · insert-shifts-the-path-not-the-identity
# ---------------------------------------------------------------------------

def test_reorder_preserves_every_uid():
    q = _question([_criterion("q1.c0"), _criterion("q1.c1"), _criterion("q1.c2")])
    ensure_uids([q])
    before = [c.uid for c in q.criteria]

    q.criteria.reverse()
    assert ensure_uids([q]) == 0, "reordering must not look like new criteria"
    assert [c.uid for c in q.criteria] == list(reversed(before))


def test_an_insert_shifts_the_path_but_never_the_identity():
    """THE bug this exists for. Inserting at position 0 renumbers every
    criterion_id; the uids must not move, or every durable reference silently
    re-targets."""
    q = _question([_criterion("q1.c0"), _criterion("q1.c1")])
    ensure_uids([q])
    kept = {c.criterion_id: c.uid for c in q.criteria}

    inserted = _criterion("q1.cNEW")
    q.criteria.insert(0, inserted)
    assert ensure_uids([q]) == 1, "exactly the new criterion should mint"

    # the editor renumbers paths; identities do not follow
    for i, c in enumerate(q.criteria):
        c.criterion_id = f"q1.c{i}"
    assert q.criteria[1].uid == kept["q1.c0"], (
        "after an insert, the old first criterion's identity moved with its path")
    assert q.criteria[2].uid == kept["q1.c1"]
    assert inserted.uid not in kept.values()


def test_delete_and_recreate_mints_a_new_uid():
    """Re-adding "the same" criterion is a NEW criterion. Re-attaching old
    rulings to it would be the positional bug wearing a different hat."""
    q = _question([_criterion("q1.c0"), _criterion("q1.c1")])
    ensure_uids([q])
    gone = q.criteria[0].uid

    q.criteria.pop(0)
    q.criteria.insert(0, _criterion("q1.c0"))
    ensure_uids([q])
    assert q.criteria[0].uid != gone


# ---------------------------------------------------------------------------
# uid-survives-open-save-compile · contract-carries-uid
# ---------------------------------------------------------------------------

def test_uid_survives_a_serialisation_round_trip_byte_for_byte():
    """An untouched open→save is a structural identity. If `uid` did not
    round-trip, every save would orphan every ruling on that rubric."""
    q = _question([_criterion("q1.c0", subs=["1", "1"])])
    ensure_uids([q])
    before = uid_map([q])

    revived = Question.model_validate(q.model_dump(mode="json"))
    assert uid_map([revived]) == before
    assert ensure_uids([revived]) == 0, "a round trip lost the identity"


def test_the_compiler_carries_uid_into_the_frozen_contract():
    """The contract is the artefact a ruling anchors to. If `uid` stopped at the
    draft, the anchor could not be resolved against what actually compiles."""
    from tests.grading_eval_suite.fixtures import load_bundle

    contract = load_bundle("dan_basiuk").rubric_contract
    from app.services.criterion_identity import _walk_criteria

    nodes = [n for q in contract.questions for n in _walk_criteria(q)]
    assert nodes, "fixture precondition: the contract has criteria"
    assert all(hasattr(n, "uid") for n in nodes), (
        "the frozen contract does not carry the uid field")


def test_the_compiler_backfills_a_rubric_that_predates_uids():
    """The six production rubrics have no uids. Their next compile must mint
    them — no data migration, and the compiler is the single place it happens."""
    from app.schemas.ontology_types import ExtractRubricResponse
    from app.services.contract_compiler import ContractCompiler

    q = _question([_criterion("q1.c0", points="4")])
    q.total_points = Decimal("4")
    assert all(c.uid is None for c in q.criteria), "precondition: no uids"

    draft = ExtractRubricResponse(rubric_name="legacy", subject="computer_science",
                                  total_points=Decimal("4"), questions=[q])
    try:
        ContractCompiler().compile(draft)
    except Exception:
        # compilation may fail on unrelated invariants for this minimal draft;
        # the backfill happens first and is what is under test
        pass
    assert all(c.uid for c in q.criteria), "compile did not backfill the uid"


def test_new_uid_is_a_uuid4():
    import uuid

    parsed = uuid.UUID(new_uid())
    assert parsed.version == 4
