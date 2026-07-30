"""The retryable self-correction for the "choose 4 of 1" bug.

A 'choose k of N' selection group whose extracted pool is smaller than k means
segmentation missed/merged the exam's questions while the selection LLM correctly
read 'answer k'. We emit a RETRYABLE validation issue so `_extract_with_retry`
re-prompts the model (via _build_retry_feedback) to extract every question — rather
than shipping a "choose 4 of 1" draft to the teacher.
"""
from app.services.docx_v3.pipeline import (
    SelectionGroupExtraction,
    _selection_satisfiability_issues,
    _is_point_mismatch,
)


def _grp(nums, k, label=None):
    return SelectionGroupExtraction(question_numbers=nums, choose_k=k, label=label)


def test_all_members_extracted_no_issue():
    assert _selection_satisfiability_issues([_grp([1, 2, 3, 4, 5, 6], 4)], {1, 2, 3, 4, 5, 6}) == []


def test_the_reported_bug_emits_a_retryable_issue():
    # choose_k=4 but only q1 extracted → the "choose 4 of 1" state
    issues = _selection_satisfiability_issues([_grp([1, 2, 3, 4, 5, 6], 4, "ענו על 4 מתוך 6 שאלות")], {1})
    assert len(issues) == 1
    assert issues[0].code == "SELECTION_UNSATISFIABLE"
    assert issues[0].retryable is True
    assert "MISSED or MERGED" in issues[0].message


def test_issue_triggers_a_retry_not_a_point_mismatch():
    # Point-mismatches do NOT trigger retries; this MUST, so it re-prompts the model.
    issue = _selection_satisfiability_issues([_grp([1, 2], 2)], {1})[0]
    assert _is_point_mismatch(issue) is False


def test_partial_dangling_but_enough_present_is_satisfiable():
    # choose 2 of 6, 3 members extracted → satisfiable (the 3 dangling members are
    # only warnings elsewhere, not a retry trigger).
    assert _selection_satisfiability_issues([_grp([1, 2, 3, 4, 5, 6], 2)], {1, 2, 3}) == []


def test_boundary_choose_equals_present_ok():
    assert _selection_satisfiability_issues([_grp([1, 2, 3], 3)], {1, 2, 3}) == []


def test_second_group_unsatisfiable_still_caught():
    issues = _selection_satisfiability_issues([_grp([1, 2], 1), _grp([3, 4, 5], 3)], {1, 2, 3})
    assert len(issues) == 1
    assert issues[0].retryable is True


def test_no_groups_is_empty():
    assert _selection_satisfiability_issues([], set()) == []
