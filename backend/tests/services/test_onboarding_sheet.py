"""The onboarding sheet projection — ONB-5..8 (028 §6).

NO NETWORK. The Sheets client is a Protocol precisely so these run against ten
lines of fake that RECORDS the ranges it was asked to write — which is what
makes ONB-6 ("never past column J") a checkable claim rather than a comment.
"""
from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services import onboarding_sheet_service as sheet


class FakeSheets:
    """Records every call. `rows` is the sheet's column A, header included."""

    def __init__(self, keys=()):
        # Row 1 is the frozen header (§11) and must never match a user id.
        self.rows = [["user_id"]] + [[k] for k in keys]
        self.updates: list[tuple[str, list]] = []
        self.appends: list[tuple[str, list]] = []
        self.reads: list[str] = []

    def get_values(self, a1_range):
        self.reads.append(a1_range)
        return self.rows

    def update_values(self, a1_range, row):
        self.updates.append((a1_range, list(row)))

    def append_values(self, a1_range, row):
        self.appends.append((a1_range, list(row)))


class Boom:
    """A client that fails the way a quota or an outage does."""

    def get_values(self, a1_range):
        raise RuntimeError("429 Quota exceeded")

    def update_values(self, a1_range, row):
        raise RuntimeError("unreachable")

    def append_values(self, a1_range, row):
        raise RuntimeError("unreachable")


def fake_user(**over):
    base = dict(
        id=uuid4(),
        created_at=datetime(2026, 3, 1, 7, 30, tzinfo=timezone.utc),
        full_name="מיכל כהן",
        email="michal@example.com",
        phone=None,
        whatsapp_opt_in=False,
        next_exam_date=None,
        next_exam_answered_at=None,
        schools=[],
        subject_matters=[],
    )
    base.update(over)
    return SimpleNamespace(**base)


# ---------------------------------------------------------------------------
# build_row — the A:J projection (pure)
# ---------------------------------------------------------------------------

def test_the_row_is_exactly_ten_cells():
    """Ten, always, even when empty. A SHORT row would leave a stale value
    standing in the columns the update did not reach."""
    row = sheet.build_row(fake_user(), None)
    assert len(row) == sheet.COLUMN_COUNT == 10


def test_dates_go_out_as_ISO_and_never_as_a_timestamp(fake_school=None):
    row = sheet.build_row(
        fake_user(next_exam_date=date(2026, 11, 3),
                  next_exam_answered_at=datetime(2026, 9, 1, tzinfo=timezone.utc)),
        date(2026, 9, 4),
    )
    assert row[1] == "2026-03-01"   # B — signed up
    assert row[7] == "2026-11-03"   # H — the exam
    assert row[9] == "2026-09-04"   # J — activation


def test_an_unknown_answer_reads_as_the_words_she_chose():
    """ONB-2 on the sheet: "answered, unknown" and "never asked" must be
    distinguishable, or the queue cannot be worked."""
    answered = sheet.build_row(
        fake_user(next_exam_answered_at=datetime(2026, 9, 1, tzinfo=timezone.utc)), None,
    )
    never = sheet.build_row(fake_user(), None)
    assert answered[7] == sheet.UNKNOWN_DATE_TEXT
    assert never[7] == ""


def test_column_E_spells_out_BOTH_consent_states():
    """The owner ruling (OD-2): storing a number is not consent to message it.
    A bare number in this cell would be read as permission by whoever works the
    queue, so the absence of a marker must never be possible."""
    opted_in = sheet.build_row(
        fake_user(phone="052-1234567", whatsapp_opt_in=True), None,
    )
    declined = sheet.build_row(
        fake_user(phone="052-1234567", whatsapp_opt_in=False), None,
    )
    assert "052-1234567" in opted_in[4] and "מאושר" in opted_in[4]
    assert "052-1234567" in declined[4] and "לא מאושר" in declined[4]
    assert opted_in[4] != declined[4]


def test_no_phone_is_a_blank_cell_not_a_consent_claim():
    assert sheet.build_row(fake_user(), None)[4] == ""


def test_column_I_is_reserved_and_stays_empty():
    """Referral attribution does not exist yet. The column is kept so K:M do
    not have to move the day it does."""
    assert sheet.build_row(fake_user(), None)[8] == ""


def test_schools_and_subjects_are_joined_in_her_order():
    row = sheet.build_row(
        fake_user(
            schools=[SimpleNamespace(name="בליך"), SimpleNamespace(name="הרצוג")],
            subject_matters=[SimpleNamespace(name_he="אנגלית", name_en="English")],
        ),
        None,
    )
    assert row[5] == "בליך, הרצוג"
    assert row[6] == "אנגלית"


# ---------------------------------------------------------------------------
# write_row — ONB-5 (upsert on user_id) and ONB-6 (A:J only)
# ---------------------------------------------------------------------------

def test_an_absent_user_APPENDS():
    client = FakeSheets()
    row = sheet.build_row(fake_user(), None)
    assert sheet.write_row(client, row) == "appended"
    assert len(client.appends) == 1 and not client.updates


def test_an_existing_user_is_UPDATED_IN_PLACE_not_appended():
    """ONB-5. Appending blindly would grow a second row per re-answer, and the
    human working the queue would call the same teacher twice."""
    user = fake_user()
    client = FakeSheets(keys=["someone-else", str(user.id)])
    assert sheet.write_row(client, sheet.build_row(user, None)) == "updated"
    assert not client.appends
    a1, _ = client.updates[0]
    assert a1 == "A3:J3", a1   # header + one other row before her


def test_a_sheet_with_NO_header_still_upserts_the_first_teacher():
    """The header is not skipped by index, on purpose. A blank sheet — one
    someone recreated, or one the reconcile command is pointed at after an
    accident — would otherwise make the FIRST teacher permanently unfindable,
    so every re-answer would append her again and a human would call her twice.

    Nothing is lost by not skipping: a key is a UUID and a header cell is the
    word "user_id", so they cannot collide."""
    user = fake_user()
    headerless = FakeSheets()
    headerless.rows = [[str(user.id)]]          # she IS row 1

    assert sheet.write_row(headerless, sheet.build_row(user, None)) == "updated"
    assert headerless.updates[0][0] == "A1:J1"
    assert not headerless.appends


@pytest.mark.parametrize("existing", [True, False])
def test_the_written_range_NEVER_reaches_K(existing):
    """ONB-6. K:M are סטטוס פנייה / שיחת ליווי / הערות — typed by a person. A
    write that reached K would erase the note explaining why a teacher must
    not be called again."""
    user = fake_user()
    client = FakeSheets(keys=[str(user.id)] if existing else [])
    sheet.write_row(client, sheet.build_row(user, None))

    for a1, row in client.updates + client.appends:
        target = a1.split(":")[-1].rstrip("0123456789")
        assert target <= "J", f"write range reached column {target}: {a1}"
        assert len(row) == sheet.COLUMN_COUNT


def test_the_scan_reads_column_A_only_and_never_the_humans_notes():
    client = FakeSheets()
    sheet.write_row(client, sheet.build_row(fake_user(), None))
    assert client.reads == [sheet.KEY_RANGE] == ["A:A"]


# ---------------------------------------------------------------------------
# ONB-7 — RAW, on the real client
# ---------------------------------------------------------------------------

def test_the_real_client_sends_RAW_and_never_USER_ENTERED():
    """USER_ENTERED would let Sheets re-interpret what we send: a Hebrew date
    locale reorders an ISO date, and "052-1234567" is a subtraction to a
    spreadsheet. Asserted against the SOURCE of the one class that talks to
    Google, since constructing it needs credentials."""
    import inspect

    src = inspect.getsource(sheet.GoogleSheetsClient)
    assert src.count('valueInputOption="RAW"') == 2   # update + append
    assert "USER_ENTERED" not in src


# ---------------------------------------------------------------------------
# ONB-8 — the projection never throws
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a_client_failure_is_swallowed_and_logged(caplog, monkeypatch):
    """She answered a question; a spreadsheet quota is not her problem, and the
    DB already holds the answer.

    The user load is stubbed so the SHEET call is what fails: an earlier draft
    of this test passed a random uuid, which short-circuited at "user missing"
    and proved nothing about ONB-8 while still going green.
    """
    user = fake_user()

    async def _load(db, user_id):
        return user

    async def _activation(db, user_id):
        return None

    monkeypatch.setattr(sheet, "load_user_for_sheet", _load)
    monkeypatch.setattr(sheet, "first_activation_date", _activation)

    result = await sheet.upsert_user_row(user.id, client=Boom())
    assert result is None
    assert "onboarding_sheet_upsert_failed" in caplog.text


@pytest.mark.asyncio
async def test_a_DB_failure_is_swallowed_too(caplog, monkeypatch):
    """The guarantee is about the whole entry point, not just the network half:
    the task handler returns 200 either way, because there is nothing to heal
    by redelivering — the answer is already committed."""
    async def _boom(db, user_id):
        raise RuntimeError("connection reset by peer")

    monkeypatch.setattr(sheet, "load_user_for_sheet", _boom)
    assert await sheet.upsert_user_row(uuid4(), client=FakeSheets()) is None
    assert "onboarding_sheet_upsert_failed" in caplog.text


@pytest.mark.asyncio
async def test_a_successful_upsert_reports_which_it_did(monkeypatch):
    user = fake_user()

    async def _load(db, user_id):
        return user

    async def _activation(db, user_id):
        return date(2026, 9, 4)

    monkeypatch.setattr(sheet, "load_user_for_sheet", _load)
    monkeypatch.setattr(sheet, "first_activation_date", _activation)

    client = FakeSheets()
    assert await sheet.upsert_user_row(user.id, client=client) == "appended"
    assert await sheet.upsert_user_row(user.id, client=FakeSheets(keys=[str(user.id)])) == "updated"
    # Column J travels on the ORDINARY path, not only via the reconcile
    # command: a per-user upsert that left it blank would erase the value the
    # last reconcile wrote, every time she re-answers.
    assert client.appends[0][1][9] == "2026-09-04"


@pytest.mark.asyncio
async def test_an_unconfigured_sheet_is_a_no_op_not_a_failure(monkeypatch):
    """Every test process is an unconfigured environment, and so is every
    laptop. The app must boot, take her answer, and commit it."""
    monkeypatch.setattr(sheet.settings, "onboarding_sheet_id", None)
    monkeypatch.setattr(sheet, "_missing_sheet_id_logged", False)
    assert await sheet.upsert_user_row(uuid4()) is None


# ---------------------------------------------------------------------------
# The reconcile command — what makes ONB-3 true rather than aspirational
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rebuild_writes_A_to_J_for_every_user_and_never_touches_K_to_M(monkeypatch):
    """«The database is the record» is a claim until something can reconstruct
    the whole view from it. This is that something — and it must be safe to run
    against a sheet a person has been working in, which is the entire point."""
    from app.scripts import rebuild_onboarding_sheet as rebuild_mod

    users = [fake_user(full_name="א"), fake_user(full_name="ב")]
    by_id = {u.id: u for u in users}

    class _Ctx:
        async def __aenter__(self):
            return None

        async def __aexit__(self, *exc):
            return False

    async def _load(db, user_id):
        return by_id[user_id]

    async def _activation(db, user_id):
        return date(2026, 9, 4)

    monkeypatch.setattr(rebuild_mod, "get_db_context", lambda: _Ctx())
    monkeypatch.setattr(sheet, "load_user_for_sheet", _load)
    monkeypatch.setattr(sheet, "first_activation_date", _activation)

    # The id scan is the one query the stubbed session cannot answer.
    async def _ids(_self=None):
        return [u.id for u in users]

    monkeypatch.setattr(rebuild_mod, "_all_user_ids", _ids)

    client = FakeSheets(keys=[str(users[0].id)])   # one known, one new
    assert await rebuild_mod.rebuild(client=client) == 2

    # ONE scan of column A for the whole rebuild, not one per user: per-row
    # scanning is 2N requests against a 60-per-minute read quota, which 429s a
    # few hundred teachers in and leaves the sheet HALF repaired.
    assert client.reads == ["A:A"], client.reads

    assert len(client.updates) == 1                # the known row, in place
    assert len(client.appends) == 1                # the new one
    for a1, row in client.updates + client.appends:
        target = a1.split(":")[-1].rstrip("0123456789")
        assert target <= "J", f"reconcile reached column {target}: {a1}"
        assert len(row) == sheet.COLUMN_COUNT
    # Column J is what only this command refreshes (§6).
    assert client.updates[0][1][9] == "2026-09-04"


@pytest.mark.asyncio
async def test_rebuild_RAISES_when_the_sheet_is_unconfigured(monkeypatch):
    """UNLIKE the request-path upsert. A repair tool that logs, exits zero and
    repairs nothing is the one behaviour a repair tool must not have."""
    from app.scripts import rebuild_onboarding_sheet as rebuild_mod

    monkeypatch.setattr(rebuild_mod.settings, "onboarding_sheet_id", None)
    with pytest.raises(RuntimeError, match="ONBOARDING_SHEET_ID"):
        await rebuild_mod.rebuild()
