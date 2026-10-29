r"""Feedback for a math subject is written in `\( … \)` spans — the one notation every surface
draws. Before: the feedback writer had no math rule, so `$f'(x)=2x$` could reach the student's
PDF raw (`linearize` reads only `\( \)` spans). Zero network.
"""
from __future__ import annotations

import pytest

from app.agents.feedback.prompt import (FEEDBACK_PROMPT_VERSION, FEEDBACK_SYSTEM_PROMPT,
                                        feedback_prompt_version, feedback_system_prompt)
from app.services.math_notation.written import normalize_written_math


@pytest.mark.parametrize("text,expected", [
    (r"הגדרת נכון $f'(x)=2x$ ולכן", r"הגדרת נכון \(f'(x)=2x\) ולכן"),
    (r"$$x = \frac{1}{e}$$", r"\(x = \frac{1}{e}\)"),
    (r"\[x^2\] נכון", r"\(x^2\) נכון"),
    (r"כבר \(x=3\) בסדר", r"כבר \(x=3\) בסדר"),
    ("עולה 5 $ לשנה ו-6 $", "עולה 5 $ לשנה ו-6 $"),                # a currency sign, padded: not math
    ("$ חציון $", "$ חציון $"),
    ("", ""),
])
def test_only_the_three_delimiters_become_spans(text, expected):
    assert normalize_written_math(text) == expected


def test_the_prompt_is_untouched_outside_math():
    assert feedback_system_prompt(False) == FEEDBACK_SYSTEM_PROMPT
    assert feedback_prompt_version(False) == FEEDBACK_PROMPT_VERSION
    math = feedback_system_prompt(True)
    assert math.startswith(FEEDBACK_SYSTEM_PROMPT)
    assert r"\( ... \)" in math and "$...$" in math
    assert feedback_prompt_version(True) == FEEDBACK_PROMPT_VERSION + "+math1"


def test_the_subject_capability_decides():
    from app.agents.feedback.runner import subject_has_math_notation
    assert subject_has_math_notation("mathematics") is True
    assert subject_has_math_notation("computer_science") is False
    assert subject_has_math_notation(None) is False
    assert subject_has_math_notation("no-such-subject") is False


async def _generate(math: bool, text: str):
    from app.agents.feedback.agent import FeedbackAgent
    from app.agents.feedback.schemas import FeedbackResponse, ScopeFeedback

    seen = {}

    class _Runner:
        async def ainvoke(self, messages):
            seen["system"] = messages[0].content
            return FeedbackResponse(scopes=[ScopeFeedback(scope_id="q1", text=text)], summary=text)

    agent = FeedbackAgent(_Runner(), model_version="m", math_notation=math)
    block, _ = await agent.generate([("q1", "...")])
    return block, seen["system"]


async def test_math_feedback_is_asked_for_spans_and_normalised_to_them():
    block, system = await _generate(True, r"חישבת $x=3$ נכון")
    assert block.scopes["q1"].text == r"חישבת \(x=3\) נכון"
    assert block.summary.text == r"חישבת \(x=3\) נכון"
    assert block.prompt_version == "feedback-v1.1+math1"
    assert "<math>" in system


async def test_cs_feedback_is_byte_for_byte_what_the_model_wrote():
    block, system = await _generate(False, "cost $5$ here")
    assert block.scopes["q1"].text == "cost $5$ here"
    assert block.prompt_version == FEEDBACK_PROMPT_VERSION
    assert system == FEEDBACK_SYSTEM_PROMPT
