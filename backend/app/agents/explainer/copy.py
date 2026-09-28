"""Every Hebrew string the reasoning line may carry, in one place (§7.5, §10.4).

CWV-5 (NoMachineVocabulary) binds here as on the grader: no line she reads may
say «מודל» or name a plan/check id. `MACHINE_VOCABULARY` is the E-3 list the
explainer's validators and the fallback's test both read.
"""
from __future__ import annotations

FULLY_EARNED_HE = "כל הדרישות בקריטריון מולאו."
MANUAL_HE = "הציון נקבע ידנית"
MISSING_PREFIX_HE = "חסר: "
DEDUCTED_PREFIX_HE = "נוכה: "
SEPARATOR = " · "
ELLIPSIS = " …"
MAX_LINE = 200

# E-3 — internal terms a reasoning line never contains.
MACHINE_VOCABULARY = ("אופציה", "צ'ק", "תוכנית הבדיקה", "מודל", "בינה מלאכותית",
                      "ויוי", "Vivi", "check", "option")
# E-5 — first-person and gendered-student markers.
VOICE_MARKERS = ("אני", "בדקתי", "מצאתי", "שלי", "התלמיד", "התלמידה")


# [AM-G15] The fault row of a group charge that a terminal pin moved here: the same
# mistake, charged where it counts, because she set the other criterion's grade herself.
MOVED_BY_PIN_ROW_HE = "נוכה כאן: אותה טעות, והציון ב«{criterion}» נקבע ידנית"
MOVED_BY_PIN_CRITERION_CHARS = 40


def moved_by_pin_row_he(pinned_criterion_text: str) -> str:
    """The row text, naming the pinned criterion by its first 40 characters."""
    return MOVED_BY_PIN_ROW_HE.format(
        criterion=pinned_criterion_text.strip()[:MOVED_BY_PIN_CRITERION_CHARS].rstrip())
