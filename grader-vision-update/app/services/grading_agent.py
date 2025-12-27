"""
LangGraph-based grading agent.
VISION-COMPATIBLE VERSION: Works with transcribed code from Vision AI.
"""
import json
import logging
from typing import Dict, List, TypedDict, Literal, Any
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
            max_tokens=8192, 
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
        
        final_state = self.workflow.invoke(
            initial_state,
            config={
                "tags": ["grading-workflow", f"model-{self.llm.model_name}"],
                "metadata": {
                    "teacher_email": teacher_email,
                    "original_message_id": original_message_id,
                    "test_count": len(student_tests),
                }
            }
        )
        
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
        rubric = state["rubric"]
        
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
            
            system_prompt = self._build_system_prompt(rubric)
            user_prompt = self._build_user_prompt(rubric, student_test)
            
            logger.info(f"System prompt length: {len(system_prompt)} chars")
            logger.info(f"User prompt length: {len(user_prompt)} chars")

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = self.llm.invoke(messages)
            
            logger.info(f"GPT-4 response length: {len(response.content)} chars")
            
            # Parse and post-process to fill any missing data
            grading_result = self._parse_grading_response(response.content, student_test, rubric)
            
            logger.info(f"Total score: {grading_result.get('total_score')}/{grading_result.get('total_possible')}")
            logger.info(f"Percentage: {grading_result.get('percentage'):.1f}%")
            logger.info(f"Number of question grades: {len(grading_result.get('question_grades', []))}")
            
            # Flatten grades for backward compatibility
            all_grades = []
            for qg in grading_result.get('question_grades', []):
                all_grades.extend(qg.get('grades', []))
            logger.info(f"Total criteria graded: {len(all_grades)}")
            
            # Collect low confidence notes
            if grading_result.get("low_confidence_items"):
                for item in grading_result["low_confidence_items"]:
                    note = f"Test: {student_test['student_name']}, {item}"
                    new_low_confidence.append(note)
                    logger.warning(f"⚠️ Low confidence: {note}")
            
            # Check for low confidence in individual grades
            for qg in grading_result.get('question_grades', []):
                for grade in qg.get('grades', []):
                    if grade.get('confidence') in ['low', 'medium']:
                        reason = grade.get('low_confidence_reason', grade.get('explanation', ''))
                        note = f"Test: {student_test['student_name']}, Q{qg.get('question_number')}: {grade.get('criterion', '')[:40]}... - {reason}"
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
                "question_grades": [],
                "grades": [],  # Flat list for backward compatibility
                "low_confidence_items": [f"Error: {str(e)}"]
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
    
    def _build_system_prompt(self, rubric: Dict) -> str:
        """Build system prompt for GPT-4 with explicit structure requirements."""
        
        # Build the expected structure based on actual rubric
        questions = rubric.get('questions', [])
        structure_example = {
            "question_grades": []
        }
        
        for q in questions[:1]:  # Just show structure for first question as example
            q_example = {
                "question_number": q['question_number'],
                "grades": []
            }
            for i, c in enumerate(q.get('criteria', [])[:2]):  # Show first 2 criteria
                q_example["grades"].append({
                    "criterion_index": i,
                    "criterion": c['description'][:50] + "...",
                    "mark": "✓",
                    "points_earned": c['points'],
                    "points_possible": c['points'],
                    "explanation": "הסבר קצר בעברית",
                    "confidence": "high"
                })
            structure_example["question_grades"].append(q_example)
        
        return f"""You are an expert Computer Science and C# teacher grading high school student programming tests.

CONTEXT:
- The student's code has been TRANSCRIBED from a scanned PDF using AI
- There may be minor transcription errors (typos, formatting issues)
- Be slightly lenient for transcription artifacts but strict on logic errors

GRADING RULES:
1. Grade STRICTLY according to the rubric - every single criterion must be graded
2. Use these marks:
   - ✓ (correct): Full points
   - ✗ (incorrect): Zero points  
   - ✓✗ (partial): Partial points (specify exactly how many)
3. Provide a brief explanation in Hebrew for each criterion (NEVER leave empty)
4. Assign confidence level: high, medium, or low
5. If confidence is low or medium, explain why in low_confidence_reason

CRITICAL REQUIREMENTS:
- You MUST grade EVERY criterion listed in the rubric
- You MUST copy the EXACT criterion text from the rubric (do not abbreviate or leave empty)
- You MUST provide an explanation for EVERY grade (never use empty string or newline)
- NEVER output "\\n" or empty strings for any field
- Output MUST be grouped by question_number

OUTPUT FORMAT - Return ONLY valid JSON matching this EXACT structure:
{{
  "question_grades": [
    {{
      "question_number": 1,
      "grades": [
        {{
          "criterion_index": 0,
          "criterion": "EXACT criterion text from rubric - NEVER empty",
          "mark": "✓" | "✗" | "✓✗",
          "points_earned": number,
          "points_possible": number,
          "explanation": "הסבר בעברית - NEVER empty",
          "confidence": "high" | "medium" | "low",
          "low_confidence_reason": "reason if not high (optional)"
        }}
      ]
    }}
  ],
  "low_confidence_items": ["Question X: reason for needing manual review"]
}}

EXAMPLE STRUCTURE (based on this rubric):
{json.dumps(structure_example, ensure_ascii=False, indent=2)}

Remember: Grade ALL {sum(len(q.get('criteria', [])) for q in questions)} criteria across {len(questions)} questions. No empty fields allowed."""

    def _build_user_prompt(self, rubric: Dict, student_test: Dict) -> str:
        """Construct user prompt with rubric and student answers."""
        prompt = "=== RUBRIC (Grade EVERY criterion below) ===\n\n"
        
        for q in rubric.get('questions', []):
            prompt += f"Question {q['question_number']} (Total: {q['total_points']} points)\n"
            prompt += f"Criteria to grade ({len(q['criteria'])} items):\n"
            for i, c in enumerate(q['criteria']):
                prompt += f"  [{i}] {c['description']} ({c['points']} points)\n"
            prompt += "\n"
            
        prompt += "=" * 50 + "\n"
        prompt += "=== STUDENT ANSWERS (Transcribed from PDF) ===\n\n"
        answers = student_test.get('answers', [])
        
        if not answers:
            prompt += "⚠️ NO ANSWERS TRANSCRIBED - Student may not have submitted code.\n"
            prompt += "Grade all criteria as ✗ (incorrect) with 0 points.\n"
        else:
            # Group answers by question number for clarity
            answers_by_q = {}
            for ans in answers:
                q_num = ans.get('question_number', 0)
                if q_num not in answers_by_q:
                    answers_by_q[q_num] = []
                answers_by_q[q_num].append(ans)
            
            for q_num in sorted(answers_by_q.keys()):
                for ans in answers_by_q[q_num]:
                    answer_text = ans.get('answer_text', '').strip()
                    sub_q = ans.get('sub_question_id', '')
                    q_label = f"Question {q_num}" + (f" ({sub_q})" if sub_q else "")
                    prompt += f"{q_label}:\n"
                    if answer_text:
                        prompt += f"```csharp\n{answer_text}\n```\n\n"
                    else:
                        prompt += "⚠️ [EMPTY - No code transcribed]\n\n"
        
        prompt += "=" * 50 + "\n"
        prompt += """INSTRUCTIONS:
1. Grade EVERY criterion from the rubric above
2. Copy the EXACT criterion text (never abbreviate)
3. Provide Hebrew explanation for each (never empty)
4. Group results by question_number
5. Output valid JSON only - no markdown, no extra text"""
            
        return prompt

    def _parse_grading_response(self, response_text: str, student_test: Dict, rubric: Dict) -> Dict:
        """Parse JSON response and fill in any missing data from rubric."""
        try:
            # Clean markdown wrappers
            cleaned = response_text.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                cleaned = "\n".join(lines[1:-1]) if len(lines) > 2 else cleaned
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:].strip()
            
            data = json.loads(cleaned)
            
            # Build rubric lookup for filling missing data
            rubric_lookup = self._build_rubric_lookup(rubric)
            
            # Process question_grades and fill missing data
            question_grades = data.get("question_grades", [])
            flat_grades = []  # For backward compatibility
            total_score = 0
            total_possible = 0
            
            for qg in question_grades:
                q_num = qg.get("question_number")
                processed_grades = []
                
                for grade in qg.get("grades", []):
                    # Fill missing criterion text from rubric
                    processed_grade = self._process_grade(grade, q_num, rubric_lookup)
                    processed_grades.append(processed_grade)
                    
                    # Add question info for flat list
                    flat_grade = {**processed_grade, "question_number": q_num}
                    flat_grades.append(flat_grade)
                    
                    total_score += processed_grade.get("points_earned", 0)
                    total_possible += processed_grade.get("points_possible", 0)
                
                qg["grades"] = processed_grades
            
            # Check for missing criteria and add them
            question_grades = self._ensure_all_criteria_graded(question_grades, rubric, flat_grades)
            
            # Recalculate totals after ensuring all criteria
            total_score = sum(g.get("points_earned", 0) for g in flat_grades)
            total_possible = sum(g.get("points_possible", 0) for g in flat_grades)
            percentage = (total_score / total_possible * 100) if total_possible > 0 else 0
            
            return {
                "student_name": student_test.get("student_name", "Unknown"),
                "filename": student_test.get("filename", "Unknown"),
                "total_score": total_score,
                "total_possible": total_possible,
                "percentage": percentage,
                "question_grades": question_grades,
                "grades": flat_grades,  # Flat list for backward compatibility
                "low_confidence_items": data.get("low_confidence_items", [])
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON Parsing failed: {e}")
            logger.error(f"Raw response: {response_text[:500]}...")
            raise
    
    def _build_rubric_lookup(self, rubric: Dict) -> Dict[str, Dict]:
        """Build a lookup dictionary for rubric criteria."""
        lookup = {}
        for q in rubric.get('questions', []):
            q_num = q['question_number']
            lookup[q_num] = {
                'total_points': q['total_points'],
                'criteria': {}
            }
            for i, c in enumerate(q.get('criteria', [])):
                lookup[q_num]['criteria'][i] = {
                    'description': c['description'],
                    'points': c['points']
                }
        return lookup
    
    def _process_grade(self, grade: Dict, question_number: int, rubric_lookup: Dict) -> Dict:
        """Process a single grade, filling missing data from rubric."""
        processed = {**grade}
        
        criterion_idx = grade.get('criterion_index')
        criterion_text = grade.get('criterion', '').strip()
        explanation = grade.get('explanation', '').strip()
        mark = grade.get('mark', '').strip()
        
        # Fix empty or newline-only values
        if not criterion_text or criterion_text == '\n':
            # Try to get from rubric using index
            if criterion_idx is not None and question_number in rubric_lookup:
                q_criteria = rubric_lookup[question_number].get('criteria', {})
                if criterion_idx in q_criteria:
                    processed['criterion'] = q_criteria[criterion_idx]['description']
                    logger.warning(f"Filled missing criterion text for Q{question_number}[{criterion_idx}]")
                else:
                    processed['criterion'] = f"קריטריון {criterion_idx + 1}"
            else:
                processed['criterion'] = f"קריטריון לא מזוהה"
        
        if not explanation or explanation == '\n':
            # Generate placeholder explanation based on score
            points_earned = grade.get('points_earned', 0)
            points_possible = grade.get('points_possible', 0)
            if points_earned == points_possible:
                processed['explanation'] = "נכון"
            elif points_earned == 0:
                processed['explanation'] = "לא נכון / חסר"
            else:
                processed['explanation'] = f"נכון חלקית ({points_earned}/{points_possible})"
            logger.warning(f"Filled missing explanation for Q{question_number}")
        
        if not mark or mark == '\n':
            # Infer mark from points
            points_earned = grade.get('points_earned', 0)
            points_possible = grade.get('points_possible', 0)
            if points_earned == points_possible:
                processed['mark'] = '✓'
            elif points_earned == 0:
                processed['mark'] = '✗'
            else:
                processed['mark'] = '✓✗'
            logger.warning(f"Filled missing mark for Q{question_number}")
        
        return processed
    
    def _ensure_all_criteria_graded(
        self, 
        question_grades: List[Dict], 
        rubric: Dict,
        flat_grades: List[Dict]
    ) -> List[Dict]:
        """Ensure all rubric criteria have been graded, add missing ones."""
        
        # Build set of graded criteria
        graded_set = set()
        for qg in question_grades:
            q_num = qg.get("question_number")
            for grade in qg.get("grades", []):
                criterion_idx = grade.get("criterion_index")
                if criterion_idx is not None:
                    graded_set.add((q_num, criterion_idx))
        
        # Check for missing criteria
        for q in rubric.get('questions', []):
            q_num = q['question_number']
            
            # Find or create question_grade entry
            qg_entry = None
            for qg in question_grades:
                if qg.get("question_number") == q_num:
                    qg_entry = qg
                    break
            
            if qg_entry is None:
                qg_entry = {"question_number": q_num, "grades": []}
                question_grades.append(qg_entry)
            
            for i, c in enumerate(q.get('criteria', [])):
                if (q_num, i) not in graded_set:
                    # Add missing criterion with 0 points and low confidence
                    missing_grade = {
                        "criterion_index": i,
                        "criterion": c['description'],
                        "mark": "✗",
                        "points_earned": 0,
                        "points_possible": c['points'],
                        "explanation": "לא נבדק על ידי המערכת",
                        "confidence": "low",
                        "low_confidence_reason": "הקריטריון לא נבדק - נדרשת בדיקה ידנית"
                    }
                    qg_entry["grades"].append(missing_grade)
                    
                    # Also add to flat list
                    flat_grades.append({**missing_grade, "question_number": q_num})
                    
                    logger.warning(f"Added missing criterion: Q{q_num}[{i}] - {c['description'][:50]}...")
        
        # Sort question_grades by question number
        question_grades.sort(key=lambda x: x.get("question_number", 0))
        
        # Sort grades within each question by criterion_index
        for qg in question_grades:
            qg["grades"].sort(key=lambda x: x.get("criterion_index", 0))
        
        return question_grades