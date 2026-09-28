"""computer_science - the baseline subject. Every v5-era fragment is None: the production
prompts are used unchanged, byte-for-byte (tests/subjects/test_prompt_identity.py).

[Q-18] A package since grader-v6 Phase 2: this file keeps the multisubject-seam data it
always held; the v6 PACK (PR_grader_v6_options.md §8) is the four sibling files —
planner.py, verifier.py, explainer.py, precedents.py — re-exported below.
"""
from __future__ import annotations

from .explainer import EXPLAINER_FRAGMENT
from .planner import PLANNER_FRAGMENT
from .precedents import PRECEDENTS
from .verifier import VERIFIER_FRAGMENT

KEY = "computer_science"

# The v6 pack identity (config_hash input, §3.5). Bump PACK_VERSION with ANY change to
# the four pack files — the sha pins in tests/subjects/test_subject_packs.py carry it.
PACK_ID = KEY
PACK_VERSION = "v1"

MODALITIES = ("code", "prose")

EXTRACTION_FRAGMENT = None
P1_FRAGMENT = None
VERIFY_FRAGMENT = None

# The P2 spec identifier filter's keyword set (F-5). This set used to live as
# `_CSHARP_KW` in two_phase/parsing.py and applied to EVERY exam; it is now the
# CS profile's data and the prose/math profiles carry an empty set.
P2_KEYWORDS = frozenset({
    "abstract", "as", "base", "bool", "break", "byte", "case", "catch", "char",
    "class", "const", "continue", "decimal", "default", "do", "double", "else",
    "enum", "false", "float", "for", "foreach", "if", "in", "int", "interface",
    "internal", "is", "long", "namespace", "new", "null", "object", "out",
    "override", "private", "protected", "public", "readonly", "ref", "return",
    "sbyte", "sealed", "short", "static", "string", "struct", "switch", "this",
    "throw", "true", "try", "uint", "ulong", "ushort", "using", "var", "virtual",
    "void", "volatile", "while",
})

# D-13: only the mathematics profile enters the grid-snap post-pass (rescale_to_exam); a flag, never a subject branch.
RESCALE_TO_EXAM = False
