"""
Ruling 1 differential: `_verdict_inputs` (single) vs `_verdict_inputs_bulk`
must produce BYTE-IDENTICAL verdict inputs. "One definition, two call shapes"
is a claim, and this is what makes it verifiable rather than asserted.

The fixtures are deliberately ADVERSARIAL rather than representative (owner
steer): grouping-by-key only does real work where cases could plausibly
diverge, so the set is built out of exactly those —
  * a batch with NO class            (falls back to the all-students roster)
  * two batches SHARING one rubric across DIFFERENT classes
  * two batches sharing one CLASS but different rubrics
  * a class whose roster is EMPTY    (a real state: class created, nobody added)
  * a batch whose rubric row is MISSING (never compiled / deleted)
  * a duplicate batch id in the input list (the grouping must be idempotent)

No live DB: both paths run against one fake session that records every query,
so the test also measures the query count the ruling asked for.
"""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.api.v0 import batch_grading as bg


class _Student:
    def __init__(self, name: str, sid: UUID | None = None):
        self.id = sid or uuid4()
        self.full_name = name

    def __eq__(self, other):           # identity by id: byte-identical inputs
        return isinstance(other, _Student) and other.id == self.id

    def __repr__(self):
        return f"<S {self.full_name}>"


class _Rubric:
    def __init__(self, rid: UUID, contract_json):
        self.id = rid
        self.contract_json = contract_json


class _Batch:
    def __init__(self, class_id, rubric_id, bid=None):
        self.id = bid or uuid4()
        self.class_id = class_id
        self.rubric_id = rubric_id


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeDB:
    """Answers the three query shapes the helpers issue, and counts them."""

    def __init__(self, memberships, all_students, rubrics):
        self.memberships = memberships      # class_id -> [students] (SQL order)
        self.all_students = all_students
        self.rubrics = rubrics              # rubric_id -> _Rubric
        self.queries: list[str] = []

    async def execute(self, stmt):
        sql = str(stmt)
        self.queries.append(sql)
        if "class_memberships" in sql or "JOIN" in sql.upper():
            cid = list(stmt.compile().params.values())[0]
            return _Result(self.memberships.get(cid, []))
        if "rubrics" in sql:
            # SQLAlchemy renders `.in_([...])` as ONE expanding parameter, so
            # the values arrive as a nested list — flatten before matching.
            # (The first version of this double missed that, handed the bulk
            # path zero rubrics, and the differential caught it immediately:
            # the double was wrong, not the code.)
            ids: list[UUID] = []
            for v in stmt.compile().params.values():
                if isinstance(v, UUID):
                    ids.append(v)
                elif isinstance(v, (list, tuple, set)):
                    ids.extend(x for x in v if isinstance(x, UUID))
            return _Result([self.rubrics[i] for i in ids if i in self.rubrics])
        return _Result(self.all_students)

    async def get(self, model, pk):
        return self.rubrics.get(pk)


@pytest.fixture(autouse=True)
def stub_groups(monkeypatch):
    """The differential is about ROUTING — which rubric's groups reach which
    batch — not about the contract parser. A deterministic stub keyed by the
    contract makes a mis-routed rubric a visible failure instead of hiding
    behind two empty lists."""
    def _fake(contract_json):
        if not contract_json:
            return []
        if contract_json.get("boom"):
            raise ValueError("corrupt contract")
        return [f"groups::{contract_json.get('tag')}"]
    monkeypatch.setattr(bg, "answer_space_groups", _fake)


@pytest.fixture
def world():
    c_alef, c_bet, c_empty = uuid4(), uuid4(), uuid4()
    r_shared, r_other, r_missing = uuid4(), uuid4(), uuid4()

    alef = [_Student("אבigail"), _Student("בן"), _Student("גיל")]
    bet = [_Student("דנה"), _Student("הדר")]
    every = alef + bet + [_Student("ותיק ללא כיתה")]

    db = _FakeDB(
        memberships={c_alef: alef, c_bet: bet, c_empty: []},
        all_students=every,
        rubrics={
            r_shared: _Rubric(r_shared, {"tag": "shared"}),
            r_other: _Rubric(r_other, {"tag": "other"}),
            # r_missing deliberately absent
        },
    )
    batches = [
        _Batch(None, r_shared),        # no class → all-students roster
        _Batch(c_alef, r_shared),      # shared rubric, class א
        _Batch(c_bet, r_shared),       # shared rubric, class ב  (same rubric, different class)
        _Batch(c_alef, r_other),       # same class, different rubric
        _Batch(c_empty, r_shared),     # empty roster
        _Batch(c_bet, r_missing),      # rubric row missing
    ]
    batches.append(batches[0])         # duplicate id — grouping must be idempotent
    return db, batches


@pytest.mark.asyncio
async def test_bulk_matches_single_on_every_adversarial_batch(world):
    db, batches = world
    user_id = uuid4()

    bulk, degraded = await bg._verdict_inputs_bulk(db, batches, user_id)
    assert degraded == set(), 'healthy fixtures must not degrade'

    for b in batches:
        single_roster, single_groups = await bg._verdict_inputs(db, b, user_id)
        bulk_roster, bulk_groups = bulk[b.id]
        assert bulk_roster == single_roster, f"roster differs for batch {b.id}"
        assert [s.full_name for s in bulk_roster] == [s.full_name for s in single_roster], (
            "roster ORDER differs — Postgres collation for Hebrew names is not "
            "Python's sorted(); the bulk path must reuse the same SQL"
        )
        assert bulk_groups == single_groups, f"selection groups differ for batch {b.id}"


@pytest.mark.asyncio
async def test_bulk_groups_by_key_not_by_batch(world):
    """The whole point of the bulk shape: query count scales with DISTINCT
    classes + rubrics, not with batches. 7 batch entries (6 distinct) over
    3 classes + a class-less batch must not issue 7 roster queries."""
    db, batches = world
    db.queries.clear()
    await bg._verdict_inputs_bulk(db, batches, uuid4())
    # 3 class rosters + 1 all-students + 1 rubric IN-query = 5
    assert len(db.queries) == 5, db.queries


@pytest.mark.asyncio
async def test_single_path_cost_is_the_baseline_the_bulk_path_beats(world):
    """Records the ruling's requested comparison at realistic scale."""
    db, batches = world
    db.queries.clear()
    for b in batches:
        await bg._verdict_inputs(db, b, uuid4())
    per_batch = len(db.queries)
    db.queries.clear()
    await bg._verdict_inputs_bulk(db, batches, uuid4())
    assert len(db.queries) < per_batch


@pytest.mark.asyncio
async def test_shared_rubric_routes_the_same_groups_to_every_batch_using_it(world):
    """The grouping's real risk: collapsing by rubric_id then handing a batch
    the WRONG rubric's groups. Two batches share r_shared across DIFFERENT
    classes — same groups, different rosters."""
    db, batches = world
    bulk, _ = await bg._verdict_inputs_bulk(db, batches, uuid4())
    shared = [b for b in batches if bulk[b.id][1] == ["groups::shared"]]
    assert len(shared) >= 3                      # no-class, class א, class ב, empty-class
    rosters = {tuple(s.full_name for s in bulk[b.id][0]) for b in shared}
    assert len(rosters) > 1, "same rubric must NOT collapse different class rosters"


@pytest.mark.asyncio
async def test_corrupt_contract_degrades_only_its_own_rubric(world):
    """The one deliberate divergence, pinned: on the LIST a malformed contract
    must not blind the teacher to every other batch. The single path stays
    loud (get_batch is the grading path); here it degrades to [] for the
    offending rubric ALONE."""
    db, batches = world
    bad_rid = uuid4()
    db.rubrics[bad_rid] = _Rubric(bad_rid, {"boom": True})
    batches = batches + [_Batch(None, bad_rid)]

    bulk, degraded = await bg._verdict_inputs_bulk(db, batches, uuid4())

    bad = batches[-1]
    # The batch is REPORTED as degraded so the caller omits its count rather
    # than publishing one computed against empty selection groups (which would
    # over-count: every "choose k of N" empty would read as a missing answer).
    assert bad.id in degraded
    assert bulk[bad.id][0], "the roster is still resolved for the bad batch"
    # every other batch is unharmed and NOT marked degraded
    healthy = [b for b in batches[:-1] if b.rubric_id != bad_rid]
    assert all(b.id not in degraded for b in healthy)
    assert any(bulk[b.id][1] == ["groups::shared"] for b in healthy)


@pytest.mark.asyncio
async def test_single_path_stays_loud_on_a_corrupt_contract(world):
    """Proof the divergence is CONFINED: get_batch's path must still raise."""
    db, batches = world
    bad_rid = uuid4()
    db.rubrics[bad_rid] = _Rubric(bad_rid, {"boom": True})
    with pytest.raises(ValueError):
        await bg._verdict_inputs(db, _Batch(None, bad_rid), uuid4())
