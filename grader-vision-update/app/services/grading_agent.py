"""
Enhanced LangGraph-based grading agent.

WORLD-CLASS FEATURES:
- Rule-by-rule evaluation with index-based matching
- Pydantic-enforced LLM output validation
- Validation & repair layer for 100% rule coverage
- Retry with exponential backoff
- GradingTrace observability
- Backward compatibility with legacy rubric format
"""
import json
import logging
import asyncio
import time
from typing import Dict, List, TypedDict, Literal, Any, Optional
from pydantic import ValidationError

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END

from ..config import settings
from ..schemas.grading_agent_models import (
    ConfidenceLevel,
    GradingRule,
    GradingCriterion,
    GradingQuestion,
    NormalizedRubric,
    RuleVerdict,
    CriterionEvaluation,
    GradingLLMResponse,
    CriterionResult,
    QuestionResult,
    GradingResult,
    GradingTrace,
)
from .rubric_normalizer import normalize_rubric

logger = logging.getLogger(__name__)


# =============================================================================
# GRADING STATE
# =============================================================================

class GradingState(TypedDict):
    """State for the grading workflow."""
    rubric: Dict                        # Raw rubric (normalized internally)
    normalized_rubric: Optional[NormalizedRubric]
    student_tests: List[Dict]
    current_test_index: int
    graded_results: List[Dict]
    low_confidence_notes: List[str]
    teacher_email: str
    original_message_id: str


# =============================================================================
# PROMPTS
# =============================================================================

RULE_GRADING_SYSTEM_PROMPT = """You are a world-class Computer Science teacher grading high school programming tests.

═══════════════════════════════════════════════════════════════════════════════
GRADING METHODOLOGY: Rule-by-Rule Evaluation
═══════════════════════════════════════════════════════════════════════════════

For EACH reduction rule, you must answer: "Is this rule VIOLATED?"

Verdicts:
- PASS = Student code SATISFIES this requirement (no deduction)
- FAIL = Student code VIOLATES this requirement (points deducted)

Process for each rule:
1. FIND: Search student code for relevant implementation
2. DECIDE: Is the rule violated? (YES=FAIL, NO=PASS)
3. QUOTE: Copy exact code evidence
4. EXPLAIN: Brief Hebrew explanation

═══════════════════════════════════════════════════════════════════════════════
CONFIDENCE CALIBRATION
═══════════════════════════════════════════════════════════════════════════════

Assign confidence based on evidence quality:
- HIGH: Found exact matching/non-matching code (>95% sure)
- MEDIUM: Code is ambiguous, uses non-standard patterns (70-95% sure)  
- LOW: Cannot find relevant code, transcription unclear, guessing (<70%)

When confidence is LOW, still make your best guess - teacher will review.

═══════════════════════════════════════════════════════════════════════════════
CRITICAL REQUIREMENTS
═══════════════════════════════════════════════════════════════════════════════

1. Evaluate EVERY rule by its [index] - never skip any
2. Output the EXACT rule_index from the prompt
3. ALWAYS provide code evidence or "לא נמצא קוד רלוונטי"
4. Explanations in Hebrew

═══════════════════════════════════════════════════════════════════════════════
OUTPUT FORMAT (JSON only)
═══════════════════════════════════════════════════════════════════════════════

{
  "evaluations": [
    {
      "criterion_index": 0,
      "rule_verdicts": [
        {
          "rule_index": 0,
          "verdict": "PASS",
          "evidence": "נמצא: private int _id;",
          "confidence": "high",
          "explanation": "השדה הוגדר כנדרש"
        },
        {
          "rule_index": 1,
          "verdict": "FAIL",
          "evidence": "לא נמצא שדה name בקוד",
          "confidence": "high",
          "explanation": "חסר הגדרת שדה name"
        }
      ]
    }
  ],
  "rubric_mismatch_detected": false,
  "rubric_mismatch_reason": null,
  "low_confidence_items": []
}"""


# =============================================================================
# GRADING AGENT
# =============================================================================

class GradingAgent:
    """
    Enhanced grading agent with rule-by-rule evaluation.
    
    Key features:
    - Normalizes any rubric format to canonical models
    - Index-based rule matching (100% reliable)
    - Pydantic validation of LLM output
    - Validation + repair layer for missing rules
    - Retry with exponential backoff
    - Observability via GradingTrace
    """
    
    def __init__(self):
        """Initialize the grading agent with JSON mode enabled."""
        model_name = getattr(settings, 'openai_model', None) or "gpt-4-turbo-preview"
        
        logger.info(f"Initializing EnhancedGradingAgent with model: {model_name}")
        
        self.llm = ChatOpenAI(
            model=model_name,
            temperature=0.15,  # Lower for more deterministic grading
            max_tokens=14384,
            api_key=settings.openai_api_key,
            model_kwargs={"response_format": {"type": "json_object"}}
        )
        
        self.max_retries = 3
        self.timeout_seconds = getattr(settings, 'grading_timeout_seconds', 60)
        
        self.workflow = self._build_workflow()
        logger.info("EnhancedGradingAgent initialized successfully")
    
    def grade_tests(
        self,
        rubric: Dict,
        student_tests: List[Dict],
        teacher_email: str,
        original_message_id: str
    ) -> Dict:
        """
        Public entry point to run the grading workflow.
        
        Returns dict with:
        - graded_results: List of grading results (legacy format)
        - low_confidence_notes: List of items needing review
        """
        logger.info("=" * 80)
        logger.info("STARTING ENHANCED GRADING WORKFLOW")
        logger.info(f"Number of student tests: {len(student_tests)}")
        logger.info("=" * 80)
        
        # Normalize rubric at entry point
        normalized = normalize_rubric(rubric)
        
        initial_state: GradingState = {
            "rubric": rubric,
            "normalized_rubric": normalized,
            "student_tests": student_tests,
            "current_test_index": 0,
            "graded_results": [],
            "low_confidence_notes": [],
            "teacher_email": teacher_email,
            "original_message_id": original_message_id
        }
        
        final_state = self.workflow.invoke(
            initial_state,
            config={
                "tags": ["grading-workflow", f"model-{self.llm.model_name}"],
                "metadata": {
                    "teacher_email": teacher_email,
                    "test_count": len(student_tests),
                }
            }
        )
        
        logger.info("=" * 80)
        logger.info("ENHANCED GRADING WORKFLOW COMPLETE")
        logger.info(f"Total results: {len(final_state['graded_results'])}")
        logger.info("=" * 80)
        
        return {
            "graded_results": final_state["graded_results"],
            "low_confidence_notes": final_state["low_confidence_notes"]
        }
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(GradingState)
        
        workflow.add_node("initialize", self._initialize_grading)
        workflow.add_node("grade_single_test", self._grade_single_test)
        workflow.add_node("compile_results", self._compile_results)
        
        workflow.set_entry_point("initialize")
        workflow.add_edge("initialize", "grade_single_test")
        
        workflow.add_conditional_edges(
            "grade_single_test",
            self._should_continue_grading,
            {
                "continue": "grade_single_test",
                "finish": "compile_results"
            }
        )
        
        workflow.add_edge("compile_results", END)
        return workflow.compile()
    
    def _initialize_grading(self, state: GradingState) -> Dict:
        """Initialize grading batch."""
        normalized = state.get("normalized_rubric")
        if normalized:
            logger.info(f"Rubric: {len(normalized.questions)} questions, "
                       f"{normalized.total_criteria} criteria, "
                       f"{normalized.total_rules} rules")
        logger.info(f"Students to grade: {len(state['student_tests'])}")
        return {}
    
    def _grade_single_test(self, state: GradingState) -> Dict:
        """Grade a single student test using rule-by-rule evaluation."""
        current_idx = state["current_test_index"]
        student_test = state["student_tests"][current_idx]
        normalized = state.get("normalized_rubric")
        
        logger.info("=" * 80)
        logger.info(f"GRADING TEST {current_idx + 1}/{len(state['student_tests'])}")
        logger.info(f"Student: {student_test.get('student_name')}")
        logger.info("=" * 80)
        
        grading_result = None
        new_low_confidence = []
        
        try:
            if normalized:
                result = self._grade_with_rules(normalized, student_test)
                grading_result = result.to_legacy_format()
                
                # Collect low confidence items
                for qr in result.question_results:
                    for cr in qr.criterion_results:
                        if cr.low_confidence_count > 0:
                            new_low_confidence.append(
                                f"{student_test.get('student_name')}: Q{qr.question_number} - {cr.criterion.description[:40]}..."
                            )
            else:
                # Fallback to legacy grading
                grading_result = self._grade_legacy(state["rubric"], student_test)
            
            logger.info(f"✅ Grading complete: {grading_result.get('total_score')}/{grading_result.get('total_possible')}")
            
        except Exception as e:
            logger.error(f"Error grading test: {e}", exc_info=True)
            grading_result = {
                "student_name": student_test.get("student_name", "Unknown"),
                "filename": student_test.get("filename"),
                "total_score": 0,
                "total_possible": 0,
                "percentage": 0,
                "error": str(e),
                "question_grades": [],
                "grades": [],
            }
            new_low_confidence.append(f"{student_test.get('student_name')}: Error - {str(e)}")
        
        return {
            "current_test_index": current_idx + 1,
            "graded_results": state["graded_results"] + [grading_result],
            "low_confidence_notes": state["low_confidence_notes"] + new_low_confidence
        }
    
    def _grade_with_rules(
        self, 
        rubric: NormalizedRubric, 
        student_test: Dict
    ) -> GradingResult:
        """Grade using rule-by-rule evaluation."""
        question_results = []
        
        for question in rubric.questions:
            # Get student answer for this question
            student_code = self._get_student_answer(student_test, question.question_number)
            
            # Build prompt
            prompt = self._build_rule_prompt(question, student_code)
            
            # Grade with retry
            trace = GradingTrace(
                question_number=question.question_number,
                criterion_count=len(question.all_criteria),
                rule_count=sum(len(c.rules) for c in question.all_criteria),
                student_code_length=len(student_code),
            )
            
            start_time = time.time()
            
            try:
                llm_response = self._call_llm_with_retry(prompt, trace)
                criterion_results = self._validate_and_repair(llm_response, question, trace)
            except Exception as e:
                logger.error(f"LLM grading failed for Q{question.question_number}: {e}")
                criterion_results = self._create_fallback_results(question)
                trace.parse_success = False
                trace.validation_errors.append(str(e))
            
            trace.llm_latency_ms = int((time.time() - start_time) * 1000)
            trace.final_score = sum(cr.points_earned for cr in criterion_results)
            trace.total_possible = sum(cr.criterion.total_points for cr in criterion_results)
            
            logger.info(trace.log_summary())
            
            question_results.append(QuestionResult(
                question_number=question.question_number,
                criterion_results=criterion_results,
            ))
        
        return GradingResult(
            student_name=student_test.get("student_name", "Unknown"),
            filename=student_test.get("filename"),
            question_results=question_results,
        )
    
    def _build_rule_prompt(self, question: GradingQuestion, student_code: str) -> str:
        """Build prompt with indexed rules for reliable matching."""
        prompt = f"=== QUESTION {question.question_number} ===\n\n"
        
        for criterion in question.all_criteria:
            prompt += f"CRITERION [{criterion.index}]: {criterion.description}\n"
            prompt += f"Total Points: {criterion.total_points}\n"
            prompt += "REDUCTION RULES (evaluate EACH by index):\n"
            
            for rule in criterion.rules:
                prompt += f"  [{rule.index}] {rule.description} (-{rule.deduction_points} pts)\n"
            prompt += "\n"
        
        prompt += "=" * 50 + "\n"
        prompt += "=== STUDENT CODE ===\n"
        
        if student_code.strip():
            prompt += f"```\n{student_code}\n```\n"
        else:
            prompt += "⚠️ NO CODE SUBMITTED - Grade all rules as FAIL\n"
        
        prompt += "\n" + "=" * 50 + "\n"
        prompt += "Grade EVERY rule by its [index]. Output JSON only."
        
        return prompt
    
    def _call_llm_with_retry(self, prompt: str, trace: GradingTrace) -> GradingLLMResponse:
        """Call LLM with retry and Pydantic validation."""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                messages = [
                    SystemMessage(content=RULE_GRADING_SYSTEM_PROMPT),
                    HumanMessage(content=prompt)
                ]
                
                response = self.llm.invoke(messages)
                raw_content = response.content
                
                trace.raw_response_preview = raw_content[:500]
                
                # Clean markdown wrappers
                cleaned = self._clean_json_response(raw_content)
                
                # Parse and validate with Pydantic
                parsed = GradingLLMResponse.model_validate_json(cleaned)
                trace.parse_success = True
                
                return parsed
                
            except (ValidationError, json.JSONDecodeError) as e:
                last_error = e
                wait_time = 2 ** attempt
                logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
                trace.validation_errors.append(f"Attempt {attempt + 1}: {str(e)}")
        
        raise last_error or Exception("All retries failed")
    
    def _validate_and_repair(
        self, 
        response: GradingLLMResponse, 
        question: GradingQuestion,
        trace: GradingTrace
    ) -> List[CriterionResult]:
        """Ensure 100% rule coverage, repair missing evaluations."""
        results = []
        
        # Build lookup by criterion index
        eval_lookup = {e.criterion_index: e for e in response.evaluations}
        
        for criterion in question.all_criteria:
            evaluation = eval_lookup.get(criterion.index)
            
            # Build lookup by rule index
            verdict_lookup = {}
            if evaluation:
                verdict_lookup = {v.rule_index: v for v in evaluation.rule_verdicts}
            
            verdicts = []
            for rule in criterion.rules:
                verdict = verdict_lookup.get(rule.index)
                
                if verdict:
                    verdicts.append(verdict)
                    trace.rules_evaluated += 1
                else:
                    # Missing rule → conservative fallback
                    verdicts.append(RuleVerdict(
                        rule_index=rule.index,
                        verdict="FAIL",
                        evidence="Not evaluated by AI",
                        confidence=ConfidenceLevel.LOW,
                        explanation="נדרשת בדיקה ידנית"
                    ))
                    trace.rules_repaired += 1
                    logger.warning(f"Repaired missing rule [{rule.index}]: {rule.description[:30]}...")
            
            # Calculate score
            deductions = sum(
                criterion.rules[v.rule_index].deduction_points
                for v in verdicts 
                if v.verdict == "FAIL" and v.rule_index < len(criterion.rules)
            )
            earned = max(0, criterion.total_points - deductions)
            
            low_conf_count = sum(1 for v in verdicts if v.confidence == ConfidenceLevel.LOW)
            trace.low_confidence_count += low_conf_count
            
            results.append(CriterionResult(
                criterion=criterion,
                verdicts=verdicts,
                points_earned=earned,
                points_deducted=deductions,
                fully_evaluated=low_conf_count == 0,
            ))
        
        return results
    
    def _create_fallback_results(self, question: GradingQuestion) -> List[CriterionResult]:
        """Create fallback results when LLM completely fails."""
        results = []
        
        for criterion in question.all_criteria:
            verdicts = [
                RuleVerdict(
                    rule_index=rule.index,
                    verdict="FAIL",
                    evidence="LLM failure - manual review required",
                    confidence=ConfidenceLevel.LOW,
                    explanation="שגיאת מערכת - נדרשת בדיקה ידנית"
                )
                for rule in criterion.rules
            ]
            
            results.append(CriterionResult(
                criterion=criterion,
                verdicts=verdicts,
                points_earned=0,
                points_deducted=criterion.total_points,
                fully_evaluated=False,
            ))
        
        return results
    
    def _get_student_answer(self, student_test: Dict, question_number: int) -> str:
        """Get student's answer for a specific question."""
        answers = student_test.get("answers", [])
        
        # Find matching answer
        for ans in answers:
            if ans.get("question_number") == question_number:
                return ans.get("answer_text", "")
        
        # Try to find any answer for this question (including sub-questions)
        matching = [a for a in answers if a.get("question_number") == question_number]
        if matching:
            return "\n\n".join(a.get("answer_text", "") for a in matching)
        
        return ""
    
    def _clean_json_response(self, content: str) -> str:
        """Clean markdown wrappers from LLM response."""
        cleaned = content.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1]) if len(lines) > 2 else cleaned
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
        return cleaned
    
    def _grade_legacy(self, rubric: Dict, student_test: Dict) -> Dict:
        """Fallback legacy grading when normalization not available."""
        # Just return minimal result
        return {
            "student_name": student_test.get("student_name", "Unknown"),
            "filename": student_test.get("filename"),
            "total_score": 0,
            "total_possible": 0,
            "percentage": 0,
            "question_grades": [],
            "grades": [],
            "error": "Legacy grading not implemented in enhanced agent"
        }
    
    def _should_continue_grading(self, state: GradingState) -> Literal["continue", "finish"]:
        """Determine if we should continue grading more tests."""
        if state["current_test_index"] < len(state["student_tests"]):
            return "continue"
        return "finish"
    
    def _compile_results(self, state: GradingState) -> Dict:
        """Compile and summarize all grading results."""
        results = state["graded_results"]
        logger.info(f"Compiled {len(results)} grading results")
        
        if results:
            valid = [r for r in results if r.get("total_possible", 0) > 0]
            if valid:
                scores = [r.get("percentage", 0) for r in valid]
                logger.info(f"Score summary: avg={sum(scores)/len(scores):.1f}%, "
                           f"min={min(scores):.1f}%, max={max(scores):.1f}%")
        
        return {}