"""Rebuild the onboarding outreach sheet from the database (028 §6).

    python -m app.scripts.rebuild_onboarding_sheet

THIS COMMAND IS WHAT MAKES ONB-3 TRUE RATHER THAN ASPIRATIONAL. "The database
is the record" is only a claim until something can reconstruct the whole view
from it: a dropped task, a Sheets outage, a hand-edit in a DB-owned column, a
sheet that never existed until today — all repair to the same place, by running
this.

WHAT IT TOUCHES. A:J, per user, matched on column A (ONB-5). K:M — סטטוס פנייה
/ שיחת ליווי נקבעה / הערות — are a HUMAN's and are never addressed: every write
range comes from `onboarding_sheet_service._row_range`, which cannot name a
column past J (ONB-6). Running this against a sheet a person has been working
in is therefore safe, and is the point.

WHAT IT REFRESHES THAT NOTHING ELSE DOES. Column J (בדקה מנה אמיתית) is the day
she first APPROVED a graded test. Approval does not write to the sheet — there
is no trigger on that path and adding one would put a spreadsheet on the
grading path — so J is only ever as fresh as the last run of this command.
That is the reason §6 says to run it weekly.

It is a projection, not a sync: the sheet is never read back into the app.
"""
import asyncio
import logging
import sys
from typing import List, Optional

from sqlalchemy import select

from ..config import settings
from ..database import get_db_context
from ..models.user import User
from ..services import onboarding_sheet_service as sheet

logger = logging.getLogger(__name__)


async def _all_user_ids() -> List:
    """Every user, oldest first — so the sheet grows in signup order and a
    freshly rebuilt sheet reads like the queue it replaces.

    Its own function so the reconcile test can drive `rebuild` without also
    faking a SQLAlchemy result object; the query itself is one line and has
    nothing to hide.
    """
    async with get_db_context() as db:
        result = await db.execute(select(User.id).order_by(User.created_at.asc()))
        return list(result.scalars().all())


async def rebuild(*, client: Optional[sheet.SheetsClient] = None) -> int:
    """Project every user into A:J. Returns the number of rows written.

    UNLIKE `upsert_user_row`, this RAISES. A no-op reconcile that logged and
    exited zero would be a repair tool that reports success while repairing
    nothing — the one behaviour a repair tool must not have. ONB-8 protects the
    teacher's request path; this is not on it.
    """
    resolved = client or (
        sheet.GoogleSheetsClient(settings.onboarding_sheet_id)
        if settings.onboarding_sheet_id else None
    )
    if resolved is None:
        raise RuntimeError(
            "ONBOARDING_SHEET_ID is not configured — there is no sheet to "
            "rebuild. Set it on this job's environment."
        )

    user_ids = await _all_user_ids()

    rows: List[List[str]] = []
    for user_id in user_ids:
        async with get_db_context() as db:
            user = await sheet.load_user_for_sheet(db, user_id)
            if user is None:
                # Deleted between the id scan and now. Nothing to project.
                continue
            activated_on = await sheet.first_activation_date(db, user_id)
            rows.append(sheet.build_row(user, activated_on))

    # ONE column-A scan for the whole rebuild (`write_rows`, not `write_row` in
    # a loop): per-row scanning is 2N requests against a 60-per-minute read
    # quota, which 429s a few hundred teachers in and leaves the sheet HALF
    # repaired — the one state a repair tool must not produce.
    outcomes = await asyncio.to_thread(sheet.write_rows, resolved, rows)

    logger.info(
        "rebuild_onboarding_sheet: wrote %d row(s) (%d updated, %d appended)",
        len(outcomes), outcomes.count("updated"), outcomes.count("appended"),
    )
    return len(outcomes)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    try:
        written = asyncio.run(rebuild())
    except Exception:
        logger.exception("rebuild_onboarding_sheet failed")
        return 1
    print(f"rebuild_onboarding_sheet: {written} row(s) written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
