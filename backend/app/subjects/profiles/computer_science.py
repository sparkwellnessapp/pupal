"""computer_science - the baseline subject. Every fragment is None: the production
prompts are used unchanged, byte-for-byte (tests/subjects/test_prompt_identity.py)."""
from __future__ import annotations

KEY = "computer_science"
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
