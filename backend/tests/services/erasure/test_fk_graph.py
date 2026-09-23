"""
The constraint graph the purge stands on, read from the LIVE test database at
test time — never from the census text, which is a snapshot (PURGE_CENSUS §1).

  PRV-8  NoSilentCascade — every FK whose REFERENCING table is one of the five
         student-data tables has delete_rule NO ACTION or RESTRICT; a direct
         delete of any parent with dependents present raises and deletes nothing.
  AM-B1  (final) keyed on tables, not edges: FKs to rubrics / users /
         grading_batches and the chain self-FKs included; regraded_to_id keeps
         DEFERRABLE INITIALLY DEFERRED; class_memberships keeps its cascades.
  AM-B4  tenant consistency enforced by the database: UNIQUE (id, user_id) on
         students and transcriptions, and four *_tenant_fkey composite FKs,
         mirrored in the ORM's __table_args__.
  §16.1  FK-graph completeness — every table with an FK path to students /
         graded_tests / transcriptions is covered by the purge plan.

RED until migration 032.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests.services.erasure.seed import add_pdf, row_counts, session

FIVE = ("students", "transcriptions", "graded_tests", "graded_test_pdfs", "transcription_jobs")

# One row per constraint (not per column): information_schema, as ruled.
DELETE_RULES = """
    SELECT tc.table_name, tc.constraint_name, rc.delete_rule,
           tc.is_deferrable, tc.initially_deferred
      FROM information_schema.table_constraints tc
      JOIN information_schema.referential_constraints rc
        ON rc.constraint_name = tc.constraint_name
       AND rc.constraint_schema = tc.table_schema
     WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public'
"""

# Columns of every FK, in order, with the referenced table and columns.
FK_COLUMNS = """
    SELECT c.conname, src.relname AS table_name, dst.relname AS ref_table,
           ARRAY(SELECT a.attname FROM unnest(c.conkey) WITH ORDINALITY k(n, i)
                   JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.n
                  ORDER BY k.i) AS cols,
           ARRAY(SELECT a.attname FROM unnest(c.confkey) WITH ORDINALITY k(n, i)
                   JOIN pg_attribute a ON a.attrelid = c.confrelid AND a.attnum = k.n
                  ORDER BY k.i) AS ref_cols,
           c.confdeltype
      FROM pg_constraint c
      JOIN pg_class src ON src.oid = c.conrelid
      JOIN pg_class dst ON dst.oid = c.confrelid
      JOIN pg_namespace n ON n.oid = src.relnamespace
     WHERE c.contype = 'f' AND n.nspname = 'public'
"""


async def _rules() -> list[dict]:
    async with session() as db:
        return [dict(r._mapping) for r in (await db.execute(text(DELETE_RULES))).all()]


async def _fk_columns() -> list[dict]:
    async with session() as db:
        return [dict(r._mapping) for r in (await db.execute(text(FK_COLUMNS))).all()]


# ---------------------------------------------------------------------------
# PRV-8 / AM-B1 — the rules themselves
# ---------------------------------------------------------------------------

async def test_prv8_every_fk_out_of_the_five_tables_is_no_action_or_restrict():
    rules = [r for r in await _rules() if r["table_name"] in FIVE]
    # Non-vacuity: census row 1 counts 18 on production at 030.
    assert len(rules) >= 18, f"only {len(rules)} FKs read — is this the right database?"
    offenders = sorted(f"{r['table_name']}.{r['constraint_name']} = {r['delete_rule']}"
                       for r in rules if r["delete_rule"] not in ("NO ACTION", "RESTRICT"))
    assert offenders == [], (
        "PRV-8: a delete out of a student-data table may never be decided by a "
        "cascade — migration 032 sets these to NO ACTION:\n  " + "\n  ".join(offenders))


async def test_regraded_to_id_keeps_its_deferral():
    """extend_chain's insert order depends on it (census §1 #5, corrected). 032
    changes its delete rule and nothing else."""
    (r,) = [r for r in await _rules() if r["constraint_name"] == "graded_tests_regraded_to_id_fkey"]
    assert (r["is_deferrable"], r["initially_deferred"]) == ("YES", "YES")


async def test_class_memberships_is_outside_the_set_and_keeps_its_cascades():
    rules = {r["constraint_name"]: r["delete_rule"] for r in await _rules()
             if r["table_name"] == "class_memberships"}
    assert rules == {"class_memberships_class_id_fkey": "CASCADE",
                     "class_memberships_student_id_fkey": "CASCADE"}


# ---------------------------------------------------------------------------
# PRV-8 — behaviour: a direct parent delete raises and deletes NOTHING
# ---------------------------------------------------------------------------

PARENTS = [
    # (label, table, how to pick the row from the graph)
    ("the student", "students", lambda g: g.student_id),
    ("a scan with a job and a chain", "transcriptions", lambda g: g.t["alpha"]),
    ("a chain's head (its successor points back)", "graded_tests", lambda g: g.g["alpha_r1"]),
    ("a chain's leaf (checked at commit)", "graded_tests", lambda g: g.g["alpha_r2"]),
    ("a graded test with a PDF row", "graded_tests", lambda g: g.g["beta"]),
    ("the rubric", "rubrics", lambda g: g.rubric_id),
    ("the batch", "grading_batches", lambda g: g.batch_id),
    ("the teacher", "users", lambda g: g.user_id),
]


@pytest.mark.parametrize("label,table,pick", PARENTS, ids=[p[0] for p in PARENTS])
async def test_prv8_a_direct_delete_of_a_parent_with_dependents_raises_and_deletes_nothing(
        graph, label, table, pick):
    await add_pdf(graph, "beta", f"graded_pdfs/{graph.g['beta']}.pdf")
    before = await row_counts(graph)

    with pytest.raises(IntegrityError):
        async with session() as db:
            await db.execute(text(f"DELETE FROM {table} WHERE id = :id"), {"id": pick(graph)})
            await db.commit()

    assert await row_counts(graph) == before, f"deleting {label} touched other rows"


# ---------------------------------------------------------------------------
# AM-B4 — tenant consistency, by the database
# ---------------------------------------------------------------------------

TENANT_FKS = {
    "transcriptions_student_tenant_fkey":
        ("transcriptions", ["student_id", "user_id"], "students", ["id", "user_id"]),
    "graded_tests_student_tenant_fkey":
        ("graded_tests", ["student_id", "user_id"], "students", ["id", "user_id"]),
    "graded_tests_transcription_tenant_fkey":
        ("graded_tests", ["transcription_id", "user_id"], "transcriptions", ["id", "user_id"]),
    "transcription_jobs_transcription_tenant_fkey":
        ("transcription_jobs", ["transcription_id", "user_id"], "transcriptions", ["id", "user_id"]),
}
TENANT_UNIQUES = {
    "students_id_user_id_key": ("students", ["id", "user_id"]),
    "transcriptions_id_user_id_key": ("transcriptions", ["id", "user_id"]),
}


async def test_am_b4_the_tenant_constraints_exist_in_the_database():
    fks = {r["conname"]: r for r in await _fk_columns()}
    for name, (table, cols, ref, ref_cols) in TENANT_FKS.items():
        assert name in fks, f"AM-B4: {name} is missing"
        r = fks[name]
        assert (r["table_name"], list(r["cols"]), r["ref_table"], list(r["ref_cols"])) == \
            (table, cols, ref, ref_cols)
        assert r["confdeltype"] == "a", f"{name} must be NO ACTION (AM-B1)"
    # The single-column FKs stay, so the ORM relationships are untouched.
    for single in ("transcriptions_student_id_fkey", "graded_tests_student_id_fkey",
                   "graded_tests_transcription_id_fkey", "transcription_jobs_transcription_id_fkey"):
        assert single in fks, f"AM-B4 keeps {single}"

    async with session() as db:
        rows = (await db.execute(text("""
            SELECT c.conname, t.relname,
                   ARRAY(SELECT a.attname FROM unnest(c.conkey) WITH ORDINALITY k(n, i)
                           JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.n
                          ORDER BY k.i) AS cols
              FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid
             WHERE c.contype = 'u' AND c.conname = ANY(:names)"""),
            {"names": list(TENANT_UNIQUES)})).all()
    assert {r[0]: (r[1], list(r[2])) for r in rows} == TENANT_UNIQUES


def test_am_b4_the_tenant_constraints_are_mirrored_in_the_orm():
    """For the schema-canon suite: the ORM declares what the database enforces."""
    from sqlalchemy import ForeignKeyConstraint, UniqueConstraint

    from app.models.grading import GradedTest
    from app.models.student import Student
    from app.models.transcription import Transcription
    from app.models.transcription_job import TranscriptionJob

    tables = {m.__tablename__: m.__table__ for m in (Student, Transcription, GradedTest, TranscriptionJob)}
    for name, (table, cols, ref, ref_cols) in TENANT_FKS.items():
        (fk,) = [c for c in tables[table].constraints
                 if isinstance(c, ForeignKeyConstraint) and c.name == name] or [None]
        assert fk is not None, f"{table}.__table_args__ lacks {name}"
        assert [c.name for c in fk.columns] == cols
        assert [e.column.table.name for e in fk.elements] == [ref] * len(ref_cols)
        assert [e.column.name for e in fk.elements] == ref_cols
    for name, (table, cols) in TENANT_UNIQUES.items():
        (uq,) = [c for c in tables[table].constraints
                 if isinstance(c, UniqueConstraint) and c.name == name] or [None]
        assert uq is not None, f"{table}.__table_args__ lacks {name}"
        assert [c.name for c in uq.columns] == cols


async def test_am_b4_a_cross_tenant_reference_is_refused_by_the_database(graph):
    """Another teacher's transcription naming THIS teacher's student."""
    import uuid

    from app.models.user import User

    other = uuid.uuid4()
    async with session() as db:
        db.add(User(id=other, email=f"purge_other_{uuid.uuid4().hex[:8]}@s2test.com",
                    full_name="Other Teacher", password_hash="x"))
        await db.commit()
    try:
        with pytest.raises(IntegrityError):
            async with session() as db:
                await db.execute(text(
                    "INSERT INTO transcriptions (id, user_id, rubric_id, student_id, gcs_uri, "
                    " gcs_bucket, gcs_object_path, filename, draft_json, contract_json, "
                    " approved_at, status, created_at, updated_at) "
                    "VALUES (gen_random_uuid(), :u, :r, :s, 'gs://b/x.pdf', 'b', 'x.pdf', 'x.pdf', "
                    " '{}'::jsonb, '{}'::jsonb, now(), 'approved', now(), now())"),
                    {"u": other, "r": graph.rubric_id, "s": graph.student_id})
                await db.commit()
    finally:
        async with session() as db:
            await db.execute(text("DELETE FROM transcriptions WHERE user_id = :u"), {"u": other})
            await db.execute(text("DELETE FROM users WHERE id = :u"), {"u": other})
            await db.commit()


# ---------------------------------------------------------------------------
# §16.1 — FK-graph completeness, self-checking
# ---------------------------------------------------------------------------

async def test_every_table_with_an_fk_path_to_the_student_graph_is_covered_by_the_plan():
    """A future table referencing any of them fails here until the plan covers
    it — by purging it, or (graded_test_pdfs, ruled 2026-09-23) by treating it
    as DEAD: refused on, asserted empty."""
    from app.services.erasure import DEAD_TABLES, PURGED_TABLES

    edges = {(r["table_name"], r["ref_table"]) for r in await _fk_columns()}
    reach = {"students", "graded_tests", "transcriptions"}
    while True:
        more = {src for (src, dst) in edges if dst in reach} - reach
        if not more:
            break
        reach |= more
    uncovered = sorted(reach - set(PURGED_TABLES) - set(DEAD_TABLES))
    assert uncovered == [], f"tables that reach a student but the plan never deletes from: {uncovered}"
