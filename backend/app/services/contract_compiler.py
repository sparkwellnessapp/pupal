"""
Contract Compiler: ExtractRubricResponse → GradingRubricContract.

This module is the VALIDATION GATE between the editable pipeline artifact
and the frozen grading contract. If compilation succeeds, the contract
is guaranteed to satisfy all invariants.

Architecture:
- ExtractRubricResponse: Editable, rich metadata, annotations
- compile() → Validates all invariants, strips pipeline-only fields
- GradingRubricContract: Frozen, minimal, closed-world

Invariants Validated:
- INV-1 QuestionPointSum: Σ direct_criteria.points + Σ sq.points ≈ q.total_points
- INV-2 CriteriaPointSum: Σ sq.criteria.points ≈ sq.points (per sub-question)
- INV-3 SubCriteriaPointsSum: Σ sc.points ≈ criterion.points (vacuous if empty)
- INV-4 RubricPointsSum: Σ q.total_points ≈ contract.total_points
- INV-6 CriterionAlignment: Every criterion links to skill/requirement (WARNING)

Compilation Blocking:
- ERROR-severity annotations → CompilationError
- Unacknowledged WARNING annotations → WarningsRequireAcknowledgment

Design Principle:
- Compiler DOES NOT mutate its input
- Validation results are collected and raised, not appended
"""
from decimal import Decimal
from typing import List, Optional
from uuid import uuid4

from ..schemas.ontology_types import (
    Annotation,
    AnnotationSeverity,
    CompilationError,
    ExtractRubricResponse,
    GradingRubricContract,
    NumericPolicy,
    SubQuestion,
    WarningsRequireAcknowledgment,
    compute_achievable_points,
)


def _fmt(d: Decimal) -> str:
    """Decimal → the shortest faithful string ('2.0'→'2', '1.50'→'1.5', '100'→'100').
    `format(d,'f')` avoids scientific notation, which .normalize() would introduce
    for round hundreds (Decimal('100').normalize() == Decimal('1E+2'))."""
    s = format(d, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s or "0"


def _invariant_error(
    *, invariant: str, target_id: Optional[str], expected: Decimal, actual: Decimal,
    message: str, message_he: str,
) -> Annotation:
    """One shape for every invariant violation: the named invariant, the node it
    anchors to, and the arithmetic — in a form the editor can render inline and a
    teacher can act on."""
    return Annotation(
        annotation_type="invariant_violation",
        severity=AnnotationSeverity.ERROR,
        message=message,
        message_he=message_he,
        target_id=target_id,
        invariant=invariant,
        expected=_fmt(expected),
        actual=_fmt(actual),
    )


class ContractCompiler:
    """
    Compiles ExtractRubricResponse to GradingRubricContract.
    
    This is the validation gate: if compile() returns successfully,
    the grading agent can trust the contract is well-formed.
    
    IMPORTANT: This compiler DOES NOT mutate its input response.
    All validation errors are collected and raised, not appended.
    """
    
    def compile(
        self,
        response: ExtractRubricResponse,
        policy: NumericPolicy = None,
        acknowledged_warnings: List[str] = None
    ) -> GradingRubricContract:
        """
        Compile a rubric response to a grading contract.
        
        Args:
            response: The editable rubric response from extraction/editing
            policy: Numeric policy for the contract (defaults to standard policy)
            acknowledged_warnings: List of warning annotation IDs that teacher has acknowledged
            
        Returns:
            GradingRubricContract: Frozen, validated contract
            
        Raises:
            CompilationError: If validation errors or error-severity annotations exist
            WarningsRequireAcknowledgment: If unacknowledged warnings exist
        """
        policy = policy or NumericPolicy()
        acknowledged_warnings = acknowledged_warnings or []
        
        # Step 1: Check existing error-severity annotations in the response
        self._check_error_annotations(response.annotations)
        
        # Step 2: Validate point-sum invariants (collect errors, don't mutate)
        validation_errors: List[Annotation] = []
        validation_errors.extend(self._validate_point_sum_question(response, policy))
        validation_errors.extend(self._validate_point_sum_criterion(response, policy))
        validation_errors.extend(self._validate_point_sum_rubric(response, policy))
        
        # Step 3: If we found validation errors, raise immediately
        if validation_errors:
            error_msgs = [f"[{a.annotation_type}] {a.message}" for a in validation_errors]
            raise CompilationError(
                f"Compilation blocked by {len(validation_errors)} validation error(s):\n" + 
                "\n".join(error_msgs),
                errors=validation_errors
            )
        
        # Step 4: Criterion alignment (INV-6) — emitted as INFO, NEVER blocking (R1).
        # Kept for the future skill-mapping feature; deliberately NOT added to the
        # acknowledgment set, which is what collapses the frontend's two-round-trip
        # ack dance into a single compile call for a clean rubric.
        self._check_criterion_alignment(response)

        # Step 5: Only genuine WARNING-severity annotations require acknowledgment.
        all_warnings = [
            a for a in response.annotations
            if a.severity == AnnotationSeverity.WARNING
        ]

        unacknowledged = [w for w in all_warnings if w.id not in acknowledged_warnings]
        if unacknowledged:
            raise WarningsRequireAcknowledgment(unacknowledged)
        
        # Step 6: Build frozen contract.
        #
        # Strip editor-only fields before freezing:
        # - proposals (Question + SubQuestion): AI-proposed criteria, editor-only, never graded.
        # - SubQuestion.title: display-only UX label, never graded.
        #
        # Keep grading-context fields (example_solution, trace_tables, context_tables):
        # the GraderAgent needs these to grade correctly. SubQuestion.example_solution
        # was already kept; Question-level fields are now kept symmetrically (S6 fix).
        # sub_criteria are kept: they are the grading substrate for partial credit.
        clean_questions = [
            q.model_copy(update={
                "proposals": None,
                "sub_questions": [
                    # Note: `title` is editor-only UX metadata and is NOT carried
                    # into the compiled contract. Graders never see custom titles.
                    sq.model_copy(update={"proposals": None, "title": None})
                    for sq in q.sub_questions
                ],
            })
            for q in response.questions
        ]
        # PR-3: selection_groups are PROPAGATED (the field existed with a docstring
        # apologising for its own non-population), and total_points is the ACHIEVABLE
        # total, not the offered sum (R4). This is the single source of the grading
        # denominator — every consumer reads contract.total_points and NONE of them
        # re-sums scopes. Re-derivation is precisely how the halved-grade bug
        # (perfect employee answer scoring 50%) came to exist.
        contract = GradingRubricContract(
            schema_version=response.schema_version,
            contract_version=str(uuid4()),
            rubric_id=response.rubric_id,
            subject=response.subject,
            programming_language=response.programming_language,
            numeric_policy=policy,
            total_points=compute_achievable_points(
                clean_questions, response.selection_groups
            ),
            questions=clean_questions,
            selection_groups=list(response.selection_groups),
        )

        return contract
    
    def _check_error_annotations(self, annotations: List[Annotation]) -> None:
        """
        Block compilation if any error-severity annotations exist.
        
        Error annotations indicate critical issues that must be resolved
        before the rubric can be used for grading.
        """
        errors = [a for a in annotations if a.severity == AnnotationSeverity.ERROR]
        
        if errors:
            error_msgs = [f"[{a.annotation_type}] {a.message}" for a in errors]
            raise CompilationError(
                f"Compilation blocked by {len(errors)} existing error(s):\n" + 
                "\n".join(error_msgs),
                errors=errors
            )
    
    def _validate_point_sum_question(
        self, 
        response: ExtractRubricResponse,
        policy: NumericPolicy
    ) -> List[Annotation]:
        """
        Invariant 1: PointSumQuestion
        
        Sum of criterion points within a question must equal
        the declared question total (within tolerance).
        
        For questions with sub-questions:
          total_points ≈ Σ direct_criteria.points + Σ sub_question.points
        
        Also validates each sub-question's points ≈ Σ its criteria.points.
        
        Returns list of error annotations (does NOT mutate input).
        """
        errors: List[Annotation] = []

        for question in response.questions:
            declared_total = question.total_points

            # INV-1 — nesting-safe already: it sums the sub-questions' DECLARED
            # points, never their contents, so depth is irrelevant here.
            direct_sum = sum(c.points for c in question.criteria)
            sub_q_sum = sum(sq.points for sq in question.sub_questions)
            criteria_sum = direct_sum + sub_q_sum
            diff = abs(declared_total - criteria_sum)

            if diff > policy.sum_tolerance:
                errors.append(_invariant_error(
                    invariant="INV-1",
                    target_id=question.question_id,
                    expected=declared_total, actual=criteria_sum,
                    message=(
                        f"Question {question.question_id}: Criteria sum ({criteria_sum}) "
                        f"differs from declared total ({declared_total}) by {diff}"
                    ),
                    message_he=(
                        f"שאלה {question.question_id}: "
                        f"סכום ניקוד "
                        f"הסעיפים ({_fmt(criteria_sum)}) "
                        f"שונה מהניקוד "
                        f"המוצהר ({_fmt(declared_total)})"
                    ),
                ))

            # INV-2 — RECURSIVE (PR-3). Mirrors the pipeline preflight's _walk_sq
            # EXACTLY (pipeline.py::_walk_sq); that preflight/compiler pair is an
            # established mirror and must not be allowed to drift.
            for sq in question.sub_questions:
                errors.extend(self._walk_sub_question(
                    sq, f"{question.question_id}.{sq.sub_question_id}", policy))

        return errors

    def _walk_sub_question(
        self, sq: SubQuestion, path: str, policy: NumericPolicy
    ) -> List[Annotation]:
        """INV-2, recursively, over the criteria-XOR-sub_questions tree.

        BEFORE PR-3 this was a FLAT loop that summed `sq.criteria` on every
        sub-question. Two consequences, both fixed here:
          * a PARENT (whose criteria live on its children) summed to 0 and ALWAYS
            failed -> every nested rubric was rejected outright (bagrut q1.א, q1.ב);
          * the parent's CHILDREN were never visited, so the faithful teacher error
            one level down (q1.א.2: 1.5+0.5 under a declared 3) was NEVER SEEN.
            The flat loop masked the very error the rubric gate exists to surface.

        `target_id` is the FULL PATH (q1.א.2) so the editor can anchor the
        rejection to the node the teacher must actually fix.
        """
        errors: List[Annotation] = []

        if sq.sub_questions:
            # Parent: declared points must equal the sum of its children's DECLARED
            # points. StructureExclusivity guarantees its own criteria list is empty.
            child_sum = sum(isq.points for isq in sq.sub_questions)
            diff = abs(sq.points - child_sum)
            if diff > policy.sum_tolerance:
                errors.append(_invariant_error(
                    invariant="INV-2",
                    target_id=path,
                    expected=sq.points, actual=child_sum,
                    message=(
                        f"Sub-question {path}: nested-part sum ({child_sum}) differs "
                        f"from declared points ({sq.points}) by {diff}"
                    ),
                    message_he=(
                        f"סעיף {path}: סכום "
                        f"ניקוד תת-הסעיפים "
                        f"({_fmt(child_sum)}) שונה מהניקוד "
                        f"המוצהר ({_fmt(sq.points)})"
                    ),
                ))
            for isq in sq.sub_questions:
                errors.extend(self._walk_sub_question(
                    isq, f"{path}.{isq.sub_question_id}", policy))
        else:
            # Leaf: declared points must equal the sum of its criteria.
            crit_sum = sum(c.points for c in sq.criteria)
            diff = abs(sq.points - crit_sum)
            if diff > policy.sum_tolerance:
                errors.append(_invariant_error(
                    invariant="INV-2",
                    target_id=path,
                    expected=sq.points, actual=crit_sum,
                    message=(
                        f"Sub-question {path}: criteria sum ({crit_sum}) differs "
                        f"from declared points ({sq.points}) by {diff}"
                    ),
                    message_he=(
                        f"סעיף {path}: סכום "
                        f"רכיבי הניקוד "
                        f"({_fmt(crit_sum)}) שונה מהניקוד "
                        f"המוצהר ({_fmt(sq.points)})"
                    ),
                ))

        return errors

    def _validate_point_sum_criterion(
        self,
        response: ExtractRubricResponse,
        policy: NumericPolicy
    ) -> List[Annotation]:
        """
        INV-3: SubCriteriaPointsSum

        When a criterion has sub_criteria, their points must sum to criterion.points.
        Vacuously satisfied when sub_criteria is None or empty.

        Checks all criteria: direct + inside sub-questions.
        Returns list of error annotations (does NOT mutate input).
        """
        errors: List[Annotation] = []

        for question in response.questions:
            for criterion in question.all_criteria:
                if not criterion.sub_criteria:
                    continue  # vacuously satisfied
                sub_sum = sum(sc.points for sc in criterion.sub_criteria)
                diff = abs(criterion.points - sub_sum)
                if diff > policy.sum_tolerance:
                    errors.append(_invariant_error(
                        invariant="INV-3",
                        target_id=criterion.criterion_id,
                        expected=criterion.points, actual=sub_sum,
                        message=(
                            f"Criterion {criterion.criterion_id}: sub-criteria sum ({sub_sum}) "
                            f"differs from declared points ({criterion.points}) by {diff}"
                        ),
                        message_he=(
                            f"רכיב {criterion.criterion_id}: סכום תתי-הרכיבים "
                            f"({_fmt(sub_sum)}) שונה מהניקוד המוצהר ({_fmt(criterion.points)})"
                        ),
                    ))

        return errors

    def _validate_point_sum_rubric(
        self,
        response: ExtractRubricResponse,
        policy: NumericPolicy
    ) -> List[Annotation]:
        """
        INV-4: RubricPointsSum — ACHIEVABLE-AWARE (PR-3).

        `total_points` means ACHIEVABLE, everywhere, by definition (R4). The Draft
        already said so (the extraction pipeline sets it via
        _achievable_from_extraction); the Contract now agrees, which resolves the
        Draft/Contract semantic split that made every selection exam a hard
        dead-end after a successful extraction.

            achievable = Σ(mandatory question totals) + Σ over groups of [top-k totals]

        With NO selection groups this reduces EXACTLY to the legacy Σ check — which
        is the back-compat proof for the 40 stored contracts (all selection-free ⇒
        achievable ≡ offered ⇒ zero behavioral change on re-parse).

        Before PR-3 this compared Σ offered vs declared, so employee (offered 100,
        achievable 50) and bagrut (offered 150, achievable 100) could never compile.
        """
        achievable = compute_achievable_points(
            response.questions, response.selection_groups
        )
        expected = response.total_points
        diff = abs(achievable - expected)
        if diff > policy.sum_tolerance:
            offered = sum(q.total_points for q in response.questions)
            detail = (
                f" (offered {offered}, achievable {achievable} after selection)"
                if response.selection_groups else ""
            )
            return [_invariant_error(
                invariant="INV-4",
                target_id=None,
                expected=expected, actual=achievable,
                message=(
                    f"Achievable points ({achievable}) differ from the rubric's "
                    f"declared total ({expected}) by {diff}{detail}"
                ),
                message_he=(
                    f"הניקוד הניתן להשגה ({_fmt(achievable)}) שונה מסך הניקוד "
                    f"המוצהר של המחוון ({_fmt(expected)})"
                ),
            )]
        return []
    
    def _check_criterion_alignment(
        self, 
        response: ExtractRubricResponse
    ) -> List[Annotation]:
        """
        Invariant 6: CriterionAlignment (WARNING only)
        
        Every criterion should link to at least one SkillTarget or Requirement.
        Checks all criteria: direct + inside sub-questions.
        
        Returns list of warning annotations (does NOT mutate input).
        """
        warnings: List[Annotation] = []
        
        # Build set of existing alignment warnings to avoid duplicates
        existing_alignment_targets = {
            a.target_id 
            for a in response.annotations 
            if a.annotation_type == "narrowness_issue"
        }
        
        for question in response.questions:
            for criterion in question.all_criteria:
                if not criterion.is_aligned:
                    # Only add if not already annotated
                    if criterion.criterion_id not in existing_alignment_targets:
                        warnings.append(Annotation(
                            annotation_type="narrowness_issue",
                            # PR-3 (R1): INFO, NOT WARNING — non-blocking.
                            # This check fired on 100% of criteria (extraction produces
                            # no skill_targets/requirements — that is a future feature,
                            # not a defect) and the frontend auto-acknowledged 100% of
                            # them. A check nobody can pass is worse than no check: it
                            # trains the click-through reflex that will swallow the next
                            # REAL warning. Kept as INFO so the future skill-mapping
                            # feature has its hook, demoted so clean rubrics compile in
                            # ONE round trip instead of a two-call ack dance.
                            severity=AnnotationSeverity.INFO,
                            invariant="INV-6",
                            message=(
                                f"Criterion '{criterion.description[:50]}...' is not linked "
                                "to any skill target or requirement"
                            ),
                            message_he=(
                                "הרכיב אינו מקושר למיומנות או לדרישה "
                                "(מידע בלבד — אינו חוסם שמירה)"
                            ),
                            target_id=criterion.criterion_id
                        ))

        return warnings


def compile_rubric(
    response: ExtractRubricResponse,
    policy: NumericPolicy = None,
    acknowledged_warnings: List[str] = None
) -> GradingRubricContract:
    """
    Convenience function to compile a rubric response.
    
    Equivalent to ContractCompiler().compile(response, policy).
    """
    return ContractCompiler().compile(response, policy, acknowledged_warnings)
