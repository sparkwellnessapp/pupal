"""[D-14] No test calls a real model by default.

Two model paths default to a real provider in `app.config`: the plan builder
(replaced structurally by the autouse fixture in tests/conftest.py) and the
student-feedback call (`feedback_model_key`, pinned empty there). A test that
wants either injects a fake; nothing reaches a provider unasked.
"""
from __future__ import annotations

import pytest

from app.agents.feedback import runner as feedback_runner
from app.config import settings


def test_feedback_has_no_model_in_tests():
    assert not settings.feedback_model_key


@pytest.mark.asyncio
async def test_attach_feedback_is_inert_without_an_injected_model():
    sentinel = object()
    assert await feedback_runner.attach_feedback(sentinel) is sentinel
