"""Structured output for the feedback call (PR-G4)."""
from typing import List, Optional

from pydantic import BaseModel


class ScopeFeedback(BaseModel):
    """Per-scope feedback. `scope_id` echoes the id it was asked about, so a
    model that answers about a scope nobody asked for is visible rather than
    silently mapped onto position."""
    scope_id: str
    text: str


class FeedbackResponse(BaseModel):
    scopes: List[ScopeFeedback] = []
    summary: Optional[str] = None
