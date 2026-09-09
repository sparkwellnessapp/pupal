"""The onboarding outreach queue's Google Sheet projection (PR 028, §6).

WHAT THIS IS, AND WHAT IT IS NOT. The sheet is a DERIVED VIEW — a surface a
human works the outreach queue from, not a store. ONB-3 (DBIsTheRecord) is the
whole design: every value here originates in `users`, no application code ever
reads the sheet back, and `app.scripts.rebuild_onboarding_sheet` can rebuild
A:J from the database alone. That is what makes an unconfigured environment a
no-op rather than a failure — the teacher's answer is already committed by the
time anything here runs.

FOUR RULES, each a named protocol:

  ONB-5 UpsertOnUserId — column A is the key. A row is found by scanning
    column A and UPDATED in place; only an absent user appends. Appending
    blindly would grow a second row per re-answer, and the human working the
    queue would call the same teacher twice.

  ONB-6 DBColumnsOnly — the written range is A:J and NEVER wider. K:M are
    hers: סטטוס פנייה / שיחת ליווי / הערות, typed by a person. A write that
    reached K would erase the note explaining why she must not be called
    again. Every write range in this module is built by `_row_range`, which
    cannot express a column past J.

  ONB-7 RawAndISO — `valueInputOption='RAW'`. USER_ENTERED would let Sheets
    re-interpret what we send: a Hebrew date locale would reorder an ISO date,
    and a phone like "052-1234567" is a subtraction to a spreadsheet. Dates go
    out as ISO strings, and nothing is ever sent as a number.

  ONB-8 NeverThrows — the projection cannot fail the teacher's request. Every
    public entry point swallows and logs. She answered a question; a
    spreadsheet quota is not her problem, and the DB already has the answer.

WHY COLUMN E CARRIES THE CONSENT STATE — a deliberate deviation from §6, which
says E is the phone and blank if none. Storing a phone is NOT consent to
message it (owner ruling, OD-2): a teacher may have given a number to be
CALLED. The consent bit therefore has to be visible exactly where the number
is, or a human working this queue will read a number as permission. A new
column is not available: A:J is DB-owned and K:M are hers, so inserting one
before K shifts the human-owned columns, which ONB-6 forbids. So E reads
"{phone} — ואטסאפ: מאושר" or "{phone} — ואטסאפ: לא מאושר", and BOTH states are
spelled out: a missing marker must never be readable as consent.
"""
import asyncio
import logging
from datetime import date, datetime
from typing import List, Optional, Protocol, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..config import settings
from ..database import get_db_context
from ..models.grading import GradedTest
from ..models.user import User

logger = logging.getLogger(__name__)

# ONB-6: the DB-owned span. K:M belong to a human and are never addressed.
FIRST_COLUMN = "A"
LAST_COLUMN = "J"
COLUMN_COUNT = 10

# The A1 range used to LOCATE a user (ONB-5). Column A only — the scan reads
# keys, never the human's notes.
KEY_RANGE = "A:A"


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# H, when she answered but has no date (ONB-2). The sheet says what she said.
UNKNOWN_DATE_TEXT = "עוד לא יודעת"

_WHATSAPP_YES = "ואטסאפ: מאושר"
_WHATSAPP_NO = "ואטסאפ: לא מאושר"

# The unconfigured-environment notice is logged ONCE per process. It is a
# normal state (every test process, every laptop), so repeating it per write
# would train the reader to ignore the log.
_missing_sheet_id_logged = False


class SheetsClient(Protocol):
    """The three calls this module makes. A Protocol rather than the raw
    googleapiclient resource so tests inject ten lines instead of mocking a
    discovery-built object graph, and so ONB-6 is checkable: a fake records
    the exact ranges it was asked to write."""

    def get_values(self, a1_range: str) -> List[List[str]]:
        ...

    def update_values(self, a1_range: str, row: Sequence[object]) -> None:
        ...

    def append_values(self, a1_range: str, row: Sequence[object]) -> None:
        ...


class GoogleSheetsClient:
    """The real client: ADC + the spreadsheets scope (§6).

    Built lazily and per-call-site rather than at import: an environment with
    no credentials must still import this module, because `ONBOARDING_SHEET_ID`
    unset is a supported configuration and the app has to boot without it.
    """

    def __init__(self, spreadsheet_id: str):
        from googleapiclient.discovery import build  # local: heavy import
        import google.auth

        credentials, _ = google.auth.default(scopes=SCOPES)
        self._spreadsheet_id = spreadsheet_id
        # cache_discovery=False: the file cache is unwritable on Cloud Run and
        # emits a warning on every construction.
        self._values = build(
            "sheets", "v4", credentials=credentials, cache_discovery=False,
        ).spreadsheets().values()

    def get_values(self, a1_range: str) -> List[List[str]]:
        resp = self._values.get(
            spreadsheetId=self._spreadsheet_id, range=a1_range,
        ).execute()
        return resp.get("values", [])

    def update_values(self, a1_range: str, row: Sequence[object]) -> None:
        self._values.update(
            spreadsheetId=self._spreadsheet_id,
            range=a1_range,
            valueInputOption="RAW",  # ONB-7
            body={"values": [list(row)]},
        ).execute()

    def append_values(self, a1_range: str, row: Sequence[object]) -> None:
        self._values.append(
            spreadsheetId=self._spreadsheet_id,
            range=a1_range,
            valueInputOption="RAW",  # ONB-7
            insertDataOption="INSERT_ROWS",
            body={"values": [list(row)]},
        ).execute()


def _row_range(sheet_row: int) -> str:
    """A:J for one row. ONB-6 lives here: this function is the ONLY place a
    write range is constructed, and it cannot name a column past J."""
    return f"{FIRST_COLUMN}{sheet_row}:{LAST_COLUMN}{sheet_row}"


def _iso_date(value: Optional[object]) -> str:
    """ISO, or blank. Never a datetime's full form — the queue is worked by
    day, and a timestamp in a date column just makes the column wider."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _phone_cell(phone: Optional[str], whatsapp_opt_in: bool) -> str:
    """Column E. See the module docstring: the number and its consent state
    are one cell because they must be read together."""
    number = (phone or "").strip()
    if not number:
        return ""
    return f"{number} — {_WHATSAPP_YES if whatsapp_opt_in else _WHATSAPP_NO}"


def build_row(user: User, activated_on: Optional[date]) -> List[str]:
    """The A:J projection of one teacher. PURE — no session, no network — so
    the column layout is testable without either.

    Ten cells, always, even when empty: a short row would leave a stale value
    standing in the columns the update did not reach.
    """
    schools = ", ".join(s.name for s in (user.schools or []))
    subjects = ", ".join(
        (s.name_he or s.name_en) for s in (user.subject_matters or [])
    )

    if user.next_exam_date is not None:
        exam = _iso_date(user.next_exam_date)
    elif user.next_exam_answered_at is not None:
        # ONB-2: she answered, and the answer was "I don't know yet". That is
        # a different fact from never having been asked, and the sheet has to
        # show the difference or the queue cannot be worked.
        exam = UNKNOWN_DATE_TEXT
    else:
        exam = ""

    row = [
        str(user.id),                                    # A user_id (ONB-5 key)
        _iso_date(user.created_at),                      # B תאריך הרשמה
        user.full_name or "",                            # C שם מלא
        user.email or "",                                # D אימייל
        _phone_cell(user.phone, bool(user.whatsapp_opt_in)),  # E טלפון
        schools,                                         # F בית ספר
        subjects,                                        # G מקצוע
        exam,                                            # H תאריך המבחן הבא
        "",                                              # I מקור / מפנה — reserved (§6)
        _iso_date(activated_on),                         # J בדקה מנה אמיתית
    ]
    assert len(row) == COLUMN_COUNT, "row must span exactly A:J (ONB-6)"
    return row


def key_index(client: SheetsClient) -> dict:
    """{user_id -> 1-based sheet row}, from ONE read of column A (ONB-5).

    NO ROW IS SKIPPED AS "the header" — deliberately, and it is the safer of
    the two mistakes available here. Skipping row 1 by index protects against a
    header cell colliding with a key, which cannot happen: the key is a UUID
    and the header is the word "user_id". Not skipping it protects against a
    sheet that has NO header row — a blank sheet someone recreated, or the one
    the reconcile command is pointed at after an accident. There, an
    index-based skip would make the FIRST teacher permanently unfindable, so
    every re-answer would append her again and the human working the queue
    would call her twice.
    """
    return {
        row[0].strip(): offset + 1        # values 0-based; sheet rows 1-based
        for offset, row in enumerate(client.get_values(KEY_RANGE))
        if row and row[0].strip()
    }


def _write_with_index(client: SheetsClient, row: Sequence[object], index: dict) -> str:
    sheet_row = index.get(str(row[0]))
    if sheet_row is None:
        client.append_values(f"{FIRST_COLUMN}:{LAST_COLUMN}", row)
        return "appended"
    client.update_values(_row_range(sheet_row), row)
    return "updated"


def write_row(client: SheetsClient, row: Sequence[object]) -> str:
    """Upsert ONE A:J row. Returns "updated" or "appended".

    SYNCHRONOUS and client-only — no DB, no settings — so the request path and
    the reconcile command share one upsert rule.
    """
    return _write_with_index(client, row, key_index(client))


def write_rows(client: SheetsClient, rows: Sequence[Sequence[object]]) -> List[str]:
    """Upsert MANY rows against a SINGLE scan of column A.

    Not an optimisation — a correctness-under-quota requirement. The reconcile
    command upserts every user, and `write_row` in a loop reads the whole key
    column once PER USER: 2N requests against a Sheets read quota of 60 per
    minute, so a few hundred teachers would 429 the rebuild halfway and leave
    the sheet in exactly the half-repaired state the command exists to prevent.

    Safe because the index maps ids that ALREADY have rows; appends land on
    consecutive empty rows and cannot collide, since a user id appears at most
    once in the input.
    """
    index = key_index(client)
    return [_write_with_index(client, row, index) for row in rows]


async def load_user_for_sheet(db, user_id: UUID) -> Optional[User]:
    """The teacher plus the two collections the projection renders, eagerly —
    a lazy load here would MissingGreenlet under asyncio."""
    result = await db.execute(
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.schools),
            selectinload(User.subject_matters),
        )
    )
    return result.scalar_one_or_none()


async def first_activation_date(db, user_id: UUID) -> Optional[date]:
    """Column J: the day she first APPROVED a graded test — i.e. the day she
    actually used Vivi on a real class, which is the only activation signal
    worth phoning about.

    Computed on the same path as every other column rather than only by the
    reconcile script (§6 says "filled by the reconcile command only"): a
    per-user upsert that left J blank would ERASE the value a previous
    reconcile wrote, every single time she re-answers the step. One builder,
    one meaning — the reconcile command is then simply this, in bulk.
    """
    result = await db.execute(
        select(GradedTest.approved_at)
        .where(GradedTest.user_id == user_id,
               GradedTest.approved_at.isnot(None))
        .order_by(GradedTest.approved_at.asc())
        .limit(1)
    )
    approved_at = result.scalar_one_or_none()
    return approved_at.date() if approved_at is not None else None


def _resolve_client(client: Optional[SheetsClient]) -> Optional[SheetsClient]:
    """The injected client, or a real one — or None when the sheet is not
    configured, which is a supported state and not an error."""
    global _missing_sheet_id_logged
    if client is not None:
        return client
    if not settings.onboarding_sheet_id:
        if not _missing_sheet_id_logged:
            _missing_sheet_id_logged = True
            logger.info(
                "onboarding_sheet_disabled: ONBOARDING_SHEET_ID is unset — the "
                "sheet projection is a no-op. The database is the record "
                "(ONB-3); run app.scripts.rebuild_onboarding_sheet once the id "
                "is configured."
            )
        return None
    return GoogleSheetsClient(settings.onboarding_sheet_id)


async def upsert_user_row(
    user_id: UUID, *, client: Optional[SheetsClient] = None,
) -> Optional[str]:
    """Project one teacher into the sheet. THE public entry point (§6).

    ONB-8: never raises. Returns "updated"/"appended" on success, None when
    the sheet is disabled or the write failed — the caller has nothing to do
    with a failure, because the DB already holds the answer and the reconcile
    command is the repair.

    Owns its own session: this runs from a task handler, after the request
    that took her answer has committed and closed.
    """
    try:
        resolved = _resolve_client(client)
        if resolved is None:
            return None

        async with get_db_context() as db:
            user = await load_user_for_sheet(db, user_id)
            if user is None:
                logger.warning("onboarding_sheet_user_missing user_id=%s", user_id)
                return None
            row = build_row(user, await first_activation_date(db, user_id))

        # googleapiclient is blocking; keep the loop free.
        outcome = await asyncio.to_thread(write_row, resolved, row)
        logger.info("onboarding_sheet_%s user_id=%s", outcome, user_id)
        return outcome
    except Exception:
        # ONB-8. The message carries the id because `extra=` is never rendered
        # by this service's logging config (CLAUDE.md §8).
        logger.exception("onboarding_sheet_upsert_failed user_id=%s", user_id)
        return None
