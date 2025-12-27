"""
LangGraph-based grading agent.
VISION-COMPATIBLE VERSION: Works with transcribed code from Vision AI.
"""
import json
import logging
from typing import Dict, List, TypedDict, Literal
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END

from ..config import settings

logger = logging.getLogger(__name__)


class GradingState(TypedDict):
    """State for the grading workflow."""
    rubric: Dict
    student_tests: List[Dict]
    current_test_index: int
    graded_results: List[Dict]
    low_confidence_notes: List[str]
    teacher_email: str
    original_message_id: str


class GradingAgent:
    """Agent that grades student tests using GPT-4 and rubric criteria."""
    
    def __init__(self):
        """Initialize the grading agent with JSON mode enabled."""
        
        model_name = settings.openai_model if settings.openai_model else "gpt-4-turbo-preview"
        
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
        logger.info("STARTING GRADING WORKFLOW")
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
        logger.info("INITIALIZING GRADING WORKFLOW")
        logger.info("=" * 80)
        logger.info(f"Rubric: {len(state['rubric'].get('questions', []))} questions")
        logger.info(f"Student tests to grade: {len(state['student_tests'])}")
        
        for q in state['rubric'].get('questions', []):
            logger.info(f"\nQuestion {q['question_number']}:")
            logger.info(f"  - Total points: {q['total_points']}")
            logger.info(f"  - Number of criteria: {len(q['criteria'])}")
        
        logger.info("\nInitialization complete. Starting grading loop...")
        return {}
    
    def _grade_single_test(self, state: GradingState) -> Dict:
        """Grade a single student test."""
        current_idx = state["current_test_index"]
        student_test = state["student_tests"][current_idx]
        
        logger.info("=" * 80)
        logger.info(f"GRADING TEST {current_idx + 1}/{len(state['student_tests'])}")
        logger.info("=" * 80)
        logger.info(f"Student: {student_test.get('student_name')}")
        logger.info(f"Filename: {student_test.get('filename')}")
        
        answers = student_test.get('answers', [])
        logger.info(f"Transcribed answers: {len(answers)}")
        
        for ans in answers:
            preview = ans.get('answer_text', '')[:100].replace('\n', ' ')
            logger.info(f"  Answer Q{ans.get('question_number', '?')}: {preview}...")
        
        grading_result = None
        new_low_confidence = []
        
        try:
            logger.info("\nSENDING TO GPT-4 FOR GRADING...")
            
            system_prompt = self._build_system_prompt()
            user_prompt = self._build_user_prompt(state["rubric"], student_test)
            
            logger.info(f"System prompt length: {len(system_prompt)} chars")
            logger.info(f"User prompt length: {len(user_prompt)} chars")

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = self.llm.invoke(messages)
            
            logger.info(f"GPT-4 response length: {len(response.content)} chars")
            
            grading_result = self._parse_grading_response(response.content, student_test)
            
            logger.info(f"Total score: {grading_result.get('total_score')}/{grading_result.get('total_possible')}")
            logger.info(f"Percentage: {grading_result.get('percentage'):.1f}%")
            logger.info(f"Number of grades: {len(grading_result.get('grades', []))}")
            
            # Collect low confidence notes
            if grading_result.get("low_confidence_items"):
                for item in grading_result["low_confidence_items"]:
                    note = f"Test: {student_test['student_name']}, {item}"
                    new_low_confidence.append(note)
                    logger.warning(f"⚠️ Low confidence: {note}")
            
            for grade in grading_result.get('grades', []):
                if grade.get('confidence') in ['low', 'medium']:
                    reason = grade.get('low_confidence_reason', grade.get('explanation', ''))
                    note = f"Test: {student_test['student_name']}, {grade.get('criterion', '')[:40]}... - {reason}"
                    if note not in new_low_confidence:
                        new_low_confidence.append(note)
            
            logger.info(f"✅ Grading complete for {student_test['student_name']}")

        except Exception as e:
            logger.error(f"Error grading test: {e}", exc_info=True)
            grading_result = {
                "student_name": student_test.get("student_name", "Unknown"),
                "filename": student_test.get("filename", "Unknown"),
                "total_score": 0,
                "total_possible": 0,
                "percentage": 0,
                "error": str(e),
                "grades": []
            }
            new_low_confidence.append(f"Test: {student_test.get('student_name')}, Error: {str(e)}")
        
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
            valid_results = [r for r in results if r.get('total_possible', 0) > 0]
            if valid_results:
                scores = [r.get('percentage', 0) for r in valid_results]
                logger.info(f"\nScore summary:")
                logger.info(f"  - Average: {sum(scores) / len(scores):.1f}%")
                logger.info(f"  - Min: {min(scores):.1f}%")
                logger.info(f"  - Max: {max(scores):.1f}%")
        
        return {}
    
    def _build_system_prompt(self) -> str:
        """Build system prompt for GPT-4."""
        return """You are an expert Computer Science and C# teacher grading highschool students programming tests.

CONTEXT:
- The student's code has been TRANSCRIBED from a scanned PDF using AI
- There may be minor transcription errors (typos, formatting issues)
- Be slightly lenient for transcription artifacts but strict on logic errors

GRADING RULES:
1. Grade strictly according to the rubric provided
2. Use these marks:
   - ✓ (correct): Full points
   - ✗ (incorrect): Zero points
   - ✓✗ (partial): Partial points (specify how many)
3. Provide a brief explanation in Hebrew for each criterion (one line)
4. Assign confidence level: high, medium, or low
5. If confidence is low or medium, explain why

IMPORTANT:
- Grade EVERY criterion in the rubric
- If code is missing or empty, mark as ✗ with 0 points
- Be thorough but fair
- Consider minor typos as transcription artifacts if the logic is correct

OUTPUT FORMAT:
Respond ONLY with valid JSON (no markdown, no extra text):
{
  "grades": [
    {
      "criterion": "exact text from rubric",
      "mark": "✓" | "✗" | "✓✗",
      "points_earned": number,
      "points_possible": number,
      "explanation": "Brief Hebrew explanation",
      "confidence": "high" | "medium" | "low",
      "low_confidence_reason": "reason if confidence is not high (optional)"
    }
  ],
  "low_confidence_items": ["Question X: reason for needing manual review"]
}
"""

    def _build_user_prompt(self, rubric: Dict, student_test: Dict) -> str:
        """Construct user prompt with rubric and student answers."""
        prompt = "RUBRIC:\n\n"
        
        for q in rubric.get('questions', []):
            prompt += f"Question {q['question_number']} (Total: {q['total_points']} points)\n"
            for c in q['criteria']:
                prompt += f"  - {c['description']} ({c['points']} points)\n"
            prompt += "\n"
            
        prompt += "=" * 40 + "\n"
        prompt += "STUDENT ANSWERS (Transcribed from PDF):\n\n"
        answers = student_test.get('answers', [])
        
        if not answers:
            prompt += "⚠️ NO ANSWERS TRANSCRIBED - Student may not have submitted code.\n"
            prompt += "Grade all criteria as ✗ (incorrect) with 0 points.\n"
        else:
            for ans in answers:
                answer_text = ans.get('answer_text', '').strip()
                q_num = ans.get('question_number', '?')
                prompt += f"Question {q_num}:\n"
                if answer_text:
                    prompt += f"```csharp\n{answer_text}\n```\n\n"
                else:
                    prompt += "⚠️ [EMPTY - No code transcribed for this question]\n\n"
        
        prompt += "=" * 40 + "\n"
        prompt += "Please grade each criterion from the rubric. Output valid JSON only."
            
        return prompt

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
            
            # Calculate totals
            grades = data.get("grades", [])
            total_score = sum(g.get("points_earned", 0) for g in grades)
            total_possible = sum(g.get("points_possible", 0) for g in grades)
            percentage = (total_score / total_possible * 100) if total_possible > 0 else 0
            
            return {
                "student_name": student_test.get("student_name", "Unknown"),
                "filename": student_test.get("filename", "Unknown"),
                "total_score": total_score,
                "total_possible": total_possible,
                "percentage": percentage,
                "grades": grades,
                "low_confidence_items": data.get("low_confidence_items", [])
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON Parsing failed: {e}")
            logger.error(f"Raw response: {response_text[:500]}...")
            raise
