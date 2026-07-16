"""
The single definition of "equal" for transcription scoring.

This function is SHARED between the eval harness (scoring) and any production
code that needs to compare transcribed text. There is exactly one normalizer in
the codebase. If the accuracy metric ever needs to change, it changes here, once
(CLAUDE.md "one concept, one place").

Pipeline (order matters):
    1. Unicode NFC      — Hebrew + combining marks compare canonically
                          ("שׁ" decomposed == "שׁ" composed).
    2. lower()          — by deliberate decision the difflib accuracy metric is
                          case-INSENSITIVE: it is a bulk-similarity proxy and
                          should not be dominated by case noise. Case errors that
                          actually matter for grading (e.g. a "While"→"while"
                          "correction") are caught case-SENSITIVELY by the
                          critical-token metric (see scoring.py / critical_tokens.py),
                          not here.
    3. strip whitespace — indentation / blank-line differences never count. The
                          student's exact spacing is irrelevant to grading, and
                          freeing the model from matching it is intentional.
    4. (lenient only) drop the illegible marker "[?]".

Two scoring modes share this one function via the `strip_illegible` flag:
    - strict  (strip_illegible=False): "[?]" is kept, so it counts as a mismatch
              against the real character in the ground truth. This is the gate —
              it measures real teacher-review cost.
    - lenient (strip_illegible=True):  "[?]" is removed, measuring the accuracy of
              what the model actually committed to (honest abstention not punished).

Whitespace is stripped BEFORE the illegible marker is removed so that a spaced
form like "[ ? ]" first collapses to "[?]" and is then handled consistently.
"""
from __future__ import annotations

import re
import unicodedata

# The marker the VLM is instructed to emit for illegible characters, and the
# same token used in ground-truth files. One shared vocabulary.
ILLEGIBLE_MARKER = "[?]"

_WHITESPACE_RE = re.compile(r"\s+")


def normalize(text: str | None, *, strip_illegible: bool) -> str:
    """Normalize transcription text for comparison. Pure; no I/O, no side effects.

    Args:
        text: raw answer text (may be None — treated as empty).
        strip_illegible: True for lenient mode (drop "[?]"), False for strict.

    Returns:
        The normalized string.
    """
    if not text:
        return ""

    out = unicodedata.normalize("NFC", text)
    out = out.lower()
    out = _WHITESPACE_RE.sub("", out)
    if strip_illegible:
        out = out.replace(ILLEGIBLE_MARKER, "")
    return out
