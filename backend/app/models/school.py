"""
School — the fifth override-attribution key (PR-G6).

Deliberately thin: a name, an optional city, and nothing else. Cross-teacher
question identity is V2 and does NOT belong here; this table exists so an
override can be attributed to an institution, not to build a school directory.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class School(Base):
    __tablename__ = "schools"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name       = Column(String(255), nullable=False)
    city       = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    users = relationship("User", back_populates="school")

    def __repr__(self) -> str:
        return f"<School {self.name!r}>"
