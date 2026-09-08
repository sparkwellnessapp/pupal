"""Subject profiles — the ONE place subject/modality knowledge lives as DATA.

Layering (docs/MULTISUBJECT_PLAN.md C2, ruled 2026-09-08):
  * ontology layer   — `app.schemas.ontology_types.SUBJECT_PROFILES` (valid question types,
                       default type, taxonomy key): what the ontology permits per subject.
  * prompt/modality  — THIS package: prompt fragments keyed by the same `subject_key`,
                       assembled into the production prompts by the prompt modules.
  * scorer profile   — beside the instrument (`tests/transcription_eval_suit/profiles.py`).
  * storage key      — `rubrics.subject` (migration 027) and the contract's `subject` field.

No module here builds prompt text except by concatenating/substituting the fragments
below; nothing here knows about a specific rubric or student.
"""
from .registry import SubjectProfile, UnknownSubject, get_profile, prompt_version, subject_keys

__all__ = ["SubjectProfile", "UnknownSubject", "get_profile", "prompt_version", "subject_keys"]
