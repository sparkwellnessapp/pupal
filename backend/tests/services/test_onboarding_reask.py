"""The 14-day re-ask digest — 028 §7.

NO MAIL. The email provider is injected as a recorder; nothing here contacts
Resend (and the root conftest pins the whole test process to the console
provider besides).

The eligibility half runs against the real Vivi-Test database because the rule
IS a SQL predicate — a Python re-implementation of it in a fake would be a
second copy of the thing under test, and the interesting failures (a NULL
comparison that quietly excludes everyone) only exist in the database.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from app.database import get_db_context
from app.models.user import User
from app.scripts import onboarding_reask as reask


class Recorder:
    """An EmailProvider stand-in. `ok=False` reproduces a send failure."""

    def __init__(self, ok: bool = True):
        self.ok = ok
        self.sent: list[dict] = []

    async def send_email(self, to, subject, html_body, attachments=None):
        from app.services.email_service import EmailResult

        self.sent.append({"to": to, "subject": subject, "html": html_body})
        return EmailResult(success=self.ok, message_id="rec-1" if self.ok else None,
                           error=None if self.ok else "provider said no")


NOW = datetime(2026, 9, 9, 8, 0, tzinfo=timezone.utc)


async def _make_user(**over) -> User:
    """A teacher row with the exam columns under full control."""
    fields = dict(
        id=uuid4(),
        email=f"reask_{uuid4().hex[:10]}@s2test.com",
        full_name="מיכל כהן",
        password_hash="x",
        next_exam_date=None,
        next_exam_answered_at=None,
        next_exam_reask_email_sent_at=None,
        phone=None,
        whatsapp_opt_in=False,
    )
    fields.update(over)
    async with get_db_context() as db:
        user = User(**fields)
        db.add(user)
        await db.commit()
    return user


@pytest.fixture
async def cleanup():
    """Delete exactly the rows a test made. The suite shares Vivi-Test with
    every other module; a blanket DELETE here would take out their fixtures."""
    made: list = []
    yield made
    if made:
        async with get_db_context() as db:
            await db.execute(delete(User).where(User.id.in_([u.id for u in made])))
            await db.commit()


def _in_digest(recorder: Recorder, user) -> bool:
    """Whether THIS teacher was in the digest.

    Membership, never a count: the digest is one mail for everyone due, and
    Vivi-Test is shared with every other module in the suite — a row another
    test left behind would make `count == 1` fail for reasons that have nothing
    to do with the rule under test.
    """
    return any(user.email in mail["html"] for mail in recorder.sent)


async def _ids(now=NOW) -> set:
    async with get_db_context() as db:
        return {u.id for u in await reask.find_due_users(db, now=now)}


# ---------------------------------------------------------------------------
# Eligibility — the query in §7
# ---------------------------------------------------------------------------

async def test_selects_only_the_teachers_who_are_actually_due(cleanup):
    due = await _make_user(next_exam_answered_at=NOW - timedelta(days=15))
    too_recent = await _make_user(next_exam_answered_at=NOW - timedelta(days=13))
    never_asked = await _make_user()
    has_a_date = await _make_user(
        next_exam_answered_at=NOW - timedelta(days=30),
        next_exam_date=(NOW + timedelta(days=20)).date(),
    )
    cleanup.extend([due, too_recent, never_asked, has_a_date])

    found = await _ids()
    assert due.id in found
    # A teacher who gave a date is not "unknown" and is never re-asked; one who
    # never answered was never asked in the first place.
    assert {too_recent.id, never_asked.id, has_a_date.id}.isdisjoint(found)


async def test_the_fourteen_day_boundary_is_inclusive(cleanup):
    exactly = await _make_user(next_exam_answered_at=NOW - timedelta(days=14))
    cleanup.append(exactly)
    assert exactly.id in await _ids()


async def test_a_second_run_the_same_day_does_not_re_include_her(cleanup):
    user = await _make_user(next_exam_answered_at=NOW - timedelta(days=20))
    cleanup.append(user)

    first = Recorder()
    await _run(first, now=NOW)
    assert _in_digest(first, user)

    second = Recorder()
    await _run(second, now=NOW)
    assert not _in_digest(second, user)


async def test_answering_unknown_AGAIN_makes_her_eligible_again(cleanup):
    """The whole reason nothing is ever cleared: `sent_at < answered_at` is what
    re-arms her, automatically."""
    user = await _make_user(next_exam_answered_at=NOW - timedelta(days=20))
    cleanup.append(user)

    first = Recorder()
    await _run(first, now=NOW)
    assert _in_digest(first, user)

    second = Recorder()
    await _run(second, now=NOW)
    assert not _in_digest(second, user)

    # She answers "still don't know" a month later.
    later = NOW + timedelta(days=30)
    async with get_db_context() as db:
        row = await db.get(User, user.id)
        row.next_exam_answered_at = later
        await db.commit()

    much_later = later + timedelta(days=15)
    assert user.id in await _ids(now=much_later)
    third = Recorder()
    await _run(third, now=much_later)
    assert _in_digest(third, user)


async def test_a_send_failure_stamps_NOTHING_and_raises(cleanup):
    """Stamping first would lose a teacher permanently on a transient error.
    Sending first can at worst repeat a digest — a nuisance, against a teacher
    nobody ever calls."""
    user = await _make_user(next_exam_answered_at=NOW - timedelta(days=20))
    cleanup.append(user)

    with pytest.raises(RuntimeError):
        await _run(Recorder(ok=False), now=NOW)

    async with get_db_context() as db:
        stamp = await db.scalar(
            select(User.next_exam_reask_email_sent_at).where(User.id == user.id)
        )
    assert stamp is None
    # …and she is still due, so the scheduler's retry finds her.
    assert user.id in await _ids()


# ---------------------------------------------------------------------------
# The digest body — the consent gate (owner ruling OD-2)
# ---------------------------------------------------------------------------

def _render(**over) -> str:
    from types import SimpleNamespace

    base = dict(
        id=uuid4(), full_name="מיכל כהן", email="michal@example.com",
        phone=None, whatsapp_opt_in=False, schools=[], subject_matters=[],
        created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    base.update(over)
    return reask.render_digest_html([SimpleNamespace(**base)], sheet_url=None)


def test_a_wa_me_link_appears_ONLY_when_she_opted_in():
    """Storing a phone is not consent to message it — she may have given the
    number to be CALLED. Messaging a teacher who declined is a spam-law
    violation, not a UX wrinkle."""
    opted_in = _render(phone="052-1234567", whatsapp_opt_in=True)
    declined = _render(phone="052-1234567", whatsapp_opt_in=False)

    assert "wa.me/972521234567" in opted_in
    assert "wa.me" not in declined
    # The number is still shown — she may be phoned — and the reason there is
    # nothing to click is spelled out, so a blank is never read as "no phone".
    assert "052-1234567" in declined
    assert "לא אישרה ואטסאפ" in declined


def test_consent_with_an_unparseable_number_says_so_rather_than_going_quiet():
    """A missing link with no explanation reads as "she declined", which is a
    different fact and would cost us a teacher who said yes."""
    out = _render(phone="not a number", whatsapp_opt_in=True)
    assert "wa.me" not in out
    assert "לא הצלחנו לזהות" in out


def test_teacher_supplied_text_is_escaped():
    """Her name and her school name are free text SHE typed; a stray '<' would
    otherwise eat the rest of the row."""
    out = _render(full_name="<script>מיכל")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_the_prefill_names_her_and_is_the_copy_from_the_spec():
    link = reask.whatsapp_link("0521234567", "מיכל")
    assert link is not None and link.startswith("https://wa.me/972521234567?text=")
    from urllib.parse import parse_qs, urlparse

    text = parse_qs(urlparse(link).query)["text"][0]
    assert text == reask.WHATSAPP_TEMPLATE.format(name="מיכל")


def test_the_subject_counts_the_teachers():
    assert reask.render_subject(3).startswith("Vivi — 3 מורות")


async def test_it_refuses_to_run_without_a_destination(monkeypatch):
    """None ⇒ refuse, rather than send nowhere and report success."""
    monkeypatch.setattr(reask.settings, "alert_email", None)
    with pytest.raises(RuntimeError, match="ALERT_EMAIL"):
        await reask.run_reask(now=NOW)


# ---------------------------------------------------------------------------

async def _run(provider, *, now):
    """`run_reask` with the provider injected — the ONE seam these tests patch,
    so everything else (the query, the transaction, the ordering of send and
    stamp) is the real code path."""
    import app.scripts.onboarding_reask as module

    original = module.get_email_service
    module.get_email_service = lambda: provider
    try:
        return await module.run_reask(now=now)
    finally:
        module.get_email_service = original
