"""
Gender-neutral lint for teacher-facing feedback (PR-G4, parent spec C2).

The rule the prompt follows: **2nd-person PAST tense and nominal forms only.**
Not stylistic — unvocalised Hebrew writes 2nd-person past identically for both
genders (כתבת), so it is the one address form that does not guess the student's
gender. Present tense, imperatives and the אתה/אתם pronouns all do.

PRECISION-BIASED, and rewritten after a measured failure. The first version
matched bare imperative spellings and fired on 8 of 10 real draws — every hit a
FALSE POSITIVE, because Hebrew imperatives are homographs of much commoner
words:

    שני    the numeral "two"  ("שני דפוסים" — which this prompt ASKS for)
    המשך   the noun "continuation" ("תנאי המשך")
    השתמש  3rd-person past "used" ("החישוב השתמש במשתנים")

That is the INV-6 failure exactly: a check nobody can pass trains the
click-through reflex that swallows the next real warning. So the vocabulary is
now restricted to forms that cannot be anything else:

  * the pronouns אתה / אתם / אתן;
  * feminine-singular imperatives (the -י forms), which are unambiguous as
    address;
  * masculine-singular imperatives only as PHRASES ("שים לב", "בדוק את"), where
    the following word disambiguates the homograph.

Known blind spots, deliberate and documented rather than traded for noise:
`את` (also the accusative particle), and bare m.sg imperatives outside the
listed phrases.
"""
from __future__ import annotations

import re
from typing import List

_PRONOUNS = ("אתה", "אתם", "אתן")

# -י imperatives: unambiguous as 2nd-person feminine address.
# NOTE: שני is NOT here — it is the numeral "two".
_F_SG_IMPERATIVES = (
    "שימי", "בדקי", "כתבי", "זכרי", "הקפידי", "המשיכי",
    "הוסיפי", "נסי", "השתמשי", "עייני", "ודאי",
)

# m.sg imperatives ONLY where the next word disambiguates the homograph.
_M_SG_PHRASES = (
    "שים לב", "בדוק את", "בדוק ש", "כתוב את", "זכור ש", "ודא ש", "נסה ל",
)

_BOUNDARY_L = r"(?<![\w\u0590-\u05FF])"
_BOUNDARY_R = r"(?![\w\u0590-\u05FF])"

_WORDS = re.compile(_BOUNDARY_L + "(" + "|".join(_PRONOUNS + _F_SG_IMPERATIVES)
                    + ")" + _BOUNDARY_R)
_PHRASES = re.compile(_BOUNDARY_L + "(" + "|".join(p.replace(" ", r"\s+")
                                                   for p in _M_SG_PHRASES) + ")")


def gender_neutral_violations(text: str) -> List[str]:
    """Every gendered 2nd-person address form in `text`, in order."""
    body = text or ""
    hits = [(m.start(), m.group(0)) for m in _WORDS.finditer(body)]
    hits += [(m.start(), m.group(0)) for m in _PHRASES.finditer(body)]
    return [h for _pos, h in sorted(hits)]
