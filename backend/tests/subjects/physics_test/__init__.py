"""physics_test — a TEST-ONLY subject pack: the §3.3 litmus as code (PR_grader_v6_options.md §8,
[Q-18]). Everything a new subject needs lives in this folder; it is registered only inside
`test_new_pack_needs_no_core_change` (monkeypatched), so production lookups never see it.

The shape is exactly a production pack's: the seam data here, the v6 pack in the four
sibling files, and — because a subject also has an ONTOLOGY layer — its ontology entry,
which the test places beside the production ones for the test's lifetime only.
"""
from __future__ import annotations

from app.schemas.ontology_types import QuestionType, SubjectProfile as OntologySubjectProfile

from .explainer import EXPLAINER_FRAGMENT
from .planner import PLANNER_FRAGMENT
from .precedents import PRECEDENTS
from .verifier import VERIFIER_FRAGMENT

KEY = "physics_test"
PACK_ID = KEY
PACK_VERSION = "v1"

MODALITIES = ("prose", "math_notation")
EXTRACTION_FRAGMENT = None
P1_FRAGMENT = None
VERIFY_FRAGMENT = None
P2_KEYWORDS = frozenset()
RESCALE_TO_EXAM = False

ONTOLOGY = OntologySubjectProfile(
    subject_key=KEY,
    display_name_he="פיזיקה (בדיקה)",
    valid_question_types={QuestionType.SHORT_ANSWER, QuestionType.COMPUTATION},
    default_question_type=QuestionType.COMPUTATION,
)
