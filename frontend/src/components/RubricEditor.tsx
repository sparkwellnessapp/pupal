'use client';

import { useCallback, useEffect, useMemo, useRef, useState, type RefObject } from 'react';
import type {
  RubricQuestion,
  RubricSubQuestion,
  RubricCriterion,
  RubricSubCriterion,
  ContextTableData,
  ProposalSet,
  ProposedCriterion,
} from '@/types/rubric';
import { parseQuestionNumber, recalculateParentsFromCriteria } from '@/utils/rubric-transform';
import { defaultSubQuestionTitle } from '@/utils/rubric-display';
import { validateAllQuestions, getQuestionErrorCount } from '@/utils/rubric-validation';
import { scopeLabel } from '@/utils/scope-label';
import { errorsBadgeLabel } from '@/utils/session-spine';
import {
  addQuestion,
  removeQuestion,
  changeQuestionPoints,
  addSubQuestion,
  removeSubQuestion,
  setExampleSolution,
  setQuestionType,
  // B-11: path-addressed ops for editing nested sub-questions at any depth.
  setSubQuestionTitleAtPath,
  changeSubQuestionPointsAtPath,
  setSubQuestionTextAtPath,
  updateCriterionAtPath,
  addCriterionAtPath,
  removeCriterionAtPath,
  reorderCriteriaAtPath,
} from '@/utils/rubric-editor-ops';
import { RubricMetadataEditor } from '@/components/RubricMetadataEditor';
import { ExampleSolutionEditor } from '@/components/ExampleSolutionEditor';
import { MarkdownTextRenderer } from '@/components/MarkdownTextRenderer';
import { AnnotationBanner } from '@/components/AnnotationBanner';
import { PagePreview, QuestionPageMapping, ExtractionMetadata, TraceTableData, Annotation } from '@/lib/api';
import { Plus, Trash2, ChevronDown, ChevronUp, GripVertical, AlertCircle, AlertTriangle, FileText, ChevronLeft, ChevronRight, Maximize2, X, Info, Code, Table, Lightbulb, CheckCircle2, Sparkles, Loader2 } from 'lucide-react';

interface RubricEditorProps {
  questions: RubricQuestion[];
  onQuestionsChange: (questions: RubricQuestion[]) => void;
  // PDF pages and mappings for inline display
  pages?: PagePreview[];
  questionMappings?: QuestionPageMapping[];
  // NEW: DOCX extraction metadata
  metadata?: ExtractionMetadata;
  // NEW: Source type indicator
  sourceType?: 'pdf' | 'docx';
  // NEW: Programming language for display
  programmingLanguage?: string;
  // Rubric ID for post-acceptance enhancement API calls
  rubricId?: string;
  // Metadata fields — editable at rubric level
  rubricName?: string;
  subject?: string;
  rubricTotalPoints?: number;
  /** Called when metadata fields (name, subject, programmingLanguage) change */
  onMetadataChange?: (patch: { rubric_name?: string; subject?: string; programming_language?: string }) => void;
  /** Called when total_points changes at rubric level (triggers full cascade) */
  onTotalPointsChange?: (newTotal: number) => void;
  /** Highlights the name field with an error border */
  hasNameError?: boolean;
  /** Extraction-time annotations to render inline (rubric_mismatch warnings, etc.). */
  annotations?: Annotation[];
  /** Ref exposed to parent so the parent's blocked save button can scroll to the error banner. */
  errorBannerRef?: RefObject<HTMLDivElement>;
}

export function RubricEditor({
  questions,
  onQuestionsChange,
  pages,
  questionMappings,
  metadata,
  sourceType,
  programmingLanguage,
  rubricId,
  rubricName = '',
  subject = '',
  rubricTotalPoints,
  onMetadataChange,
  onTotalPointsChange,
  hasNameError = false,
  annotations = [],
  errorBannerRef: externalErrorBannerRef,
}: RubricEditorProps) {
  const [expandedQuestions, setExpandedQuestions] = useState<Set<number>>(
    new Set(questions.map((_, i) => i))
  );

  // Save-blocking UX
  const internalErrorBannerRef = useRef<HTMLDivElement>(null);
  const errorBannerRef = externalErrorBannerRef || internalErrorBannerRef;
  const errorAnnotations = useMemo(
    () => annotations.filter(a => a.severity === 'error'),
    [annotations]
  );
  const hasBlockingErrors = errorAnnotations.length > 0;

  const scrollToScope = useCallback((targetId: string | null) => {
    const selector = targetId ? `[data-scope-id="${targetId}"]` : null;
    const el = selector ? document.querySelector(selector) : null;
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, []);

  // Track criteria currently being enhanced (post-acceptance Call 2)
  const [enhancingCriterionIds, setEnhancingCriterionIds] = useState<Set<string>>(new Set());

  const toggleExpanded = (index: number) => {
    const newExpanded = new Set(expandedQuestions);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedQuestions(newExpanded);
  };

  // Live validation: recomputes whenever questions change
  // Note: relies on immutable updates (new array references) from all update functions
  const validationIssues = useMemo(
    () => validateAllQuestions(questions),
    [questions]
  );

  const updateQuestion = (index: number, updates: Partial<RubricQuestion>) => {
    const newQuestions = [...questions];
    newQuestions[index] = { ...newQuestions[index], ...updates };
    // No cascade — non-criterion updates never move points.
    onQuestionsChange(newQuestions);
  };

  const updateCriterion = (
    qIndex: number,
    cIndex: number,
    updates: Partial<RubricCriterion>,
    sqIndex?: number
  ) => {
    const newQuestions = [...questions];
    if (sqIndex !== undefined) {
      newQuestions[qIndex].sub_questions[sqIndex].criteria[cIndex] = {
        ...newQuestions[qIndex].sub_questions[sqIndex].criteria[cIndex],
        ...updates,
      };
    } else {
      newQuestions[qIndex].criteria[cIndex] = {
        ...newQuestions[qIndex].criteria[cIndex],
        ...updates,
      };
    }
    // THE ONE CASCADE SITE: a criterion.points edit propagates one level up
    // to its direct structural parent. See recalculateParentsFromCriteria
    // in rubric-transform.ts.
    onQuestionsChange(recalculateParentsFromCriteria(newQuestions));
  };

  const addCriterion = (qIndex: number, sqIndex?: number) => {
    const newQuestions = [...questions];
    const newCriterion: RubricCriterion = {
      criterion_id: `c${Date.now()}`,
      index: sqIndex !== undefined
        ? newQuestions[qIndex].sub_questions[sqIndex].criteria.length
        : newQuestions[qIndex].criteria.length,
      description: '',
      points: 0,
      sub_criteria: null,
      extraction_confidence: 'high',
      notes: null,
    };
    if (sqIndex !== undefined) {
      newQuestions[qIndex].sub_questions[sqIndex].criteria.push(newCriterion);
    } else {
      newQuestions[qIndex].criteria.push(newCriterion);
    }
    onQuestionsChange(newQuestions);
  };

  const removeCriterion = (qIndex: number, cIndex: number, sqIndex?: number) => {
    // Strict per Q1: removing a criterion leaves a hole. No redistribution
    // among surviving criteria. INV-R1 / INV-R1b will fire on the resulting
    // mismatch (Σ criteria.points < parent.points); the teacher resolves it
    // by editing the parent down or another criterion up.
    //
    // The surviving criteria are reindexed so the `.index` field stays
    // contiguous (positional metadata, not point math).
    const newQuestions = [...questions];
    const sourceArray = sqIndex !== undefined
      ? newQuestions[qIndex].sub_questions[sqIndex].criteria
      : newQuestions[qIndex].criteria;

    const reindexed = sourceArray
      .filter((_, i) => i !== cIndex)
      .map((c, i) => ({ ...c, index: i }));

    if (sqIndex !== undefined) {
      newQuestions[qIndex].sub_questions[sqIndex].criteria = reindexed;
    } else {
      newQuestions[qIndex].criteria = reindexed;
    }

    // No cascade — Q1 strict.
    onQuestionsChange(newQuestions);
  };

  const reorderCriteria = (
    qIndex: number,
    fromIndex: number,
    toIndex: number,
    sqIndex?: number
  ) => {
    const newQuestions = [...questions];
    let criteriaArray: RubricCriterion[];

    if (sqIndex !== undefined) {
      criteriaArray = [...newQuestions[qIndex].sub_questions[sqIndex].criteria];
    } else {
      criteriaArray = [...newQuestions[qIndex].criteria];
    }

    const [movedItem] = criteriaArray.splice(fromIndex, 1);
    criteriaArray.splice(toIndex, 0, movedItem);

    if (sqIndex !== undefined) {
      newQuestions[qIndex].sub_questions[sqIndex].criteria = criteriaArray;
    } else {
      newQuestions[qIndex].criteria = criteriaArray;
    }

    onQuestionsChange(newQuestions);
  };

  // ─── Proposal Accept / Reject ─────────────────────────────────────────────

  /**
   * Accept all proposed criteria for a scope (question or sub-question).
   * 1. Apply enhanced_distribution points to existing criteria
   * 2. Convert proposed criteria to normal RubricCriterion (empty rules[])
   * 3. Clear proposals from state
   * 4. Trigger post-acceptance Call 2 for new criteria
   */
  const acceptProposals = (qIndex: number, sqIndex?: number) => {
    const newQuestions = [...questions];

    const scope = sqIndex !== undefined
      ? newQuestions[qIndex].sub_questions[sqIndex]
      : newQuestions[qIndex];

    const proposals = scope.proposals;
    if (!proposals || proposals.proposed_criteria.length === 0) return;

    // Capture question_purpose BEFORE clearing proposals (needed for Call 2)
    const questionPurpose = proposals.question_purpose || '';

    // Step 1: Apply enhanced_distribution points to existing criteria.
    //   Also proportionally scale each criterion's sub_criteria so that
    //   sum(sub_criteria.points) continues to equal the (new) criterion points.
    if (proposals.enhanced_distribution.length > 0) {
      const distMap = new Map(
        proposals.enhanced_distribution.map(entry => [entry.criterion_id, entry.points])
      );
      const r2 = (n: number) => Math.round(n * 100) / 100;

      scope.criteria = scope.criteria.map(c => {
        const newPts = distMap.get(c.criterion_id);
        if (newPts === undefined) return c;

        // Scale sub_criteria proportionally if present
        const oldPts = c.points;
        if (!c.sub_criteria?.length || oldPts === 0) {
          return { ...c, points: newPts };
        }

        const ratio = newPts / oldPts;
        let running = 0;
        const scaledSubCriteria = c.sub_criteria.map((sc, scIdx) => {
          let scaledPts: number;
          if (scIdx === c.sub_criteria!.length - 1) {
            scaledPts = r2(newPts - running);
          } else {
            scaledPts = r2(sc.points * ratio);
            running += scaledPts;
          }
          return { ...sc, points: scaledPts };
        });

        return { ...c, points: newPts, sub_criteria: scaledSubCriteria };
      });
    }

    // Step 2: Convert proposed criteria to normal RubricCriterion
    const newCriteria: RubricCriterion[] = proposals.proposed_criteria.map(
      (pc, idx) => ({
        criterion_id: pc.temp_id || `c_proposed_${Date.now()}_${idx}`,
        index: scope.criteria.length + idx,
        description: pc.description,
        points: pc.points,
        sub_criteria: null,
        extraction_confidence: 'high' as const,
        notes: null,
      })
    );

    // Step 3: Append and clear proposals
    scope.criteria = [...scope.criteria, ...newCriteria];
    scope.proposals = null;

    // No cascade — proposals are legacy (V3 pipeline doesn't generate them);
    // this entire code path is slated for full removal in a separate PR.
    onQuestionsChange(newQuestions);

    // Step 4: Trigger post-acceptance Call 2 (async, does not block UI)
    _triggerPostAcceptanceEnhancement(newCriteria, questionPurpose, qIndex, sqIndex);
  };

  /**
   * Reject all proposed criteria for a scope. Clears proposals, keeps original points.
   */
  const rejectProposals = (qIndex: number, sqIndex?: number) => {
    const newQuestions = [...questions];

    if (sqIndex !== undefined) {
      newQuestions[qIndex].sub_questions[sqIndex] = {
        ...newQuestions[qIndex].sub_questions[sqIndex],
        proposals: null,
      };
    } else {
      newQuestions[qIndex] = {
        ...newQuestions[qIndex],
        proposals: null,
      };
    }

    onQuestionsChange(newQuestions);
  };

  /**
   * Trigger Call 2 (rules + levels) for newly accepted criteria.
   * Async: sets loading state, calls API, merges results.
   */
  const _triggerPostAcceptanceEnhancement = async (
    newCriteria: RubricCriterion[],
    questionPurpose: string,
    qIndex: number,
    sqIndex?: number,
  ) => {
    if (!rubricId || newCriteria.length === 0) {
      console.info('[Vivi] Post-acceptance enhancement skipped: no rubricId or empty criteria');
      return;
    }

    const criterionIds = newCriteria.map(c => c.criterion_id);

    // Set loading state
    setEnhancingCriterionIds(prev => {
      const next = new Set(prev);
      criterionIds.forEach(id => next.add(id));
      return next;
    });

    try {
      // Get optional context from the question
      const question = questions[qIndex];
      const subQuestion = sqIndex !== undefined ? question?.sub_questions?.[sqIndex] : undefined;

      const response = await fetch(`/api/v0/rubrics/${rubricId}/enhance-criteria`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          criteria: newCriteria.map(c => ({
            criterion_id: c.criterion_id,
            description: c.description,
            points: c.points,
          })),
          question_purpose: questionPurpose,
          sub_question_text: subQuestion?.text || null,
          example_solution: question?.example_solution || null,
          programming_language: programmingLanguage || null,
          locale: 'he-IL',
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('[Vivi] Enhancement API error:', response.status, errorText);
        return;
      }

      const data = await response.json();
      // DEAD UNTIL grader redesign — see grader-migration-TODO
      // Enhancement endpoint previously returned reduction_rules; now a no-op merge.
      console.info(
        `[Vivi] Post-acceptance enhancement complete: ${data.total_sub_criteria || 0} sub-criteria for ${criterionIds.length} criteria`
      );

    } catch (err) {
      console.error('[Vivi] Post-acceptance enhancement failed:', err);
    } finally {
      // Clear loading state
      setEnhancingCriterionIds(prev => {
        const next = new Set(prev);
        criterionIds.forEach(id => next.delete(id));
        return next;
      });
    }
  };


  // Get page indexes for a question's text
  // Inferred as: the page before the first rubric table page
  const getQuestionPageIndexes = (questionNumber: number): number[] => {
    if (!questionMappings) return [];
    const mapping = questionMappings.find(m => m.question_number === questionNumber);
    if (!mapping) return [];

    // Get all criterion page indexes (from direct criteria or sub-questions)
    let criteriaPages: number[] = [];
    if (mapping.criteria_page_indexes.length > 0) {
      criteriaPages = mapping.criteria_page_indexes;
    } else if (mapping.sub_questions.length > 0) {
      // Get earliest page from any sub-question
      const allSubQPages = mapping.sub_questions.flatMap(sq => sq.criteria_page_indexes);
      criteriaPages = allSubQPages;
    }

    if (criteriaPages.length === 0) return [];

    // Question page is the one before the first rubric table page
    const firstCriteriaPage = Math.min(...criteriaPages);
    const inferredQuestionPage = firstCriteriaPage - 1;

    // Return if valid page index (>= 0)
    return inferredQuestionPage >= 0 ? [inferredQuestionPage] : [];
  };

  // ─── Question / Sub-question CRUD handlers ────────────────────────────────

  const handleAddQuestion = () => {
    onQuestionsChange(addQuestion(questions));
  };

  const handleRemoveQuestion = (qIndex: number) => {
    // Strict per Q1: no redistribution. Σ q.total_points changes; INV-R3
    // fires against the unchanged rubricDeclaredTotal; teacher resolves.
    onQuestionsChange(removeQuestion(questions, qIndex));
  };

  const handleQuestionPointsChange = (qIndex: number, newPts: number) => {
    onQuestionsChange(changeQuestionPoints(questions, qIndex, newPts));
  };

  const handleRubricTotalChange = (newTotal: number) => {
    // The rubric-level total is owned by page.tsx state (rubricDeclaredTotal),
    // not by the questions[] array. We just forward the new value upstream;
    // INV-R3 in combinedAnnotations will fire if it no longer matches
    // Σ q.total_points.
    onTotalPointsChange?.(newTotal);
  };

  const handleAddSubQuestion = (qIndex: number) => {
    onQuestionsChange(addSubQuestion(questions, qIndex));
  };

  // ─── B-11: path-addressed handlers for nested sub-questions ────────────────
  // Each takes an `sqPath` (positional chain from the question). Editing a
  // criterion still routes through recalculateParentsFromCriteria — the ONE
  // silent cascade — which is now recursive, so a deep edit propagates up
  // through every nested parent.
  const handleSubQTitleAtPath = (qIndex: number, sqPath: number[], title: string | null) => {
    onQuestionsChange(setSubQuestionTitleAtPath(questions, qIndex, sqPath, title));
  };
  const handleSubQPointsAtPath = (qIndex: number, sqPath: number[], newPts: number) => {
    onQuestionsChange(changeSubQuestionPointsAtPath(questions, qIndex, sqPath, newPts));
  };
  const handleSubQTextAtPath = (qIndex: number, sqPath: number[], text: string) => {
    onQuestionsChange(setSubQuestionTextAtPath(questions, qIndex, sqPath, text));
  };
  const handleUpdateCriterionAtPath = (
    qIndex: number, sqPath: number[], cIndex: number, updates: Partial<RubricCriterion>,
  ) => {
    onQuestionsChange(
      recalculateParentsFromCriteria(updateCriterionAtPath(questions, qIndex, sqPath, cIndex, updates)),
    );
  };
  const handleAddCriterionAtPath = (qIndex: number, sqPath: number[]) => {
    onQuestionsChange(addCriterionAtPath(questions, qIndex, sqPath));
  };
  const handleRemoveCriterionAtPath = (qIndex: number, sqPath: number[], cIndex: number) => {
    onQuestionsChange(removeCriterionAtPath(questions, qIndex, sqPath, cIndex));
  };
  const handleReorderCriteriaAtPath = (qIndex: number, sqPath: number[], from: number, to: number) => {
    onQuestionsChange(reorderCriteriaAtPath(questions, qIndex, sqPath, from, to));
  };
  // Structural remove and proposals stay depth-1 (MVP defers nested-node CRUD;
  // proposals are ephemeral and only ever produced at the top-level scope).
  const handleRemoveSubQAtPath = (qIndex: number, sqPath: number[]) => {
    if (sqPath.length === 1) onQuestionsChange(removeSubQuestion(questions, qIndex, sqPath[0]));
  };
  const handleAcceptProposalsAtPath = (qIndex: number, sqPath: number[]) => {
    if (sqPath.length === 1) acceptProposals(qIndex, sqPath[0]);
  };
  const handleRejectProposalsAtPath = (qIndex: number, sqPath: number[]) => {
    if (sqPath.length === 1) rejectProposals(qIndex, sqPath[0]);
  };

  const handleExampleSolutionChange = (qIndex: number, val: string | null) => {
    onQuestionsChange(setExampleSolution(questions, qIndex, val));
  };

  const handleQuestionTypeChange = (qIndex: number, type: RubricQuestion['question_type']) => {
    onQuestionsChange(setQuestionType(questions, qIndex, type));
  };

  // Derived: rubric-level total points for the metadata editor display.
  // INV-R3 (Σ q.total_points vs. rubric.total_points) is enforced centrally
  // in page.tsx's combinedAnnotations and rendered through the unified
  // global-annotations path below — not locally here.
  const effectiveTotalPoints = rubricTotalPoints ?? questions.reduce((s, q) => s + q.total_points, 0);


  // Get page indexes for a question's criteria
  const getCriteriaPageIndexes = (questionNumber: number): number[] => {
    if (!questionMappings) return [];
    const mapping = questionMappings.find(m => m.question_number === questionNumber);
    return mapping?.criteria_page_indexes || [];
  };

  // Get page indexes for a sub-question's criteria
  const getSubQuestionCriteriaPageIndexes = (questionNumber: number, subQuestionId: string): number[] => {
    if (!questionMappings) return [];
    const mapping = questionMappings.find(m => m.question_number === questionNumber);
    const subQ = mapping?.sub_questions.find(sq => sq.sub_question_id === subQuestionId);
    return subQ?.criteria_page_indexes || [];
  };

  // Calculate statistics.
  // B-11: RECURSE the criteria-XOR-sub_questions tree at any depth. The depth-1
  // version undercounted nested rubrics (bagrut: it saw 6 of 18 criteria and
  // none of the depth-2 leaves) — the client twin of the backend
  // calculate_rubric_stats nesting-blindness the census flagged (E10).
  const stats = useMemo(() => {
    let totalCriteria = 0;
    let totalSubCriteria = 0;
    let highConfidence = 0;
    let mediumConfidence = 0;
    let lowConfidence = 0;

    const countCriterion = (c: RubricCriterion) => {
      totalCriteria++;
      totalSubCriteria += c.sub_criteria?.length || 0;
      const conf = c.extraction_confidence || 'medium';
      if (conf === 'high') highConfidence++;
      else if (conf === 'medium') mediumConfidence++;
      else lowConfidence++;
    };
    const walk = (node: { criteria?: RubricCriterion[]; sub_questions?: RubricSubQuestion[] }) => {
      (node.criteria || []).forEach(countCriterion);
      (node.sub_questions || []).forEach(walk);
    };
    questions.forEach(walk);

    return { totalCriteria, totalSubCriteria, highConfidence, mediumConfidence, lowConfidence };
  }, [questions]);
  const testTitleStr = typeof metadata?.test_title === 'string' ? metadata.test_title.trim() : '';
  const backendTestDateStr = typeof metadata?.test_date === 'string' ? metadata.test_date.trim() : '';
  const titleDateMatch = testTitleStr.match(/\b(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})\b/);
  const testDateStr = backendTestDateStr || titleDateMatch?.[1] || '';

  return (
    <div className="space-y-4">
      {/* Metadata editor — shown when onMetadataChange is provided */}
      {onMetadataChange && (
        <RubricMetadataEditor
          rubricName={rubricName}
          subject={subject}
          programmingLanguage={programmingLanguage ?? ''}
          totalPoints={effectiveTotalPoints}
          onChange={onMetadataChange}
          onTotalPointsChange={handleRubricTotalChange}
          hasNameError={hasNameError}
        />
      )}

      {/* Save-blocking error summary banner — shown when any ERROR annotations exist */}
      {hasBlockingErrors && (
        <div ref={errorBannerRef} className="bg-red-50 border border-red-300 rounded-lg p-3 text-sm text-red-800" dir="rtl">
          <div className="font-semibold flex items-center gap-2">
            <AlertCircle size={15} />
            לא ניתן לשמור: {errorsBadgeLabel(errorAnnotations.length)} חוסמות
          </div>
          <ul className="mt-2 space-y-1 list-disc list-inside">
            {errorAnnotations.map(a => (
              <li key={a.id}>
                {a.target_id ? (
                  <button
                    className="underline text-red-700 hover:text-red-900"
                    onClick={() => scrollToScope(a.target_id)}
                  >
                    {/* S1-9: the naming law — never the raw id (q1.א.2). */}
                    {scopeLabel(a.target_id, questions)}
                  </button>
                ) : (
                  <span>המחוון</span>
                )}
                {' — '}{a.message}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Global annotations.
          Two scopes: 'rubric' from live INV-R3, and null from legacy backend
          rubric-scope annotations. Both render as global banners above the
          summary header. */}
      {annotations.filter(a => a.target_id === null || a.target_id === 'rubric').map(a => (
        <AnnotationBanner key={a.id} annotation={a} />
      ))}

      {/* Summary header */}
      <div className="flex items-center justify-between p-4 bg-primary-50 border border-primary-200 rounded-lg">
        <div>
          <h3 className="font-semibold text-lg text-primary-800">סיכום מחוון</h3>
          <div className="text-sm text-primary-700 mt-1 space-y-0.5">
            {testTitleStr && (
              <div className="font-medium" dir={/[\u0590-\u05FF]/.test(testTitleStr) ? 'rtl' : 'ltr'}>
                {testTitleStr}
              </div>
            )}
            {testDateStr && (
              <div className="text-primary-600">
                תאריך: {testDateStr}
              </div>
            )}
            <div className="text-primary-600">
              {questions.length} שאלות · {effectiveTotalPoints} נקודות · {stats.totalCriteria} קריטריונים
            </div>
          </div>
        </div>

        {/* Confidence breakdown */}
        {stats.totalCriteria > 0 && (
          <div className="flex items-center gap-2">
            {stats.highConfidence > 0 && (
              <span className="px-2 py-1 bg-green-100 text-green-700 text-xs rounded-full">
                ✓ {stats.highConfidence} בטוחים
              </span>
            )}
            {stats.lowConfidence > 0 && (
              <span className="px-2 py-1 bg-red-100 text-red-700 text-xs rounded-full">
                ! {stats.lowConfidence} לבדיקה
              </span>
            )}
          </div>
        )}
      </div>

      {/* Questions */}
      <div className="space-y-3">
        {questions.map((question, qIndex) => (
          <div
            key={qIndex}
            data-scope-id={question.question_id}
            className="border border-surface-200 rounded-lg bg-white overflow-hidden shadow-sm"
          >
            {/* Question header */}
            <div
              className="flex items-center justify-between p-4 bg-surface-50"
              dir="rtl"
            >
              {/* Toggle chevron + title (clicking title area expands) */}
              <div
                className="flex items-center gap-3 flex-1 cursor-pointer min-w-0"
                onClick={() => toggleExpanded(qIndex)}
              >
                {expandedQuestions.has(qIndex) ? (
                  <ChevronUp size={20} className="text-gray-400 flex-shrink-0" />
                ) : (
                  <ChevronDown size={20} className="text-gray-400 flex-shrink-0" />
                )}
                <span className="font-semibold text-lg whitespace-nowrap">שאלה {parseQuestionNumber(question.question_id)}</span>
              </div>

              {/* Points input — click to stop propagation */}
              <div className="flex items-center gap-1.5 flex-shrink-0 mx-3" onClick={e => e.stopPropagation()}>
                <input
                  type="number"
                  defaultValue={question.total_points}
                  key={question.total_points}
                  onBlur={e => {
                    const val = parseFloat(e.target.value);
                    if (!isNaN(val) && val > 0) handleQuestionPointsChange(qIndex, val);
                    else e.target.value = String(question.total_points);
                  }}
                  min={0.25}
                  step={0.25}
                  className="w-16 text-center text-sm border border-surface-300 rounded-lg px-2 py-1 bg-white focus:outline-none focus:ring-2 focus:ring-primary-300 font-semibold"
                  title="נקודות השאלה"
                />
                <span className="text-xs text-gray-400">נק׳</span>
              </div>

              {/* Question-type selector */}
              <select
                value={question.question_type || 'short_answer'}
                onChange={e => handleQuestionTypeChange(qIndex, e.target.value as RubricQuestion['question_type'])}
                onClick={e => e.stopPropagation()}
                className="text-xs border border-surface-200 rounded-lg px-2 py-1 bg-white text-gray-600 focus:outline-none focus:ring-2 focus:ring-primary-200 flex-shrink-0"
                dir="rtl"
              >
                <option value="short_answer">תשובה קצרה</option>
                <option value="coding_task">תכנות</option>
                <option value="trace_table">טבלת מעקב</option>
                <option value="computation">חישוב</option>
                <option value="proof">הוכחה</option>
                <option value="essay">חיבור</option>
                <option value="source_analysis">ניתוח מקור</option>
              </select>

              {/* Badges row */}
              <div className="flex items-center gap-2 flex-shrink-0 mr-2">
                {question.code_blocks && question.code_blocks.length > 0 && (
                  <span className="px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded-full flex items-center gap-1">
                    <Code size={12} />
                    {question.code_blocks.length} קוד
                  </span>
                )}
                {question.trace_tables && question.trace_tables.length > 0 && (
                  <span className="px-2 py-1 bg-purple-100 text-purple-700 text-xs rounded-full flex items-center gap-1">
                    <Table size={12} />
                    {question.trace_tables.length} טבלת מעקב
                  </span>
                )}
                {question.example_solution && (
                  <span className="px-2 py-1 bg-green-100 text-green-700 text-xs rounded-full flex items-center gap-1">
                    <Lightbulb size={12} />
                    פתרון
                  </span>
                )}
                {/* Validation error badge */}
                {(() => {
                  const errorCount = getQuestionErrorCount(question, qIndex, questions);
                  return errorCount > 0 ? (
                    <span className="px-2 py-1 bg-red-100 text-red-700 text-xs rounded-full flex items-center gap-1 font-medium">
                      <AlertCircle size={12} />
                      {errorsBadgeLabel(errorCount)}
                    </span>
                  ) : null;
                })()}
              </div>

              {/* Remove question button */}
              <button
                onClick={e => { e.stopPropagation(); handleRemoveQuestion(qIndex); }}
                title="הסר שאלה"
                className="flex-shrink-0 text-gray-300 hover:text-red-500 transition-colors p-1 rounded"
              >
                <Trash2 size={15} />
              </button>
            </div>

            {/* Question content */}
            {expandedQuestions.has(qIndex) && (
              <div className="p-4 space-y-4 border-t border-surface-200">
                {/* Question-level annotations.
                    Two clauses: legacy backend "q1" format and raw question_id
                    from live validators (INV-R1). */}
                {annotations
                  .filter(a =>
                    a.target_id === `q${parseQuestionNumber(question.question_id)}` ||
                    a.target_id === question.question_id
                  )
                  .map(a => <AnnotationBanner key={a.id} annotation={a} />)
                }

                {/* PDF Pages for Question Text (PDF source only) */}
                {sourceType === 'pdf' && (
                  <PdfPagesDisplay
                    pages={pages}
                    pageIndexes={getQuestionPageIndexes(parseQuestionNumber(question.question_id))}
                    label="עמודי השאלה במקור"
                  />
                )}

                {/* Question text */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    טקסט השאלה
                  </label>
                  <MarkdownTextRenderer
                    value={question.question_text || ''}
                    onChange={(val) => updateQuestion(qIndex, { question_text: val })}
                    placeholder="טקסט השאלה..."
                    minHeight="60px"
                    maxHeight="240px"
                  />
                </div>

                {/* Code Blocks (DOCX source) */}
                {question.code_blocks && question.code_blocks.length > 0 && (
                  <CodeBlocksDisplay
                    codeBlocks={question.code_blocks}
                    language={programmingLanguage}
                  />
                )}

                {/* Context Tables (DOCX source) — class interfaces, I/O data tables */}
                {question.context_tables && question.context_tables.length > 0 && (
                  <QuestionContextTablesDisplay contextTables={question.context_tables} />
                )}

                {/* Example Solution — editable */}
                <ExampleSolutionEditor
                  value={question.example_solution}
                  onChange={val => handleExampleSolutionChange(qIndex, val)}
                />

                {/* Trace Tables (DOCX source) */}
                {question.trace_tables && question.trace_tables.length > 0 && (
                  <TraceTablesDisplay traceTables={question.trace_tables} />
                )}

                {/* Sub-questions or direct criteria */}
                {(question.sub_questions?.length ?? 0) > 0 ? (
                  <div className="space-y-4">
                    {/* B-11: recursive render — a sub-question with nested
                        sub_questions renders child nodes; a leaf renders its
                        criteria. data-scope-id is the FULL dotted path so a
                        backend/validator annotation targeting q1.א.2 anchors here. */}
                    {question.sub_questions.map((subQ, sqIndex) => (
                      <SubQuestionNode
                        key={subQ.sub_question_id}
                        subQ={subQ}
                        qIndex={qIndex}
                        questionId={question.question_id}
                        sqPath={[sqIndex]}
                        idPath={`${question.question_id}.${subQ.sub_question_id}`}
                        annotations={annotations}
                        sourceType={sourceType}
                        pages={pages}
                        enhancingCriterionIds={enhancingCriterionIds}
                        onTitleChange={handleSubQTitleAtPath}
                        onPointsChange={handleSubQPointsAtPath}
                        onTextChange={handleSubQTextAtPath}
                        onRemove={handleRemoveSubQAtPath}
                        onUpdateCriterion={handleUpdateCriterionAtPath}
                        onAddCriterion={handleAddCriterionAtPath}
                        onRemoveCriterion={handleRemoveCriterionAtPath}
                        onReorderCriteria={handleReorderCriteriaAtPath}
                        onAcceptProposals={handleAcceptProposalsAtPath}
                        onRejectProposals={handleRejectProposalsAtPath}
                        getSubQuestionCriteriaPageIndexes={getSubQuestionCriteriaPageIndexes}
                      />
                    ))}

                    {/* Add sub-question button (top-level only; nested-node CRUD is B-11 MVP-deferred) */}
                    <button
                      onClick={() => handleAddSubQuestion(qIndex)}
                      className="flex items-center gap-1.5 text-xs text-primary-500 hover:text-primary-700 transition-colors mt-1"
                      dir="rtl"
                    >
                      <Plus size={13} />
                      <span>הוסף סעיף</span>
                    </button>
                  </div>
                ) : (
                  <>
                    {/* PDF Pages for Direct Criteria */}
                    {sourceType === 'pdf' && (
                      <PdfPagesDisplay
                        pages={pages}
                        pageIndexes={getCriteriaPageIndexes(parseQuestionNumber(question.question_id))}
                        label="טבלת קריטריונים במקור"
                      />
                    )}

                    {/* Direct criteria */}
                    <CriteriaList
                      criteria={question.criteria}
                      onUpdateCriterion={(cIndex, updates) => updateCriterion(qIndex, cIndex, updates)}
                      onAddCriterion={() => addCriterion(qIndex)}
                      onRemoveCriterion={(cIndex) => removeCriterion(qIndex, cIndex)}
                      onReorderCriteria={(fromIndex, toIndex) => reorderCriteria(qIndex, fromIndex, toIndex)}
                      extractionStatus={question.extraction_status}
                      extractionError={question.extraction_error}
                      proposals={question.proposals}
                      onAcceptProposals={() => acceptProposals(qIndex)}
                      onRejectProposals={() => rejectProposals(qIndex)}
                      enhancingCriterionIds={enhancingCriterionIds}
                    />

                    {/* Add sub-question button */}
                    <button
                      onClick={() => handleAddSubQuestion(qIndex)}
                      className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-primary-500 transition-colors mt-1"
                      dir="rtl"
                    >
                      <Plus size={13} />
                      <span>הוסף סעיף (עבור למבנה עם תת-שאלות)</span>
                    </button>
                  </>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Add question button */}
      <button
        onClick={handleAddQuestion}
        className="w-full flex items-center justify-center gap-2 py-3 border-2 border-dashed border-primary-200 rounded-lg text-sm text-primary-500 hover:border-primary-400 hover:text-primary-700 hover:bg-primary-50 transition-all"
        dir="rtl"
      >
        <Plus size={16} />
        <span>הוסף שאלה</span>
      </button>
    </div>
  );
}

// Code Blocks Display (NEW - DOCX Pipeline)
// =============================================================================

interface CodeBlocksDisplayProps {
  codeBlocks: string[];
  language?: string;
}

function CodeBlocksDisplay({ codeBlocks, language }: CodeBlocksDisplayProps) {
  const [expandedBlock, setExpandedBlock] = useState<number | null>(null);

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-sm text-gray-600">
        <Code size={16} className="text-blue-500" />
        <span className="font-medium">בלוקי קוד ({codeBlocks.length})</span>
        {language && <span className="text-xs text-gray-400">{language}</span>}
      </div>

      <div className="space-y-2">
        {codeBlocks.map((code, idx) => (
          <div key={idx} className="border border-gray-200 rounded-lg overflow-hidden">
            <button
              onClick={() => setExpandedBlock(expandedBlock === idx ? null : idx)}
              className="w-full flex items-center justify-between p-2 bg-gray-50 hover:bg-gray-100 text-sm"
            >
              <span className="font-mono text-gray-600 truncate max-w-[80%]">
                {code.split('\n')[0].slice(0, 50)}...
              </span>
              {expandedBlock === idx ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
            {expandedBlock === idx && (
              <pre className="p-3 bg-gray-900 text-gray-100 text-xs overflow-x-auto max-h-[300px]" dir="ltr">
                <code>{code}</code>
              </pre>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// =============================================================================
// Example Solution Display (NEW - DOCX Pipeline)
// =============================================================================

interface ExampleSolutionDisplayProps {
  solution: string;
  language?: string;
}

function ExampleSolutionDisplay({ solution, language }: ExampleSolutionDisplayProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="border border-green-200 rounded-lg overflow-hidden bg-green-50">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-3 hover:bg-green-100"
      >
        <div className="flex items-center gap-2 text-green-700">
          <Lightbulb size={16} />
          <span className="font-medium text-sm">פתרון לדוגמה</span>
          {language && <span className="text-xs text-green-500">({language})</span>}
        </div>
        {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>

      {isExpanded && (
        <pre className="p-3 bg-gray-900 text-gray-100 text-xs overflow-x-auto max-h-[400px]" dir="ltr">
          <code>{solution}</code>
        </pre>
      )}
    </div>
  );
}

// =============================================================================
// Trace Tables Display (NEW - DOCX Pipeline)
// =============================================================================

interface TraceTablesDisplayProps {
  traceTables: TraceTableData[];
}

function TraceTablesDisplay({ traceTables }: TraceTablesDisplayProps) {
  const [expandedTable, setExpandedTable] = useState<number | null>(0);

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-sm text-gray-600">
        <Table size={16} className="text-purple-500" />
        <span className="font-medium">טבלאות מעקב ({traceTables.length})</span>
      </div>

      {traceTables.map((table, idx) => (
        <div key={idx} className="border border-purple-200 rounded-lg overflow-hidden">
          <button
            onClick={() => setExpandedTable(expandedTable === idx ? null : idx)}
            className="w-full flex items-center justify-between p-2 bg-purple-50 hover:bg-purple-100 text-sm"
          >
            <span className="text-purple-700">
              טבלה {idx + 1}: {table.headers.slice(0, 4).join(', ')}
              {table.headers.length > 4 && '...'}
            </span>
            <span className="text-xs text-purple-500">{table.row_count} שורות</span>
          </button>

          {expandedTable === idx && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs" dir="ltr">
                <thead className="bg-purple-100">
                  <tr>
                    {table.headers.map((h: string, i: number) => (
                      <th key={i} className="px-2 py-1 text-right font-medium text-purple-800 border-b">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {table.rows.slice(0, 10).map((row: Record<string, string>, rowIdx: number) => (
                    <tr key={rowIdx} className={rowIdx % 2 === 0 ? 'bg-white' : 'bg-purple-50/50'}>
                      {table.headers.map((h: string, colIdx: number) => (
                        <td key={colIdx} className="px-2 py-1 border-b border-purple-100 font-mono">
                          {row[h] || '-'}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {table.row_count > 10 && (
                <div className="p-2 text-center text-xs text-purple-500 bg-purple-50">
                  ... ועוד {table.row_count - 10} שורות
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// =============================================================================
// Question Context Tables Display Component
// Renders QUESTION_LAYOUT_TABLE / EXAMPLE_DATA_TABLE content that is part of
// the question itself — e.g. a class interface definition or an I/O data table.
// Visually distinct from trace tables (blue-grey palette, different label).
// =============================================================================

interface QuestionContextTablesDisplayProps {
  contextTables: ContextTableData[];
}

function QuestionContextTablesDisplay({ contextTables }: QuestionContextTablesDisplayProps) {
  const [expandedTables, setExpandedTables] = useState<Set<number>>(
    () => new Set(contextTables.map((_, i) => i))
  );

  if (!contextTables || contextTables.length === 0) return null;

  // Default behavior: show (expand) all context tables. Reset when count changes
  // (e.g., when switching to another rubric/question).
  useEffect(() => {
    setExpandedTables(new Set(contextTables.map((_, i) => i)));
  }, [contextTables.length]);

  // Infer per-table direction. Some DOCX "context tables" are actually LTR (arrays, code-ish I/O),
  // even inside an overall Hebrew/RTL document. Rendering them with dir="rtl" reverses columns.
  const inferGridDir = (grid: string[][]): 'rtl' | 'ltr' => {
    const hebrewRe = /[\u0590-\u05FF]/;
    const latinRe = /[A-Za-z]/;
    for (const row of grid) {
      for (const cell of row) {
        const s = (cell ?? '').trim();
        if (!s) continue;
        if (hebrewRe.test(s)) return 'rtl';
        if (latinRe.test(s)) return 'ltr';
      }
    }
    // Digits/punctuation-only tables (common for arrays) should default to LTR to preserve order.
    return 'ltr';
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-sm text-gray-600">
        <Table size={16} className="text-blue-500" />
        <span className="font-medium text-blue-700">
          {contextTables.length === 1 ? 'טבלת הקשר לשאלה' : `טבלאות הקשר לשאלה (${contextTables.length})`}
        </span>
      </div>

      {contextTables.map((table, idx) => {
        // Defensive: backend may still send old {headers, rows} shape if server
        // hasn't restarted with the new transformer. Normalise to grid on the fly.
        const raw = table as unknown as Record<string, unknown>;
        const title =
          (typeof (table as unknown as { title?: unknown }).title === 'string'
            ? ((table as unknown as { title?: string }).title ?? '').trim()
            : typeof raw['title'] === 'string'
              ? (raw['title'] as string).trim()
              : '') || '';
        const grid: string[][] = Array.isArray(table.grid)
          ? table.grid
          : Array.isArray(raw['headers'])
            ? [raw['headers'] as string[], ...(raw['rows'] as Record<string, string>[]).map(
              row => (raw['headers'] as string[]).map(h => row[h] ?? '')
            )]
            : [];

        const rowCount = table.row_count ?? grid.length;
        const colCount = (table as ContextTableData).col_count ?? (grid[0]?.length ?? 0);
        const tableDir = inferGridDir(grid);
        const titleDir: 'rtl' | 'ltr' = /[\u0590-\u05FF]/.test(title) ? 'rtl' : 'ltr';
        const buttonLabel = `טבלה ${idx + 1}`;
        const isExpanded = expandedTables.has(idx);

        return (
          <div key={idx} className="border border-blue-200 rounded-lg overflow-hidden">
            <button
              onClick={() => {
                setExpandedTables(prev => {
                  const next = new Set(prev);
                  if (next.has(idx)) next.delete(idx);
                  else next.add(idx);
                  return next;
                });
              }}
              className="w-full flex items-center justify-between p-2 bg-blue-50 hover:bg-blue-100 text-sm transition-colors"
            >
              <span className="text-gray-900 font-medium truncate max-w-xs">
                {buttonLabel}
              </span>
              <div className="flex items-center gap-2 flex-shrink-0">
                <span className="text-xs text-blue-400">
                  {rowCount} × {colCount}
                </span>
                {isExpanded
                  ? <ChevronUp size={14} className="text-blue-400" />
                  : <ChevronDown size={14} className="text-blue-400" />
                }
              </div>
            </button>

            {isExpanded && (
              <div className="overflow-x-auto">
                {title && (
                  <div
                    className="px-3 py-2 text-sm font-medium text-blue-900 bg-blue-50 border-b border-blue-100"
                    dir={titleDir}
                  >
                    {title}
                  </div>
                )}
                <table className="text-xs border-collapse" dir={tableDir}>
                  <tbody>
                    {grid.map((row: string[], rowIdx: number) => (
                      <tr
                        key={rowIdx}
                        className={rowIdx === 0 ? 'bg-blue-100' : rowIdx % 2 === 0 ? 'bg-white' : 'bg-blue-50/40'}
                      >
                        {row.map((cell: string, colIdx: number) => {
                          const Tag = rowIdx === 0 ? 'th' : 'td';
                          return (
                            <Tag
                              key={colIdx}
                              className={[
                                'px-3 py-2 border border-blue-100 align-top',
                                tableDir === 'rtl' ? 'text-right' : 'text-left',
                                rowIdx === 0 ? 'font-semibold text-blue-900' : 'text-gray-700',
                                !cell ? 'text-gray-300' : '',
                              ].join(' ')}
                            >
                              {cell || ''}
                            </Tag>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// =============================================================================
// PDF Pages Display Component
// =============================================================================

interface PdfPagesDisplayProps {
  pages?: PagePreview[];
  pageIndexes: number[];
  label: string;
}

function PdfPagesDisplay({ pages, pageIndexes, label }: PdfPagesDisplayProps) {
  const [currentPageIdx, setCurrentPageIdx] = useState(0);
  const [expandedPage, setExpandedPage] = useState<number | null>(null);

  if (!pages || pageIndexes.length === 0) return null;

  const relevantPages = pageIndexes
    .filter(idx => idx >= 0 && idx < pages.length)
    .map(idx => pages[idx]);

  if (relevantPages.length === 0) return null;

  const hasPdfUrls = relevantPages.some(p => p.page_pdf_url);
  const hasMultiplePages = relevantPages.length > 1;

  const goToPrevPage = () => {
    setCurrentPageIdx(prev => Math.max(0, prev - 1));
  };

  const goToNextPage = () => {
    setCurrentPageIdx(prev => Math.min(relevantPages.length - 1, prev + 1));
  };

  return (
    <div className="mb-4">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2 text-sm text-gray-600">
          <FileText size={16} className="text-primary-500" />
          <span className="font-medium">{label}</span>
          {hasMultiplePages && (
            <span className="text-gray-400">
              (עמוד {currentPageIdx + 1} מתוך {relevantPages.length})
            </span>
          )}
        </div>

        {/* Navigation arrows for multiple pages */}
        {hasMultiplePages && (
          <div className="flex items-center gap-1">
            <button
              onClick={goToPrevPage}
              disabled={currentPageIdx === 0}
              className="p-1 rounded hover:bg-surface-100 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <ChevronRight size={18} className="text-gray-500" />
            </button>
            <button
              onClick={goToNextPage}
              disabled={currentPageIdx === relevantPages.length - 1}
              className="p-1 rounded hover:bg-surface-100 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <ChevronLeft size={18} className="text-gray-500" />
            </button>
          </div>
        )}
      </div>

      {/* PDF/Thumbnail Display */}
      <div className="relative bg-surface-50 rounded-lg border border-surface-200 overflow-hidden">
        {hasPdfUrls ? (
          // Display PDF in iframe for text selection
          <div className="relative">
            <iframe
              src={`${relevantPages[currentPageIdx].page_pdf_url}#toolbar=0&navpanes=0&zoom=70`}
              className="w-full h-[320px] border-0"
              title={`עמוד ${relevantPages[currentPageIdx].page_number}`}
            />
            {/* Expand button */}
            <button
              onClick={() => setExpandedPage(currentPageIdx)}
              className="absolute top-2 left-2 p-1.5 bg-white/90 hover:bg-white rounded-lg shadow-md transition-colors"
              title="הגדל"
            >
              <Maximize2 size={16} className="text-gray-600" />
            </button>
          </div>
        ) : (
          // Fallback to thumbnail
          <div className="relative">
            <img
              src={`data:image/png;base64,${relevantPages[currentPageIdx].thumbnail_base64}`}
              alt={`עמוד ${relevantPages[currentPageIdx].page_number}`}
              className="w-full max-h-[320px] object-contain"
            />
            <button
              onClick={() => setExpandedPage(currentPageIdx)}
              className="absolute top-2 left-2 p-1.5 bg-white/90 hover:bg-white rounded-lg shadow-md transition-colors"
              title="הגדל"
            >
              <Maximize2 size={16} className="text-gray-600" />
            </button>
          </div>
        )}
      </div>

      {/* Expanded Modal */}
      {expandedPage !== null && (
        <div
          className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4"
          onClick={() => setExpandedPage(null)}
        >
          <div className="relative max-w-4xl max-h-[90vh] w-full bg-white rounded-lg overflow-hidden" onClick={e => e.stopPropagation()}>
            <button
              onClick={() => setExpandedPage(null)}
              className="absolute top-2 right-2 p-2 bg-black/50 hover:bg-black/70 rounded-full text-white z-10"
            >
              <X size={20} />
            </button>
            {hasPdfUrls ? (
              <iframe
                src={`${relevantPages[expandedPage].page_pdf_url}#toolbar=0&navpanes=0`}
                className="w-full h-[85vh] border-0"
                title={`עמוד ${relevantPages[expandedPage].page_number}`}
              />
            ) : (
              <img
                src={`data:image/png;base64,${relevantPages[expandedPage].thumbnail_base64}`}
                alt={`עמוד ${relevantPages[expandedPage].page_number}`}
                className="w-full h-auto max-h-[85vh] object-contain"
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Sub-Criteria Editor Component — add/edit/delete sub-criteria with point inputs
// =============================================================================

interface SubCriteriaEditorProps {
  subCriteria: RubricSubCriterion[] | null;
  totalPoints: number;
  onSubCriteriaChange: (sc: RubricSubCriterion[] | null) => void;
}

function SubCriteriaEditor({ subCriteria, totalPoints, onSubCriteriaChange }: SubCriteriaEditorProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const list = subCriteria || [];
  const subSum = list.reduce((s, sc) => s + sc.points, 0);
  const hasMismatch = list.length > 0 && Math.abs(subSum - totalPoints) > 0.01;

  const addSubCriterion = () => {
    const remaining = Math.max(0, totalPoints - subSum);
    const newSc: RubricSubCriterion = {
      sub_criterion_id: `sc${Date.now()}`,
      index: list.length,
      description: '',
      points: remaining > 0 ? Math.min(1, remaining) : 1,
    };
    onSubCriteriaChange([...list, newSc]);
    setIsExpanded(true);
  };

  const updateSubCriterion = (idx: number, patch: Partial<RubricSubCriterion>) => {
    const next = [...list];
    next[idx] = { ...next[idx], ...patch };
    onSubCriteriaChange(next);
  };

  const deleteSubCriterion = (idx: number) => {
    const next = list.filter((_, i) => i !== idx).map((sc, i) => ({ ...sc, index: i }));
    onSubCriteriaChange(next.length > 0 ? next : null);
    if (next.length === 0) setIsExpanded(false);
  };

  return (
    <div className="mt-3" dir="rtl">
      <div className="flex items-center gap-2">
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="group flex items-center gap-2 flex-1 px-3 py-2 rounded-lg bg-gradient-to-l from-slate-50 to-slate-100 hover:from-slate-100 border border-slate-200 transition-all duration-200"
        >
          <div className="flex items-center gap-2 flex-1">
            {isExpanded
              ? <ChevronUp size={14} className="text-slate-400 group-hover:text-slate-600 transition-colors" />
              : <ChevronDown size={14} className="text-slate-400 group-hover:text-slate-600 transition-colors" />
            }
            <span className="text-sm font-medium text-slate-600">
              {list.length > 0 ? `פירוט ניקוד (${list.length})` : 'פירוט ניקוד'}
            </span>
          </div>
          {list.length > 0 && (
            <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold shadow-sm ${
              hasMismatch
                ? 'bg-amber-100 text-amber-800 border border-amber-300'
                : 'bg-gradient-to-l from-blue-500 to-indigo-500 text-white'
            }`}>
              <span>סה״כ</span>
              <span className="font-mono">{subSum}</span>
              <span>נק׳</span>
            </div>
          )}
        </button>
        <button
          onClick={addSubCriterion}
          className="p-2 rounded-lg bg-primary-50 hover:bg-primary-100 border border-primary-200 text-primary-600 hover:text-primary-700 transition-colors"
          title="הוסף פירוט"
        >
          <Plus size={14} />
        </button>
      </div>

      {isExpanded && (
        <div className="mt-2 rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
          {list.length === 0 ? (
            <div className="px-4 py-5 text-center">
              <p className="text-xs text-slate-400 mb-3">
                אין פירוט ניקוד. ניתן להוסיף תת-קריטריונים לפירוט הניקוד.
              </p>
              <button
                onClick={addSubCriterion}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary-50 hover:bg-primary-100 text-primary-600 text-sm font-medium transition-colors"
              >
                <Plus size={14} />
                <span>הוסף פירוט</span>
              </button>
            </div>
          ) : (
            <div className="p-3 space-y-2">
              {list.map((sc, idx) => (
                <div key={sc.sub_criterion_id} className="flex items-center gap-2 p-2.5 rounded-lg bg-blue-50 border border-blue-100">
                  <div className="w-2 h-2 rounded-full bg-blue-400 flex-shrink-0" />
                  <input
                    type="text"
                    value={sc.description}
                    onChange={(e) => updateSubCriterion(idx, { description: e.target.value })}
                    className="flex-1 bg-transparent border-none outline-none text-sm text-slate-700 placeholder-slate-400"
                    placeholder="תיאור..."
                    dir="rtl"
                  />
                  <input
                    type="number"
                    defaultValue={sc.points}
                    key={`${sc.sub_criterion_id}-${sc.points}`}
                    onBlur={(e) => {
                      const value = parseFloat(e.target.value);
                      if (!isNaN(value) && value >= 0) {
                        updateSubCriterion(idx, { points: value });
                      } else {
                        e.target.value = String(sc.points);
                      }
                    }}
                    className="w-14 text-center text-xs font-bold rounded-md px-2 py-1 bg-blue-500 text-white"
                    min={0}
                    step={0.25}
                  />
                  <button
                    onClick={() => deleteSubCriterion(idx)}
                    className="p-1 text-slate-400 hover:text-red-500 transition-colors flex-shrink-0"
                    title="מחק"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
              <div className="flex items-center justify-between pt-2 border-t border-slate-100">
                <button
                  onClick={addSubCriterion}
                  className="inline-flex items-center gap-1 text-xs text-primary-600 hover:text-primary-700"
                >
                  <Plus size={12} />
                  <span>הוסף פירוט</span>
                </button>
                {hasMismatch && (
                  <div className="flex items-center gap-1.5 text-xs text-amber-700 font-medium" dir="rtl">
                    <AlertTriangle size={12} className="flex-shrink-0" />
                    <span>
                      {subSum < totalPoints
                        ? `חסרות ${(totalPoints - subSum).toFixed(2)} נק׳ בפירוט הניקוד (סה״כ פירוט ${subSum}, נקודות הקריטריון ${totalPoints})`
                        : `יש עודף של ${(subSum - totalPoints).toFixed(2)} נק׳ בפירוט הניקוד (סה״כ פירוט ${subSum}, נקודות הקריטריון ${totalPoints})`}
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// AnnotationBanner (the rubric-surface severity renderer) was lifted to its own
// file in PR-5 S2 — `@/components/AnnotationBanner` (imported at the top). The
// mirror (RubricDocument) imports the same one copy.

// =============================================================================
// Sub-Question Node (B-11) — recursive render at any nesting depth
// =============================================================================

interface SubQuestionNodeProps {
  subQ: RubricSubQuestion;
  qIndex: number;
  questionId: string;
  /** Positional index chain from the question down (e.g. [0] or [0, 1]). */
  sqPath: number[];
  /** Full dotted id-path (e.g. "q1.א.2") — the annotation/scroll anchor. */
  idPath: string;
  annotations: Annotation[];
  sourceType?: 'pdf' | 'docx';
  pages?: PagePreview[];
  enhancingCriterionIds?: Set<string>;
  onTitleChange: (qIndex: number, sqPath: number[], title: string | null) => void;
  onPointsChange: (qIndex: number, sqPath: number[], newPts: number) => void;
  onTextChange: (qIndex: number, sqPath: number[], text: string) => void;
  /** Present only where structural remove is offered (top-level, MVP). */
  onRemove?: (qIndex: number, sqPath: number[]) => void;
  onUpdateCriterion: (qIndex: number, sqPath: number[], cIndex: number, updates: Partial<RubricCriterion>) => void;
  onAddCriterion: (qIndex: number, sqPath: number[]) => void;
  onRemoveCriterion: (qIndex: number, sqPath: number[], cIndex: number) => void;
  onReorderCriteria: (qIndex: number, sqPath: number[], fromIndex: number, toIndex: number) => void;
  onAcceptProposals?: (qIndex: number, sqPath: number[]) => void;
  onRejectProposals?: (qIndex: number, sqPath: number[]) => void;
  getSubQuestionCriteriaPageIndexes?: (questionNumber: number, subQuestionId: string) => number[];
}

/**
 * One sub-question, rendered recursively. A PARENT (has sub_questions) renders
 * child SubQuestionNodes; a LEAF renders its CriteriaList. Reuses CriteriaList,
 * MarkdownTextRenderer, TraceTablesDisplay and AnnotationBanner unchanged. MVP:
 * edit points/text/title/criteria in place at any depth; nested-node add/remove
 * is deferred, so a child gets no remove button and no add-sub-question control.
 */
function SubQuestionNode(props: SubQuestionNodeProps) {
  const {
    subQ, qIndex, questionId, sqPath, idPath, annotations,
    sourceType, pages, enhancingCriterionIds,
  } = props;
  const hasChildren = (subQ.sub_questions?.length ?? 0) > 0;
  const positionalIndex = sqPath[sqPath.length - 1];

  return (
    <div
      data-scope-id={idPath}
      className="mr-4 border-r-2 border-primary-200 pr-4 space-y-3"
    >
      {/* Header: title, points, remove */}
      <div className="flex items-center gap-2" dir="rtl">
        <input
          type="text"
          defaultValue={subQ.title || ''}
          key={`${subQ.sub_question_id}-${subQ.title ?? ''}`}
          placeholder={defaultSubQuestionTitle(positionalIndex)}
          onBlur={(e) => {
            const trimmed = e.target.value.trim();
            props.onTitleChange(qIndex, sqPath, trimmed || null);
          }}
          className="font-semibold text-primary-700 bg-transparent border-b border-transparent hover:border-primary-200 focus:border-primary-500 focus:outline-none px-1 min-w-[80px]"
          dir="rtl"
          aria-label="כותרת הסעיף"
        />
        <input
          type="number"
          defaultValue={subQ.points}
          key={subQ.points}
          onBlur={e => {
            const val = parseFloat(e.target.value);
            if (!isNaN(val) && val >= 0) props.onPointsChange(qIndex, sqPath, val);
            else e.target.value = String(subQ.points);
          }}
          min={0}
          step={0.25}
          className="w-14 text-center text-xs border border-surface-200 rounded-lg px-1.5 py-1 bg-white focus:outline-none focus:ring-2 focus:ring-primary-200 font-semibold"
          title="נקודות הסעיף"
        />
        <span className="text-xs text-gray-400">נק׳</span>
        <div className="flex-1" />
        {props.onRemove && (
          <button
            onClick={() => props.onRemove!(qIndex, sqPath)}
            title="הסר סעיף"
            className="text-gray-300 hover:text-red-400 transition-colors p-0.5 rounded"
          >
            <Trash2 size={13} />
          </button>
        )}
      </div>

      {/* Node-level annotations. Full dotted path (INV-R1b / backend q1.א.2),
          plus legacy clauses for depth-1 back-compat. */}
      {annotations
        .filter(a =>
          a.target_id === idPath ||
          a.target_id === `q${parseQuestionNumber(questionId)}.${subQ.sub_question_id}` ||
          a.target_id === subQ.sub_question_id
        )
        .map(a => <AnnotationBanner key={a.id} annotation={a} />)
      }

      {/* Sub-question text */}
      <MarkdownTextRenderer
        value={subQ.text || ''}
        onChange={(val) => props.onTextChange(qIndex, sqPath, val)}
        placeholder="טקסט הסעיף..."
        minHeight="40px"
        maxHeight="180px"
      />

      {/* Sub-question trace tables */}
      {subQ.trace_tables && subQ.trace_tables.length > 0 && (
        <TraceTablesDisplay traceTables={subQ.trace_tables} />
      )}

      {hasChildren ? (
        // PARENT — recurse into nested sub-questions (no criteria of its own).
        <div className="space-y-4">
          {subQ.sub_questions!.map((child, i) => (
            <SubQuestionNode
              {...props}
              key={child.sub_question_id}
              subQ={child}
              sqPath={[...sqPath, i]}
              idPath={`${idPath}.${child.sub_question_id}`}
              onRemove={undefined}
            />
          ))}
        </div>
      ) : (
        // LEAF — render its criteria.
        <>
          {sourceType === 'pdf' && sqPath.length === 1 && props.getSubQuestionCriteriaPageIndexes && (
            <PdfPagesDisplay
              pages={pages}
              pageIndexes={props.getSubQuestionCriteriaPageIndexes(parseQuestionNumber(questionId), subQ.sub_question_id)}
              label="טבלת קריטריונים במקור"
            />
          )}
          <CriteriaList
            criteria={subQ.criteria}
            onUpdateCriterion={(cIndex, updates) => props.onUpdateCriterion(qIndex, sqPath, cIndex, updates)}
            onAddCriterion={() => props.onAddCriterion(qIndex, sqPath)}
            onRemoveCriterion={(cIndex) => props.onRemoveCriterion(qIndex, sqPath, cIndex)}
            onReorderCriteria={(fromIndex, toIndex) => props.onReorderCriteria(qIndex, sqPath, fromIndex, toIndex)}
            extractionStatus={subQ.extraction_status}
            extractionError={subQ.extraction_error}
            proposals={sqPath.length === 1 ? subQ.proposals : null}
            onAcceptProposals={props.onAcceptProposals ? () => props.onAcceptProposals!(qIndex, sqPath) : undefined}
            onRejectProposals={props.onRejectProposals ? () => props.onRejectProposals!(qIndex, sqPath) : undefined}
            enhancingCriterionIds={enhancingCriterionIds}
            annotations={annotations}
          />
        </>
      )}
    </div>
  );
}

// =============================================================================
// Criteria List Component
// =============================================================================

interface CriteriaListProps {
  criteria: RubricCriterion[];
  onUpdateCriterion: (index: number, updates: Partial<RubricCriterion>) => void;
  onAddCriterion: () => void;
  onRemoveCriterion: (index: number) => void;
  onReorderCriteria: (fromIndex: number, toIndex: number) => void;
  // Extraction status for showing warnings
  extractionStatus?: 'success' | 'partial' | 'failed';
  extractionError?: string | null;
  // Proposal support
  proposals?: ProposalSet | null;
  onAcceptProposals?: () => void;
  onRejectProposals?: () => void;
  // Post-acceptance loading state
  enhancingCriterionIds?: Set<string>;
  // Annotations for per-criterion banners
  annotations?: Annotation[];
}

function CriteriaList({
  criteria,
  onUpdateCriterion,
  onAddCriterion,
  onRemoveCriterion,
  onReorderCriteria,
  extractionStatus = 'success',
  extractionError,
  proposals,
  onAcceptProposals,
  onRejectProposals,
  enhancingCriterionIds,
  annotations = [],
}: CriteriaListProps) {
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [dropPosition, setDropPosition] = useState<{ index: number; position: 'above' | 'below' } | null>(null);

  const handleDragStart = (e: React.DragEvent, index: number) => {
    setDraggedIndex(index);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', index.toString());
  };

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';

    if (draggedIndex === null || draggedIndex === index) {
      setDropPosition(null);
      return;
    }

    // Determine if cursor is in upper or lower half of the element
    const rect = e.currentTarget.getBoundingClientRect();
    const midpoint = rect.top + rect.height / 2;
    const position = e.clientY < midpoint ? 'above' : 'below';

    setDropPosition({ index, position });
  };

  const handleDragLeave = () => {
    setDropPosition(null);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();

    if (draggedIndex === null || dropPosition === null) {
      setDraggedIndex(null);
      setDropPosition(null);
      return;
    }

    let targetIndex = dropPosition.index;

    // Calculate the actual insert position
    if (dropPosition.position === 'below') {
      targetIndex = targetIndex + 1;
    }

    // Adjust for the removal of the dragged item
    if (draggedIndex < targetIndex) {
      targetIndex = targetIndex - 1;
    }

    if (draggedIndex !== targetIndex) {
      onReorderCriteria(draggedIndex, targetIndex);
    }

    setDraggedIndex(null);
    setDropPosition(null);
  };

  const handleDragEnd = () => {
    setDraggedIndex(null);
    setDropPosition(null);
  };

  // Check if drop indicator should show above/below a specific item
  const getDropIndicator = (index: number): 'above' | 'below' | null => {
    if (!dropPosition || draggedIndex === null) return null;
    if (dropPosition.index === index) return dropPosition.position;
    return null;
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-gray-700">קריטריונים</label>
        <button
          onClick={onAddCriterion}
          className="text-xs text-primary-600 hover:text-primary-700 flex items-center gap-1"
        >
          <Plus size={14} />
          הוסף קריטריון
        </button>
      </div>

      {/* Extraction Status Warning */}
      {extractionStatus === 'failed' && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2 text-red-700 mb-2">
          <AlertCircle size={16} className="flex-shrink-0 mt-0.5" />
          <div className="text-sm">
            <div className="font-medium">שגיאה בחילוץ קריטריונים</div>
            <div className="text-red-600">{extractionError || 'לא הצלחנו לחלץ קריטריונים מהעמוד'}</div>
          </div>
        </div>
      )}

      {/* Empty criteria with success status - pages might be wrong */}
      {criteria.length === 0 && extractionStatus === 'success' && (
        <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg flex items-start gap-2 text-amber-700 mb-2">
          <AlertTriangle size={16} className="flex-shrink-0 mt-0.5" />
          <div className="text-sm">
            לא נמצאו קריטריונים בעמודים שסומנו. ודא שסימנת את העמודים הנכונים או הוסף ידנית.
          </div>
        </div>
      )}

      {criteria.length === 0 ? (
        <div className="text-center py-4 text-gray-400 text-sm bg-surface-50 rounded-lg">
          אין קריטריונים. לחץ על &quot;הוסף קריטריון&quot; כדי להוסיף.
        </div>
      ) : (
        <div className="space-y-2">
          {criteria.map((criterion, cIndex) => {
            const dropIndicator = getDropIndicator(cIndex);
            const displayDescription = criterion.description || '';
            const displayPoints = criterion.points;

            return (
              <div key={cIndex} className="relative">
                {/* Drop indicator line - ABOVE */}
                {dropIndicator === 'above' && (
                  <div className="absolute -top-1 left-0 right-0 h-0.5 bg-primary-500 rounded-full z-10">
                    <div className="absolute right-0 -top-1 w-2.5 h-2.5 bg-primary-500 rounded-full" />
                  </div>
                )}

                <div
                  draggable
                  data-scope-id={criterion.criterion_id}
                  onDragStart={(e) => handleDragStart(e, cIndex)}
                  onDragOver={(e) => handleDragOver(e, cIndex)}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  onDragEnd={handleDragEnd}
                  className={`p-3 my-1 bg-surface-50 rounded-lg border transition-all duration-150 ${criterion.extraction_confidence === 'low'
                    ? 'border-amber-300 bg-amber-50'
                    : criterion.extraction_confidence === 'medium'
                      ? 'border-yellow-200 bg-yellow-50'
                      : 'border-surface-200'
                    } ${draggedIndex === cIndex ? 'opacity-40 scale-[0.98]' : ''
                    }`}
                >
                  {/* Main criterion row - RTL for Hebrew */}
                  <div className="flex items-center gap-2" dir="rtl">
                    <GripVertical
                      size={16}
                      className="text-gray-400 cursor-grab active:cursor-grabbing hover:text-gray-600 flex-shrink-0"
                    />

                    {criterion.extraction_confidence !== 'high' && (
                      <AlertCircle
                        size={16}
                        className={
                          criterion.extraction_confidence === 'low' ? 'text-amber-500' : 'text-yellow-500'
                        }
                      />
                    )}

                    <input
                      type="text"
                      value={displayDescription}
                      onChange={(e) => onUpdateCriterion(cIndex, {
                        description: e.target.value,
                      })}
                      className="flex-1 bg-transparent border-none outline-none text-sm text-right"
                      placeholder="תיאור הקריטריון..."
                      dir="rtl"
                      style={{ unicodeBidi: 'plaintext' }}
                    />

                    <input
                      type="number"
                      defaultValue={displayPoints}
                      key={`${criterion.criterion_id}-${displayPoints}`}
                      onBlur={(e) => {
                        const value = parseFloat(e.target.value);
                        if (!isNaN(value) && value >= 0) {
                          onUpdateCriterion(cIndex, { points: value });
                        } else {
                          e.target.value = String(displayPoints);
                        }
                      }}
                      className="w-16 text-center bg-white border border-surface-300 rounded px-2 py-1 text-sm font-medium"
                      min={0}
                      step={0.25}
                    />

                    <button
                      onClick={() => onRemoveCriterion(cIndex)}
                      className="text-red-400 hover:text-red-600 p-1"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>

                  {/* Sub-criteria (v3 pipeline) or reduction rules (legacy) */}
                  {enhancingCriterionIds?.has(criterion.criterion_id) ? (
                    <div className="mt-3 px-3 py-3 rounded-lg bg-violet-50 border border-violet-200 animate-pulse" dir="rtl">
                      <div className="flex items-center gap-2 text-xs text-violet-500">
                        <Loader2 size={12} className="animate-spin" />
                        <span>מייצר כללי הורדה...</span>
                      </div>
                      <div className="mt-2 space-y-1.5">
                        <div className="h-3 bg-violet-200 rounded w-3/4" />
                        <div className="h-3 bg-violet-200 rounded w-1/2" />
                      </div>
                    </div>
                  ) : (
                    <SubCriteriaEditor
                      subCriteria={criterion.sub_criteria ?? null}
                      totalPoints={displayPoints}
                      onSubCriteriaChange={(sc) => onUpdateCriterion(cIndex, { sub_criteria: sc })}
                    />
                  )}

                  {/* Per-criterion annotations */}
                  {annotations
                    .filter(a => a.target_id === criterion.criterion_id)
                    .map(a => <AnnotationBanner key={a.id} annotation={a} />)
                  }
                </div>

                {/* Drop indicator line - BELOW */}
                {dropIndicator === 'below' && (
                  <div className="absolute -bottom-1 left-0 right-0 h-0.5 bg-primary-500 rounded-full z-10">
                    <div className="absolute right-0 -top-1 w-2.5 h-2.5 bg-primary-500 rounded-full" />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* AI Proposal Banner — shown when proposals exist for this scope */}
      {proposals && proposals.proposed_criteria.length > 0 && onAcceptProposals && onRejectProposals && (
        <ProposalBanner
          proposals={proposals}
          onAccept={onAcceptProposals}
          onReject={onRejectProposals}
        />
      )}
    </div>
  );
}

// =============================================================================
// AI Proposal Banner Component
// =============================================================================

interface ProposalBannerProps {
  proposals: ProposalSet;
  onAccept: () => void;
  onReject: () => void;
}

function ProposalBanner({ proposals, onAccept, onReject }: ProposalBannerProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const count = proposals.proposed_criteria.length;

  return (
    <div
      className="mt-3 rounded-xl border-2 border-dashed border-violet-300 bg-gradient-to-l from-violet-50 to-indigo-50 overflow-hidden"
      dir="rtl"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3">
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex items-center gap-2 flex-1"
        >
          <Sparkles size={16} className="text-violet-500" />
          <span className="text-sm font-semibold text-violet-800">
            הצעות AI לקריטריונים נוספים ({count})
          </span>
          {isExpanded
            ? <ChevronUp size={14} className="text-violet-400" />
            : <ChevronDown size={14} className="text-violet-400" />
          }
        </button>

        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={onReject}
            className="px-3 py-1.5 text-xs font-medium text-gray-600 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            דחה הכל
          </button>
          <button
            onClick={onAccept}
            className="px-3 py-1.5 text-xs font-medium text-white bg-violet-600 border border-violet-700 rounded-lg hover:bg-violet-700 transition-colors"
          >
            אשר הכל
          </button>
        </div>
      </div>

      {/* Expanded content: list of proposed criteria */}
      {isExpanded && (
        <div className="px-4 pb-4 space-y-2">
          {proposals.proposed_criteria.map((pc) => (
            <div
              key={pc.temp_id}
              className="flex items-start gap-3 p-3 rounded-lg bg-white/70 border border-violet-200"
            >
              {/* AI indicator dot */}
              <div className="w-2 h-2 mt-1.5 rounded-full bg-violet-400 flex-shrink-0" />

              <div className="flex-1 min-w-0">
                {/* Description */}
                <p className="text-sm text-gray-800 leading-relaxed">
                  {pc.description}
                </p>

                {/* Explanation */}
                <p className="mt-1 text-xs text-violet-600 leading-relaxed">
                  <Lightbulb size={11} className="inline ml-1 -mt-0.5" />
                  {pc.explanation}
                </p>
              </div>

              {/* Points badge */}
              <div className="flex-shrink-0 px-2.5 py-1 rounded-full bg-violet-100 text-violet-700 text-xs font-bold">
                {pc.points} נק׳
              </div>
            </div>
          ))}

          {/* Redistribution note */}
          {proposals.enhanced_distribution.length > 0 && (
            <p className="text-xs text-violet-500 pt-1">
              <Info size={11} className="inline ml-1 -mt-0.5" />
              אישור ההצעות יעדכן את חלוקת הנקודות של הקריטריונים הקיימים.
            </p>
          )}
        </div>
      )}
    </div>
  );
}