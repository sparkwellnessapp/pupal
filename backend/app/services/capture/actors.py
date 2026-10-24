"""
Who is acting, and the one error type the capture service raises.

Endpoints resolve a `CaptureActor` (§6.1) and hand it to the service; the
service enforces SCOPE with it. Page operations are implemented once and are
reachable from both routers because both actors are accepted there:

  TeacherActor  the owning teacher — through her normal session, or a capture
                session scoped to this batch (D2/OD-5).
  StudentActor  a capture link, plus (once a submission exists) the device
                secret that binds the student's browser to it (D1, SCN-7).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union
from uuid import UUID


@dataclass(frozen=True)
class TeacherActor:
    user_id: UUID
    batch_id: UUID


@dataclass(frozen=True)
class StudentActor:
    link_id: UUID
    batch_id: UUID
    user_id: UUID                       # the OWNING teacher (rows are hers)
    device_hash: Optional[bytes] = None


CaptureActor = Union[TeacherActor, StudentActor]


@dataclass
class CaptureError(Exception):
    """A refusal with an HTTP status and a machine `code`. `extra` is merged
    into the JSON `detail`; `message_he` is what a screen may show."""
    status: int
    code: str
    message_he: str = ""
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        super().__init__(f"{self.status} {self.code}")

    def detail(self) -> dict:
        return {"code": self.code, "message_he": self.message_he, **self.extra}


NOT_FOUND = lambda: CaptureError(404, "not_found", "לא נמצא")        # noqa: E731
