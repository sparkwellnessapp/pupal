"""
Gender-neutral lint for teacher-facing feedback (PR-G4, parent spec C2).

The rule the prompt follows: **2nd-person PAST tense and nominal forms only.**
That is not stylistic — unvocalised Hebrew writes 2nd-person past identically
for both genders (כתבת), so past tense is the one address form that does not
guess the student's gender. Present tense, imperatives and the אתה/אתם pronouns
all do.

PRECISION-BIASED on purpose. `את` is both the feminine pronoun and the
accusative particle, and the particle is unavoidable in ordinary Hebrew — a lint
that fired on it would fire on almost every correct sentence, and a check nobody
can pass trains the click-through reflex that swallows the next real warning
(the INV-6 lesson, CLAUDE.md §5). So `את` is deliberately NOT flagged, and the
cost is a known blind spot rather than a noisy gate.
"""
from __future__ import annotations

import re
from typing import List

# Unambiguously gendered 2nd-person address.
_GENDERED = (
    # pronouns (את excluded — see module docstring)
    "אתה", "אתם", "אתן",
    # imperatives, m.sg / f.sg
    "בדוק", "בדקי", "כתוב", "כתבי", "שים", "שימי", "זכור", "זכרי",
    "הקפד", "הקפידי", "המשך", "המשיכי", "הוסף", "הוסיפי", "ודא", "ודאי",
    "נסה", "נסי", "השתמש", "השתמשי", "שנה", "שני", "עיין", "עייני",
    # present participles used to address the student
    "צריך", "צריכה", "כותב", "כותבת", "בודק", "בודקת",
    "מגדיר", "מגדירה", "משתמש", "משתמשת",
)

_PATTERN = re.compile(r"(?<![\w\u0590-\u05FF])(" + "|".join(_GENDERED) +
                      r")(?![\w\u0590-\u05FF])")


def gender_neutral_violations(text: str) -> List[str]:
    """Every gendered address form in `text`, in order of appearance."""
    return _PATTERN.findall(text or "")
