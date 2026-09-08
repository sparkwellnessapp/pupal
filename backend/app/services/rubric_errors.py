"""
Rubric Error Types for Atomic Save+Compile Flow.

These exceptions are raised by save and update operations when
validation or compilation fails. They carry structured error
information for frontend display.

INVARIANT: A saved rubric is always a compiled rubric.
"""
from typing import Any, List


class RubricSaveError(Exception):
    """Base exception for rubric save errors."""
    
    def __init__(self, error_type: str, errors: List[Any], message_he: str = ""):
        super().__init__(message_he or error_type)
        self.error_type = error_type
        self.errors = errors
        self.message_he = message_he


class RubricValidationError(RubricSaveError):
    """Raised when rubric draft validation fails."""
    
    def __init__(self, errors: List[Any], message_he: str = "המחוון אינו תקין"):
        super().__init__("validation_failed", errors, message_he)


class RubricCompilationError(RubricSaveError):
    """Raised when rubric compilation fails with errors."""
    
    def __init__(self, errors: List[Any], message_he: str = "שגיאה בהכנת המחוון"):
        super().__init__("compilation_failed", errors, message_he)


class RubricSubjectConflictError(RubricSaveError):
    """Raised when an update's draft names a different subject than the rubric row.

    A rubric's subject is IMMUTABLE once saved (migration 027 — every downstream
    row reaches it through the rubric FK). The API maps this to 409.
    """

    def __init__(self, existing: str, incoming: str):
        super().__init__(
            "subject_conflict",
            [{"location": "subject", "message": f"rubric subject is {existing!r}; draft says {incoming!r}"}],
            "לא ניתן לשנות את תחום הדעת של מחוון שנשמר",
        )
        self.existing = existing
        self.incoming = incoming


class RubricWarningsError(RubricSaveError):
    """Raised when compilation has warnings that need acknowledgment.
    
    This is NOT an error - it's a request for user acknowledgment before
    proceeding with save.
    """
    
    def __init__(self, warnings: List[Any], message_he: str = "נמצאו אזהרות שדורשות אישור"):
        super().__init__("warnings_require_acknowledgment", warnings, message_he)
