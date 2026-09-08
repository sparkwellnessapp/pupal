"""english - prose modality. Fragments per the execution plan section 5 Phase 1 (F-1/F-2/F-3).
Written blind (no eval behind them); <= 12 lines each; replace CS rules, add none."""
from __future__ import annotations

KEY = "english"
MODALITIES = ("prose",)

# F-1 (extraction). Appended to the extraction system prompt as a final section.
EXTRACTION_FRAGMENT = """\
═══════════════════════════════════════════
SUBJECT: ENGLISH
═══════════════════════════════════════════
This rubric is for an English exam: prose answers, no code, no trace tables.
• An answer key with OR-alternatives ("X OR Y", "Any two of the following") is ONE criterion whose description lists the alternatives verbatim.
"""

# F-3 (P1 perception). Replaces the CS ink rules (misspellings/identifiers/CW/CR/code).
P1_FRAGMENT = """\
- Transcribe EXACTLY what the student wrote. Preserve every student error: \
misspellings, wrong or missing punctuation, wrong words. Transcribe misspellings exactly.
- Crossed-out text is omitted entirely — no strikethrough, no marker of any kind.
- Do not fix, complete, improve, or normalize anything. Do not add words the student did not write.
- Preserve paragraph breaks as one blank line.
- Include the student's handwritten answer content and substantive margin notes or messages.
"""

# F-2 (verifier). Replaces rules 3-5 of grader-v5.3 (the code-trace rules).
VERIFY_FRAGMENT = """\
3. VERIFY WHAT THE STUDENT WROTE against the check: the required element's
   presence and its quality as written. Quote the verbatim span that shows it.

4. THE ABSENCE AUDIT. Before returning not_met for a missing element, search the
   ENTIRE answer for it; basis_he states, in Hebrew, what you searched for and where.

5. Spelling, grammar and word-choice errors are EVIDENCE, not noise: judge them
   exactly as the check describes; never correct the student's text in your head.
"""

P2_KEYWORDS = frozenset()

# D-13: only the mathematics profile enters the grid-snap post-pass (rescale_to_exam); a flag, never a subject branch.
RESCALE_TO_EXAM = False
