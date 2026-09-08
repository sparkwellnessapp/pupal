"""The subject registry: one key, one frozen profile, one stamp rule.

`get_profile(key)` is the ONLY lookup. Unknown keys raise `UnknownSubject` — the API
boundary turns that into a 422; nothing downstream ever guesses a subject.

`prompt_version(base, profile)` is the D-16 stamp rule: CS stamps are unchanged
(the measured numbers ride on them); every other subject carries `+<key>` so an
English or Math number can never be mistaken for a CS one.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, Optional, Tuple

from app.schemas.ontology_types import (
    QuestionType,
    SUBJECT_PROFILES as _ONTOLOGY_PROFILES,
    SubjectProfile as OntologySubjectProfile,
)

from .profiles import computer_science, english, mathematics


class UnknownSubject(ValueError):
    """A subject key that is not in the registry. 422 at the API boundary."""


@dataclass(frozen=True)
class SubjectProfile:
    """Prompt/modality layer of a subject. All fields are DATA.

    A `None` fragment means "the base prompt, unchanged" — that is how the
    `computer_science` profile reproduces today's prompts byte-for-byte
    (pinned by tests/subjects/test_prompt_identity.py).
    """
    key: str
    modalities: FrozenSet[str]                     # {"code","prose","math_notation","figure"} — never on GradableTest
    extraction_fragment: Optional[str]             # F-1: appended to the extraction system prompt
    p1_fragment: Optional[str]                     # F-3: replaces the CS ink rules in P1
    verify_fragment: Optional[str]                 # F-2: replaces verifier rules 3-5
    p2_keywords: FrozenSet[str]                    # F-5: identifier-filter keyword set for the P2 spec
    ontology: OntologySubjectProfile               # the ontology-layer profile (valid/default question types)
    rescale_to_exam: bool = False                  # D-13: the grid-snap post-pass runs on this subject's drafts

    @property
    def valid_question_types(self) -> FrozenSet[QuestionType]:
        return frozenset(self.ontology.valid_question_types)

    @property
    def default_question_type(self) -> QuestionType:
        return self.ontology.default_question_type

    @property
    def is_baseline(self) -> bool:
        """The subject whose prompts ARE the pinned production constants."""
        return self.key == computer_science.KEY


def _build(module) -> SubjectProfile:
    return SubjectProfile(
        key=module.KEY,
        modalities=frozenset(module.MODALITIES),
        extraction_fragment=module.EXTRACTION_FRAGMENT,
        p1_fragment=module.P1_FRAGMENT,
        verify_fragment=module.VERIFY_FRAGMENT,
        p2_keywords=frozenset(module.P2_KEYWORDS),
        ontology=_ONTOLOGY_PROFILES[module.KEY],
        rescale_to_exam=bool(getattr(module, "RESCALE_TO_EXAM", False)),
    )


_PROFILES: Dict[str, SubjectProfile] = {
    m.KEY: _build(m) for m in (computer_science, english, mathematics)
}

# The registry and the ontology must name the same subjects - a key in one and
# not the other is a bug at import time, not at the first teacher.
assert set(_PROFILES) == set(_ONTOLOGY_PROFILES), (
    f"subject registry {sorted(_PROFILES)} != ontology SUBJECT_PROFILES {sorted(_ONTOLOGY_PROFILES)}")


def subject_keys() -> Tuple[str, ...]:
    return tuple(sorted(_PROFILES))


def get_profile(key: Optional[str]) -> SubjectProfile:
    """Look a subject up by its key. Raises UnknownSubject; never defaults."""
    if not key or key not in _PROFILES:
        raise UnknownSubject(
            f"Unknown subject {key!r}. Known: {', '.join(subject_keys())}")
    return _PROFILES[key]


def prompt_version(base: str, profile: SubjectProfile) -> str:
    """D-16 (ruled 2026-09-08): CS stamps are unchanged; others carry `+<key>`."""
    return base if profile.is_baseline else f"{base}+{profile.key}"
