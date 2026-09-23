"""
The erasure core — privacy-complete deletion of a student (PR_student_profile
Part B; docs/PURGE_CENSUS.md). Plan → execute → verify: the plan is the whole
of the discovery, execution deletes exactly the plan (PRV-6), and every purge
ends with a verify report (PRV-7).
"""
from .execute import PurgeResult, execute_purge, purge_student
from .ledger import ObjectFailure, retry_purge_failures
from .plan import (
    PurgeBlocked,
    PurgePlan,
    PurgeRefused,
    StudentNotFound,
    UnassignedScans,
    plan_purge,
)
from .registry import DEAD_TABLES, PII_REGISTRY, PURGED_TABLES, Disposition
from .storage import GcsStorage, GuardedStorage, StorageClient, get_purge_storage
from .verify import VerifyReport, verify_purged
from .targets import (
    UnsafeStorageTarget,
    known_buckets,
    returned_exams_prefix,
    thumbs_prefix,
    validate_object,
    validate_target,
)

__all__ = [
    "DEAD_TABLES", "Disposition", "GcsStorage", "GuardedStorage", "ObjectFailure", "PII_REGISTRY",
    "PURGED_TABLES", "PurgeBlocked", "PurgePlan", "PurgeRefused", "PurgeResult", "StorageClient",
    "VerifyReport", "execute_purge", "purge_student", "retry_purge_failures", "verify_purged",
    "StudentNotFound", "UnassignedScans", "UnsafeStorageTarget", "get_purge_storage",
    "known_buckets", "plan_purge", "returned_exams_prefix", "thumbs_prefix",
    "validate_object", "validate_target",
]
