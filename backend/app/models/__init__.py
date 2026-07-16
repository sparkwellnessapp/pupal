# Models package — import order ensures all classes are registered with
# Base.metadata before the first database operation.
from .grading import Rubric, GradingBatch, GradedTest
from .user import User, SubscriptionStatus
from .subject_matter import SubjectMatter, user_subject_matters
from .raw_rubric import RawRubric
from .rubric_extraction_job import RubricExtractionJob
from .rubric_share import RubricShare, SharePermission
from .student import Student
from .classroom import Class, ClassMembership
from .transcription import Transcription

__all__ = [
    # Grading models
    "Rubric",
    "GradingBatch",
    "GradedTest",
    # User models
    "User",
    "SubscriptionStatus",
    # Subject matter models
    "SubjectMatter",
    "user_subject_matters",
    # Raw data models
    "RawRubric",
    # Extraction job lifecycle (PR-1)
    "RubricExtractionJob",
    # Sharing models
    "RubricShare",
    "SharePermission",
    # Student / class models
    "Student",
    "Class",
    "ClassMembership",
    # Transcription model
    "Transcription",
]
