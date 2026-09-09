"""The verification-code email — subject, Hebrew RTL body, and the send call.

Kept apart from `email_service` for the same reason the frontend keeps a copy
module: the words a teacher reads are edited far more often than the transport
that carries them, and mixing the two makes every wording tweak a change to
sending code.

The body is deliberately minimal. A one-time code email is the most phished
message shape there is, so it carries no links, no buttons, and nothing to
click — only the code, its lifetime, and what to do if she did not ask for it.
"""
from __future__ import annotations

import logging

from .email_service import EmailResult, get_email_service


logger = logging.getLogger(__name__)


SUBJECT = "קוד האימות שלך ל‑Vivi"


def build_html(code: str, ttl_minutes: int) -> str:
    """The RTL body. `code` is rendered LTR-isolated so a six-digit number never
    reorders inside a right-to-left paragraph — the same bidi discipline the
    frontend applies to file sizes and code blocks."""
    return f"""\
<!doctype html>
<html lang="he" dir="rtl">
  <body style="margin:0;padding:24px;background:#FFFaf2;
               font-family:Rubik,Arial,sans-serif;color:#1F2937;">
    <div style="max-width:520px;margin:0 auto;background:#ffffff;border-radius:16px;
                padding:32px;border:1px solid #E8E4DC;">
      <h1 style="margin:0 0 16px;font-size:20px;font-weight:600;">
        קוד האימות שלך
      </h1>
      <p style="margin:0 0 24px;font-size:15px;line-height:1.7;color:#4B5563;">
        הזיני את הקוד הזה כדי לסיים את ההרשמה ל‑Vivi.
      </p>
      <div dir="ltr" style="font-size:34px;font-weight:600;letter-spacing:8px;
                            text-align:center;padding:16px;background:#F0FDFA;
                            border-radius:12px;color:#0F766E;">{code}</div>
      <p style="margin:24px 0 0;font-size:14px;line-height:1.7;color:#6B7280;">
        הקוד תקף ל‑{ttl_minutes} דקות.
      </p>
      <p style="margin:12px 0 0;font-size:13px;line-height:1.7;color:#9CA3AF;">
        אם לא ביקשת קוד, אפשר להתעלם מההודעה הזאת — לא נעשה דבר בחשבון.
      </p>
    </div>
  </body>
</html>"""


async def send_verification_code(to: str, code: str, ttl_minutes: int) -> EmailResult:
    """Send one code. NEVER logs `code` — not on success, not on failure.

    Returns the result rather than raising: whether a failed send should surface
    to the teacher or be swallowed is the endpoint's decision, and the two
    endpoints answer it differently (signup tells her; resend stays uniform so
    it cannot be used to probe which addresses exist).
    """
    service = get_email_service()
    result = await service.send_email(
        to=to,
        subject=SUBJECT,
        html_body=build_html(code, ttl_minutes),
    )
    if not result.success:
        logger.warning("verification email failed for a recipient: %s", result.error)
    return result
