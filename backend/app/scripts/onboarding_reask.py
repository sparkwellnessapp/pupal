"""The 14-day re-ask digest (028 §7).

    python -m app.scripts.onboarding_reask

A teacher who answered «עוד לא יודעת» is not a lost lead — she is a lead with
an unknown date. Two weeks later she almost always knows. This command finds
those teachers and sends ONE digest to ALERT_EMAIL so a human works the list;
it does not email the teachers.

WHY ONE DIGEST AND NOT ONE MAIL PER TEACHER. The recipient is Noam, not the
teacher. n separate mails are n notifications to triage and n chances to lose
one; a single list is read once and worked top to bottom.

THE CONSENT GATE (owner ruling, OD-2). A `wa.me` link is emitted ONLY when
`whatsapp_opt_in` is true. Storing a phone is not consent to message it — she
may have given the number to be CALLED — and messaging a teacher who declined
is a spam-law violation, not a UX wrinkle. When she has a phone but no opt-in
the digest prints the number with an explicit «לא אישרה ואטסאפ» and no link, so
the reader sees why there is nothing to click.

IDEMPOTENCY, and why nothing is ever cleared. Eligibility is

    next_exam_date IS NULL
    AND next_exam_answered_at <= now() - 14 days
    AND (next_exam_reask_email_sent_at IS NULL
         OR next_exam_reask_email_sent_at < next_exam_answered_at)

The last clause is the whole trick: answering again moves `answered_at` past
the stamp and makes her eligible again by itself. A second run the same day
sends nothing.

FAILURE POLICY. The stamp is written only after a SUCCESSFUL send, and a failed
send stamps nothing and exits non-zero so the scheduler retries. The order
matters and it is deliberate: stamping first would lose a teacher permanently
on a transient SMTP error, while sending first can at worst repeat a digest —
and a repeated digest is a nuisance, whereas a dropped one is a teacher nobody
ever calls (§3.5a: degrade by omission, never by guessing).
"""
import asyncio
import html
import logging
import sys
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from urllib.parse import quote
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from ..config import settings
from ..database import get_db_context
from ..models.user import User
from ..services.email_service import get_email_service

logger = logging.getLogger(__name__)

REASK_AFTER_DAYS = 14

# The Hebrew opener, verbatim from §7. `{name}` is her full name.
WHATSAPP_TEMPLATE = (
    "היי {name}, כאן נועם מ-Vivi. כשנרשמת עוד לא ידעת מתי המבחן הבא שלך — "
    "כבר יודעים? אשמח לתאם שנבדוק את המנה הראשונה ביחד."
)

_SHEET_URL_TEMPLATE = "https://docs.google.com/spreadsheets/d/{sheet_id}/edit"


def normalize_phone_e164(raw: Optional[str]) -> Optional[str]:
    """Israeli local form -> E.164 digits, for a `wa.me` link.

    ON READ, never on write: the column stores exactly what she typed (§5), and
    this is the one place that has to guess. It is a GUESS, and it is allowed to
    fail — returning None costs a link, not a record.

    Rules, in order:
      * strip everything that is not a digit or a leading '+';
      * starts with 972 (with or without '+') -> Israeli international. Drop
        the country code, drop the local trunk '0' a teacher writing
        "+972 052-..." leaves in, re-prefix;
      * any OTHER '+' number -> already international, taken verbatim. It must
        NOT be given a 972 prefix: that turned "+1 415 555 0100" into
        "97214155550100", a real-looking Israeli number belonging to somebody
        else — the exact failure the last rule exists to prevent;
      * a leading '0' -> Israeli local: drop it, prefix 972;
      * anything else -> None, because a number we cannot place is a number we
        must not build a link to. A wrong wa.me link opens a chat with a
        STRANGER, which is worse than no link at all.
    """
    if not raw:
        return None
    text = raw.strip()
    plus = text.startswith("+")
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return None

    if digits.startswith("972"):
        rest = digits[3:].lstrip("0")
        return "972" + rest if rest else None

    if plus:
        return digits

    if digits.startswith("0"):
        rest = digits.lstrip("0")
        return "972" + rest if rest else None

    return None


def whatsapp_link(phone: Optional[str], full_name: str) -> Optional[str]:
    """The prefilled `wa.me` deep link, or None when the number cannot be
    normalised. THIS FUNCTION DOES NOT CHECK CONSENT — the caller does, once,
    where the decision is visible."""
    number = normalize_phone_e164(phone)
    if number is None:
        return None
    text = WHATSAPP_TEMPLATE.format(name=full_name)
    return f"https://wa.me/{number}?text={quote(text)}"


async def find_due_users(db, *, now: Optional[datetime] = None) -> List[User]:
    """The eligible set, and only it (the query in the module docstring).

    `now` is injectable so a test can move the clock instead of moving data.
    """
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=REASK_AFTER_DAYS)

    result = await db.execute(
        select(User)
        .where(
            User.next_exam_date.is_(None),
            User.next_exam_answered_at.isnot(None),
            User.next_exam_answered_at <= cutoff,
            (User.next_exam_reask_email_sent_at.is_(None))
            | (User.next_exam_reask_email_sent_at < User.next_exam_answered_at),
        )
        .options(
            selectinload(User.schools),
            selectinload(User.subject_matters),
        )
        .order_by(User.next_exam_answered_at.asc())
    )
    return list(result.scalars().all())


def _esc(value: Optional[str]) -> str:
    """Every teacher-supplied string reaches the digest through here. Her name
    and her school name are free text SHE typed; interpolating them raw into
    HTML would let a stray '<' silently eat the rest of the row."""
    return html.escape(value or "", quote=True)


def render_digest_html(users: List[User], *, sheet_url: Optional[str]) -> str:
    """The digest body. RTL, one block per teacher (§7)."""
    blocks: List[str] = []
    for user in users:
        schools = ", ".join(s.name for s in (user.schools or []))
        subjects = ", ".join(
            (s.name_he or s.name_en) for s in (user.subject_matters or [])
        )
        signed_up = (
            user.created_at.date().isoformat() if user.created_at else ""
        )

        rows = [
            f"<div><strong>{_esc(user.full_name)}</strong></div>",
            f"<div>אימייל: {_esc(user.email)}</div>",
        ]

        # THE CONSENT GATE, in one place and readable as one thought.
        if user.phone:
            if user.whatsapp_opt_in:
                link = whatsapp_link(user.phone, user.full_name or "")
                if link:
                    rows.append(
                        f'<div>טלפון: {_esc(user.phone)} — '
                        f'<a href="{_esc(link)}">פתחי ואטסאפ</a></div>'
                    )
                else:
                    # Consent given, number unparseable. Say so — a missing
                    # link with no explanation reads as "she declined".
                    rows.append(
                        f"<div>טלפון: {_esc(user.phone)} — "
                        f"אישרה ואטסאפ, אך לא הצלחנו לזהות את מבנה המספר</div>"
                    )
            else:
                rows.append(
                    f"<div>טלפון: {_esc(user.phone)} — "
                    f"<em>לא אישרה ואטסאפ</em></div>"
                )
        else:
            rows.append("<div>טלפון: —</div>")

        if schools:
            rows.append(f"<div>בית ספר: {_esc(schools)}</div>")
        if subjects:
            rows.append(f"<div>מקצוע: {_esc(subjects)}</div>")
        if signed_up:
            rows.append(f"<div>תאריך הרשמה: {_esc(signed_up)}</div>")

        blocks.append(
            '<div style="margin-bottom:18px;padding-bottom:14px;'
            'border-bottom:1px solid #e5e5e5">' + "".join(rows) + "</div>"
        )

    footer = ""
    if sheet_url:
        footer = (
            f'<p><a href="{_esc(sheet_url)}">תור הפנייה המלא בגיליון</a></p>'
        )

    return (
        '<div dir="rtl" style="font-family:Arial,Helvetica,sans-serif;'
        'font-size:15px;line-height:1.6">'
        f"<p>המורות הבאות ענו «עוד לא יודעת» לפני שבועיים או יותר:</p>"
        + "".join(blocks)
        + footer
        + "</div>"
    )


def render_subject(count: int) -> str:
    """§7, verbatim."""
    return f"Vivi — {count} מורות לשאול שוב על תאריך המבחן"


def _sheet_url() -> Optional[str]:
    if not settings.onboarding_sheet_id:
        return None
    return _SHEET_URL_TEMPLATE.format(sheet_id=settings.onboarding_sheet_id)


async def run_reask(*, now: Optional[datetime] = None) -> int:
    """Send today's digest. Returns the number of teachers included (0 when
    there was nothing to send). Raises on a send failure — `main` turns that
    into a non-zero exit so the scheduler retries."""
    if not settings.alert_email:
        raise RuntimeError(
            "ALERT_EMAIL is not configured — the digest has nowhere to go. "
            "Set it on the job's environment before scheduling this."
        )

    now = now or datetime.now(timezone.utc)

    async with get_db_context() as db:
        due = await find_due_users(db, now=now)
        if not due:
            logger.info("onboarding_reask: no teachers due")
            return 0
        # Render INSIDE the session: the relationships are loaded here, and a
        # detached User would lazy-load on attribute access.
        html_body = render_digest_html(due, sheet_url=_sheet_url())
        subject = render_subject(len(due))
        due_ids: List[UUID] = [u.id for u in due]

    result = await get_email_service().send_email(
        to=settings.alert_email, subject=subject, html_body=html_body,
    )
    if not result.success:
        # Stamp NOTHING. See the failure policy in the module docstring.
        raise RuntimeError(f"digest send failed: {result.error}")

    async with get_db_context() as db:
        await db.execute(
            update(User)
            .where(User.id.in_(due_ids))
            .values(next_exam_reask_email_sent_at=now)
        )
        await db.commit()

    logger.info("onboarding_reask: digest sent for %d teacher(s)", len(due))
    return len(due)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    try:
        count = asyncio.run(run_reask())
    except Exception:
        logger.exception("onboarding_reask failed")
        return 1
    print(f"onboarding_reask: {count} teacher(s) in today's digest")
    return 0


if __name__ == "__main__":
    sys.exit(main())
