"""
LangGraph-based grading agent.
ENHANCED VERSION: Uses reduction_rules for rule-by-rule evaluation.
"""
import json
import logging
from typing import Dict, List, TypedDict, Literal, Optional, Any
from difflib import SequenceMatcher
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END

from .config import settings

logger = logging.getLogger(__name__)


# =============================================================================
# System Prompt for Rule-Based Grading
# =============================================================================

GRADING_SYSTEM_PROMPT = """אתה מורה מומחה לתכנות C# עם ניסיון של 20 שנה בהוראה ובדיקת מבחנים.
אתה בודק מבחן של תלמיד תיכון בקורס מדעי המחשב.

# שיטת הבדיקה - הערכה לפי כללי הורדה

לכל קריטריון במחוון יש:
1. תיאור הקריטריון
2. סה"כ נקודות
3. כללי הורדה (reduction_rules) - כל כלל מציין טעות ספציפית וכמה נקודות להוריד

**חישוב הניקוד:**
נקודות_שהתקבלו = סה"כ_נקודות - סכום(כללים_שהופרו)

# הוראות בדיקה

1. **בדוק כל כלל הורדה בנפרד**
   - עבור על כל reduction_rule ובדוק אם הקוד של התלמיד מפר אותו
   - אם הכלל הופר - הוסף אותו ל-applied_deductions עם הסבר
   - אם הכלל לא הופר - הוסף את שמו ל-rules_passed

2. **צטט את הקוד הרלוונטי**
   - בשדה student_code_snippet, העתק את החלק הרלוונטי מקוד התלמיד
   - זה חייב להיות ציטוט מדויק, לא פרפרזה

3. **סמן כללים מפורשים vs מוסקים**
   - כללים עם is_explicit: true הם מהמחוון המקורי
   - כללים עם is_explicit: false הם שהוסקו על ידי AI
   - שניהם נבדקים ומוחלים באותו אופן

4. **טיפול בתשובה חסרה**
   - אם אין קוד/תשובה לקריטריון זה:
     - סמן unable_to_grade: true
     - סמן unable_to_grade_reason: "תשובת התלמיד חסרה"
     - השאר points_earned: null

5. **הצעות AI לטעויות נוספות**
   - אם זיהית טעות משמעותית שלא מכוסה בכללים הקיימים, הוסף ל-ai_suggested_deductions
   - **אל תציע הורדות על:** שגיאות כתיב, רגישות לאותיות גדולות/קטנות, רווחים, פורמט
   - **כן תציע הורדות על:** שגיאות לוגיות, מקרי קצה לא מטופלים, בעיות נכונות

6. **התחשב בהקשר**
   - זכור שזה מבחן תיכון, לא קוד production
   - התחשב בטעויות תמלול קלות (OCR artifacts)
   - אם הכוונה ברורה למרות טעות קטנה - אל תוריד נקודות

# דוגמה

**קריטריון:** "חתימת הפעולה נכונה" (1.5 נקודות)
**כללי הורדה:**
- "חסר static" (0.5) [is_explicit: true]
- "שם הפעולה שגוי" (0.5) [is_explicit: true]
- "פרמטרים שגויים" (0.5) [is_explicit: false]

**קוד התלמיד:**
```csharp
public void AddStudent(string name) {
    // implementation
}
```

**תוצאה:**
```json
{
  "criterion_description": "חתימת הפעולה נכונה",
  "total_points": 1.5,
  "points_earned": 1.0,
  "student_code_snippet": "public void AddStudent(string name)",
  "applied_deductions": [
    {
      "rule_description": "חסר static",
      "reduction_value": 0.5,
      "is_explicit": true,
      "explanation": "הפעולה מוגדרת כ-instance method במקום static method"
    }
  ],
  "rules_passed": ["שם הפעולה נכון - AddStudent", "פרמטרים נכונים - string name"],
  "ai_suggested_deductions": [],
  "unable_to_grade": false,
  "unable_to_grade_reason": null
}
```

# פורמט הפלט

החזר JSON בלבד, ללא טקסט נוסף. עקוב אחרי הסכמה הבאה:

```json
{
  "grades": [
    {
      "question_number": 1,
      "sub_question_id": "א",
      "criterion_description": "תיאור הקריטריון",
      "total_points": 1.5,
      "points_earned": 1.0,
      "student_code_snippet": "קטע קוד רלוונטי",
      "applied_deductions": [
        {
          "rule_description": "תיאור הכלל שהופר",
          "reduction_value": 0.5,
          "is_explicit": true,
          "explanation": "הסבר בעברית"
        }
      ],
      "rules_passed": ["כלל 1 שעבר", "כלל 2 שעבר"],
      "ai_suggested_deductions": [],
      "unable_to_grade": false,
      "unable_to_grade_reason": null
    }
  ]
}
```
"""


class GradingState(TypedDict):
    """State for the grading workflow."""
    rubric: Dict
    student_tests: List[Dict]
    current_test_index: int
    graded_results: List[Dict]
    low_confidence_notes: List[str]
    teacher_email: str
    original_message_id: str


class GradingValidationError(Exception):
    """Raised when grading response fails validation."""
    pass


class GradingAgent:
    """Agent that grades student tests using GPT-4 and rubric criteria with reduction_rules."""
    
    def __init__(self):
        """Initialize the grading agent with JSON mode enabled."""
        
        model_name = settings.openai_model if settings.openai_model else "gpt-4o"
        
        logger.info(f"Initializing GradingAgent with model: {model_name}")
        
        self.llm = ChatOpenAI(
            model=model_name,
            temperature=0.2,
            api_key=settings.openai_api_key,
            model_kwargs={"response_format": {"type": "json_object"}}
        )
        
        self.workflow = self._build_workflow()
        logger.info("GradingAgent initialized successfully")
    
    def grade_tests(
        self,
        rubric: Dict,
        student_tests: List[Dict],
        teacher_email: str,
        original_message_id: str
    ) -> Dict:
        """
        Public entry point to run the grading workflow.
        """
        logger.info("\n" + "=" * 80)
        logger.info("STARTING GRADING WORKFLOW (Enhanced with reduction_rules)")
        logger.info(f"Number of student tests: {len(student_tests)}")
        logger.info("=" * 80)

        initial_state: GradingState = {
            "rubric": rubric,
            "student_tests": student_tests,
            "current_test_index": 0,
            "graded_results": [],
            "low_confidence_notes": [],
            "teacher_email": teacher_email,
            "original_message_id": original_message_id
        }
        
        final_state = self.workflow.invoke(initial_state)
        
        logger.info("\n" + "=" * 80)
        logger.info("GRADING WORKFLOW COMPLETE")
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
        logger.info("=" * 80)
        logger.info("INITIALIZING GRADING WORKFLOW (Enhanced reduction_rules)")
        logger.info("=" * 80)
        logger.info(f"Rubric: {len(state['rubric'].get('questions', []))} questions")
        logger.info(f"Student tests to grade: {len(state['student_tests'])}")
        
        for q in state['rubric'].get('questions', []):
            logger.info(f"\nQuestion {q['question_number']}:")
            logger.info(f"  - Total points: {q.get('total_points', 0)}")
            criteria_count = len(q.get('criteria', []))
            for sq in q.get('sub_questions', []):
                criteria_count += len(sq.get('criteria', []))
            logger.info(f"  - Number of criteria: {criteria_count}")
        
        logger.info("\nInitialization complete. Starting grading loop...")
        return {}
    
    def _grade_single_test(self, state: GradingState) -> Dict:
        """Grade a single student test using reduction_rules."""
        current_idx = state["current_test_index"]
        student_test = state["student_tests"][current_idx]
        
        logger.info("=" * 80)
        logger.info(f"GRADING TEST {current_idx + 1}/{len(state['student_tests'])}")
        logger.info("=" * 80)
        logger.info(f"Student: {student_test.get('student_name')}")
        logger.info(f"Filename: {student_test.get('filename')}")
        
        answers = student_test.get('answers', [])
        logger.info(f"Transcribed answers: {len(answers)}")
        
        grading_result = None
        new_low_confidence = []
        
        try:
            logger.info("\nSENDING TO LLM FOR GRADING...")
            
            system_prompt = self._build_system_prompt()
            user_prompt = self._build_user_prompt(state["rubric"], student_test)
            
            logger.info(f"System prompt length: {len(system_prompt)} chars")
            logger.info(f"User prompt length: {len(user_prompt)} chars")

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = self.llm.invoke(messages)
            
            logger.info(f"LLM response length: {len(response.content)} chars")
            
            # Parse and validate response
            raw_result = self._parse_grading_response(response.content, student_test)
            grading_result = self._validate_grading_response(raw_result, state["rubric"])
            
            logger.info(f"Total score: {grading_result.get('summary', {}).get('total_score', 0):.1f}/{grading_result.get('summary', {}).get('total_possible', 0):.1f}")
            logger.info(f"Percentage: {grading_result.get('summary', {}).get('percentage', 0):.1f}%")
            logger.info(f"Number of grades: {len(grading_result.get('grades', []))}")
            
            # Check for AI suggestions
            if grading_result.get('summary', {}).get('has_ai_suggestions'):
                logger.warning("⚠️ This test has AI-suggested deductions for teacher review")
                new_low_confidence.append(
                    f"Test: {student_test['student_name']} - Has AI-suggested additional deductions"
                )
            
            # Check for items that couldn't be graded
            unable_count = grading_result.get('summary', {}).get('criteria_unable_to_grade', 0)
            if unable_count > 0:
                logger.warning(f"⚠️ {unable_count} criteria could not be graded (missing answers)")
                new_low_confidence.append(
                    f"Test: {student_test['student_name']} - {unable_count} criteria require manual review"
                )
            
            logger.info(f"✅ Grading complete for {student_test['student_name']}")

        except Exception as e:
            logger.error(f"Error grading test: {e}", exc_info=True)
            grading_result = {
                "student_name": student_test.get("student_name", "Unknown"),
                "filename": student_test.get("filename", "Unknown"),
                "error": str(e),
                "grades": [],
                "summary": {
                    "total_score": 0,
                    "total_possible": 0,
                    "percentage": 0,
                    "has_ai_suggestions": False,
                    "criteria_unable_to_grade": 0
                }
            }
            new_low_confidence.append(f"Test: {student_test.get('student_name')}, Error: {str(e)}")
        
        # Add student info to result
        if "student_name" not in grading_result:
            grading_result["student_name"] = student_test.get("student_name", "Unknown")
        if "filename" not in grading_result:
            grading_result["filename"] = student_test.get("filename", "Unknown")
        
        # Return NEW lists (immutable update pattern)
        updated_results = state["graded_results"] + [grading_result]
        updated_notes = state["low_confidence_notes"] + new_low_confidence
        
        return {
            "current_test_index": current_idx + 1,
            "graded_results": updated_results,
            "low_confidence_notes": updated_notes
        }
    
    def _should_continue_grading(self, state: GradingState) -> Literal["continue", "finish"]:
        """Determine if we should continue grading more tests."""
        current_idx = state["current_test_index"]
        total_tests = len(state["student_tests"])
        
        logger.info(f"Check continue: index={current_idx}, total={total_tests}")
        
        if current_idx < total_tests:
            logger.info("→ Continuing to next test")
            return "continue"
        else:
            logger.info("→ All tests graded, finishing...")
            return "finish"
    
    def _compile_results(self, state: GradingState) -> Dict:
        """Compile and summarize all grading results."""
        logger.info("=" * 80)
        logger.info("COMPILING FINAL RESULTS")
        logger.info("=" * 80)
        
        results = state["graded_results"]
        logger.info(f"Total tests graded: {len(results)}")
        logger.info(f"Low confidence items: {len(state['low_confidence_notes'])}")
        
        if results:
            valid_results = [r for r in results if r.get('summary', {}).get('total_possible', 0) > 0]
            if valid_results:
                scores = [r.get('summary', {}).get('percentage', 0) for r in valid_results]
                logger.info(f"\nScore summary:")
                logger.info(f"  - Average: {sum(scores) / len(scores):.1f}%")
                logger.info(f"  - Min: {min(scores):.1f}%")
                logger.info(f"  - Max: {max(scores):.1f}%")
        
        return {}
    
    def _build_system_prompt(self) -> str:
        """Build system prompt for rule-based grading."""
        return GRADING_SYSTEM_PROMPT
    
    def _build_user_prompt(self, rubric: Dict, student_test: Dict) -> str:
        """Build user prompt with rubric (including reduction_rules) and student answers."""
        prompt_parts = []
        
        # Part 1: Rubric
        prompt_parts.append("=" * 50)
        prompt_parts.append("# מחוון הבדיקה")
        prompt_parts.append("=" * 50)
        
        for question in rubric.get('questions', []):
            q_num = question.get('question_number', '?')
            q_points = question.get('total_points', 0)
            prompt_parts.append(f"\n## שאלה {q_num} ({q_points} נקודות)")
            
            # Check if question has sub-questions
            sub_questions = question.get('sub_questions', [])
            if sub_questions:
                for sub_q in sub_questions:
                    sub_id = sub_q.get('sub_question_id', '')
                    sub_points = sub_q.get('total_points', 0)
                    prompt_parts.append(f"\n### סעיף {sub_id} ({sub_points} נקודות)")
                    
                    for criterion in sub_q.get('criteria', []):
                        self._format_criterion(criterion, prompt_parts, q_num, sub_id)
            else:
                # Direct criteria (no sub-questions)
                for criterion in question.get('criteria', []):
                    self._format_criterion(criterion, prompt_parts, q_num, None)
        
        # Part 2: Student Answers
        prompt_parts.append("\n" + "=" * 50)
        prompt_parts.append("# תשובות התלמיד")
        prompt_parts.append("=" * 50)
        
        answers = student_test.get('answers', [])
        if not answers:
            prompt_parts.append("\n**[אין תשובות - התלמיד לא ענה על השאלות]**")
        else:
            for answer in answers:
                q_num = answer.get('question_number', '?')
                sub_id = answer.get('sub_question_id')
                content = answer.get('answer_text', '').strip()
                
                if sub_id:
                    prompt_parts.append(f"\n## שאלה {q_num} סעיף {sub_id}")
                else:
                    prompt_parts.append(f"\n## שאלה {q_num}")
                
                if content:
                    prompt_parts.append("```csharp")
                    prompt_parts.append(content)
                    prompt_parts.append("```")
                else:
                    prompt_parts.append("**[תשובה חסרה - התלמיד לא ענה]**")
        
        # Part 3: Instructions
        prompt_parts.append("\n" + "=" * 50)
        prompt_parts.append("# הוראות")
        prompt_parts.append("=" * 50)
        prompt_parts.append("בדוק כל קריטריון לפי כללי ההורדה. החזר JSON בלבד לפי הסכמה.")
        
        return "\n".join(prompt_parts)

    def _format_criterion(
        self, 
        criterion: Dict, 
        prompt_parts: List[str],
        question_number: int,
        sub_question_id: Optional[str]
    ) -> None:
        """Format a single criterion with its reduction rules for the prompt."""
        # Support both old format (description/points) and new format (criterion_description/total_points)
        description = criterion.get('criterion_description') or criterion.get('description', 'Unknown')
        total_points = criterion.get('total_points') or criterion.get('points', 0)
        
        prompt_parts.append(f"\n**קריטריון:** {description}")
        prompt_parts.append(f"**נקודות:** {total_points}")
        
        # Add reduction rules if present
        reduction_rules = criterion.get('reduction_rules', [])
        if reduction_rules:
            prompt_parts.append("**כללי הורדה:**")
            for rule in reduction_rules:
                rule_desc = rule.get('description', '')
                rule_value = rule.get('reduction_value', 0)
                is_explicit = rule.get('is_explicit', True)
                marker = "[מחוון]" if is_explicit else "[מוסק]"
                prompt_parts.append(f"  - {rule_desc} ({rule_value} נק') {marker}")
        else:
            # Old format without reduction_rules - create implicit rule
            prompt_parts.append("**כללי הורדה:**")
            prompt_parts.append(f"  - הקריטריון לא מתקיים ({total_points} נק') [מחוון]")

    def _parse_grading_response(self, response_text: str, student_test: Dict) -> Dict:
        """Parse JSON response safely."""
        try:
            # Clean markdown wrappers
            cleaned = response_text.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                cleaned = "\n".join(lines[1:-1]) if len(lines) > 2 else cleaned
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:].strip()
            
            data = json.loads(cleaned)
            
            # Add student info
            data["student_name"] = student_test.get("student_name", "Unknown")
            data["filename"] = student_test.get("filename", "Unknown")
            
            return data
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON Parsing failed: {e}")
            logger.error(f"Raw response: {response_text[:500]}...")
            raise
    
    def _validate_grading_response(self, response: Dict, rubric: Dict) -> Dict:
        """
        Validate and auto-correct LLM grading response.
        
        Checks:
        1. All referenced criteria exist in rubric
        2. All applied deductions reference valid rules
        3. Points math is correct
        4. No points_earned exceeds total_points
        5. No negative points_earned
        
        Auto-corrections:
        - Recalculates points_earned if math is wrong
        - Clamps points_earned to [0, total_points]
        - Moves deductions referencing non-existent rules to ai_suggested_deductions
        """
        grades = response.get("grades", [])
        
        for grade in grades:
            # Skip validation for unable_to_grade items
            if grade.get("unable_to_grade"):
                grade["points_earned"] = None
                grade["applied_deductions"] = []
                continue
            
            # Find matching criterion in rubric
            criterion = self._find_criterion_in_rubric(
                rubric,
                grade.get("question_number"),
                grade.get("sub_question_id"),
                grade.get("criterion_description", "")
            )
            
            if not criterion:
                logger.warning(f"LLM referenced unknown criterion: {grade.get('criterion_description', '')}")
                # Don't fail - continue with LLM's values
                continue
            
            # Get valid rule descriptions
            reduction_rules = criterion.get("reduction_rules", [])
            valid_rule_descriptions = {r.get("description", "") for r in reduction_rules}
            
            # Validate applied deductions
            validated_deductions = []
            ai_suggestions = grade.get("ai_suggested_deductions", [])
            
            for deduction in grade.get("applied_deductions", []):
                rule_desc = deduction.get("rule_description", "")
                
                if rule_desc in valid_rule_descriptions:
                    validated_deductions.append(deduction)
                else:
                    # Try fuzzy match
                    fuzzy_match = self._find_fuzzy_rule_match(rule_desc, reduction_rules)
                    if fuzzy_match:
                        deduction["rule_description"] = fuzzy_match.get("description", "")
                        deduction["reduction_value"] = fuzzy_match.get("reduction_value", 0)
                        validated_deductions.append(deduction)
                    else:
                        logger.warning(
                            f"Moving unknown rule to AI suggestions: {rule_desc}"
                        )
                        ai_suggestions.append({
                            "rule_description": rule_desc,
                            "suggested_reduction": deduction.get("reduction_value", 0),
                            "explanation": deduction.get("explanation", "")
                        })
            
            grade["applied_deductions"] = validated_deductions
            grade["ai_suggested_deductions"] = ai_suggestions
            
            # Recalculate points_earned from validated deductions
            total_points = criterion.get("total_points") or criterion.get("points", 0)
            total_deductions = sum(d.get("reduction_value", 0) for d in validated_deductions)
            calculated_points = total_points - total_deductions
            
            # Clamp to valid range
            grade["points_earned"] = max(0, min(calculated_points, total_points))
            grade["total_points"] = total_points
        
        # Calculate summary
        gradable_grades = [g for g in grades if not g.get("unable_to_grade")]
        total_score = sum(g.get("points_earned", 0) or 0 for g in gradable_grades)
        total_possible = sum(g.get("total_points", 0) for g in gradable_grades)
        
        response["summary"] = {
            "total_score": total_score,
            "total_possible": total_possible,
            "percentage": (total_score / total_possible * 100) if total_possible > 0 else 0,
            "has_ai_suggestions": any(len(g.get("ai_suggested_deductions", [])) > 0 for g in grades),
            "criteria_unable_to_grade": sum(1 for g in grades if g.get("unable_to_grade"))
        }
        
        # For backward compatibility, also include these at top level
        response["total_score"] = total_score
        response["total_possible"] = total_possible
        response["percentage"] = response["summary"]["percentage"]
        
        return response
    
    def _find_criterion_in_rubric(
        self,
        rubric: Dict,
        question_number: int,
        sub_question_id: Optional[str],
        criterion_description: str
    ) -> Optional[Dict]:
        """Find a criterion in the rubric by matching question/sub-question and description."""
        for question in rubric.get("questions", []):
            if question.get("question_number") != question_number:
                continue
            
            # Check sub-questions if sub_question_id provided
            if sub_question_id:
                for sub_q in question.get("sub_questions", []):
                    if sub_q.get("sub_question_id") == sub_question_id:
                        for criterion in sub_q.get("criteria", []):
                            if self._criteria_match(criterion, criterion_description):
                                return criterion
            else:
                # Check direct criteria
                for criterion in question.get("criteria", []):
                    if self._criteria_match(criterion, criterion_description):
                        return criterion
        
        return None
    
    def _criteria_match(self, criterion: Dict, description: str) -> bool:
        """Check if criterion matches description (fuzzy)."""
        crit_desc = criterion.get("criterion_description") or criterion.get("description", "")
        # Exact match
        if crit_desc == description:
            return True
        # Fuzzy match (80% similar)
        ratio = SequenceMatcher(None, crit_desc, description).ratio()
        return ratio >= 0.8
    
    def _find_fuzzy_rule_match(
        self,
        description: str,
        rules: List[Dict],
        threshold: float = 0.8
    ) -> Optional[Dict]:
        """Find a rule that closely matches the description."""
        best_match = None
        best_score = 0
        
        for rule in rules:
            rule_desc = rule.get("description", "")
            score = SequenceMatcher(None, description, rule_desc).ratio()
            if score > best_score and score >= threshold:
                best_match = rule
                best_score = score
        
        return best_match
