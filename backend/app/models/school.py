"""
School — the fifth override-attribution key (PR-G6).

Deliberately thin: a name, an optional city, and nothing else. Cross-teacher
question identity is V2 and does NOT belong here; this table exists so an
override can be attributed to an institution, not to build a school directory.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


# Junction (migration 022): every school a teacher works at. The FULL truth.
# users.school_id stays the single PR-G6 attribution key (the teacher's FIRST
# school) — see PUT /api/v0/users/me/schools, which is the one writer that keeps
# the two in agreement.
user_schools = Table(
    'user_schools',
    Base.metadata,
    Column('user_id', UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    Column('school_id', UUID(as_uuid=True), ForeignKey('schools.id', ondelete='CASCADE'), primary_key=True),
    # Position 0 is the school users.school_id points at. Ordering is not
    # cosmetic here — it DEFINES the PR-G6 attribution key.
    Column('position', Integer, nullable=False, default=0),
    Column('created_at', DateTime, default=datetime.utcnow, nullable=False),
)


class School(Base):
    __tablename__ = "schools"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name       = Column(String(255), nullable=False)
    city       = Column(String(255), nullable=True)
    # [023] סמל מוסד — the Ministry's institution symbol. THE identity when it is
    # present: it separates the two «בית אקשטיין» schools in פרדס חנה-כרכור that
    # name and city together cannot, and it does not move when a name is spelled
    # differently or the source list is refreshed. NULL for a school the teacher
    # typed herself, which is why 023's unique index is partial.
    ministry_symbol = Column(String(16), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # TWO relationships over TWO different columns, deliberately distinct names:
    # `users` is users.school_id (the attribution key); `teachers` is the 022
    # junction. Sharing a name here is a mapper misconfiguration that fails at
    # `import app.main`.
    users = relationship("User", back_populates="school")
    teachers = relationship("User", secondary=user_schools, viewonly=True)

    def __repr__(self) -> str:
        return f"<School {self.name!r}>"
