'use client';

import { useState, useRef } from 'react';
import { ExtractedQuestion, ExtractedSubQuestion, ExtractedCriterion, ReductionRule, PagePreview, QuestionPageMapping } from '@/lib/api';
import { Plus, Trash2, ChevronDown, ChevronUp, GripVertical, AlertCircle, AlertTriangle, FileText, ChevronLeft, ChevronRight, Maximize2, X, Info } from 'lucide-react';

interface RubricEditorProps {
  questions: ExtractedQuestion[];
  onQuestionsChange: (questions: ExtractedQuestion[]) => void;
  // NEW: PDF pages and mappings for inline display
  pages?: PagePreview[];
  questionMappings?: QuestionPageMapping[];
}

export function RubricEditor({ questions, onQuestionsChange, pages, questionMappings }: RubricEditorProps) {
  const [expandedQuestions, setExpandedQuestions] = useState<Set<number>>(
    new Set(questions.map((_, i) => i))
  );

  const toggleExpanded = (index: number) => {
    const newExpanded = new Set(expandedQuestions);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedQuestions(newExpanded);
  };

  const updateQuestion = (index: number, updates: Partial<ExtractedQuestion>) => {
    const newQuestions = [...questions];
    newQuestions[index] = { ...newQuestions[index], ...updates };
    recalculateTotals(newQuestions);
    onQuestionsChange(newQuestions);
  };

  const updateSubQuestion = (
    qIndex: number,
    sqIndex: number,
    updates: Partial<ExtractedSubQuestion>
  ) => {
    const newQuestions = [...questions];
    newQuestions[qIndex].sub_questions[sqIndex] = {
      ...newQuestions[qIndex].sub_questions[sqIndex],
      ...updates,
    };
    recalculateTotals(newQuestions);
    onQuestionsChange(newQuestions);
  };

  const updateCriterion = (
    qIndex: number,
    cIndex: number,
    updates: Partial<ExtractedCriterion>,
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
    recalculateTotals(newQuestions);
    onQuestionsChange(newQuestions);
  };

  const addCriterion = (qIndex: number, sqIndex?: number) => {
    const newQuestions = [...questions];
    // Create new enhanced criterion with empty reduction rules
    const newCriterion: ExtractedCriterion = {
      criterion_description: '',
      total_points: 0,
      reduction_rules: [],
      extraction_confidence: 'high',
      notes: null,
      raw_text: null,
    };
    if (sqIndex !== undefined) {
      newQuestions[qIndex].sub_questions[sqIndex].criteria.push(newCriterion);
    } else {
      newQuestions[qIndex].criteria.push(newCriterion);
    }
    onQuestionsChange(newQuestions);
  };

  const removeCriterion = (qIndex: number, cIndex: number, sqIndex?: number) => {
    const newQuestions = [...questions];
    if (sqIndex !== undefined) {
      newQuestions[qIndex].sub_questions[sqIndex].criteria.splice(cIndex, 1);
    } else {
      newQuestions[qIndex].criteria.splice(cIndex, 1);
    }
    recalculateTotals(newQuestions);
    onQuestionsChange(newQuestions);
  };

  const reorderCriteria = (
    qIndex: number,
    fromIndex: number,
    toIndex: number,
    sqIndex?: number
  ) => {
    const newQuestions = [...questions];
    let criteriaArray: ExtractedCriterion[];

    if (sqIndex !== undefined) {
      criteriaArray = [...newQuestions[qIndex].sub_questions[sqIndex].criteria];
    } else {
      criteriaArray = [...newQuestions[qIndex].criteria];
    }

    // Remove the item from original position and insert at new position
    const [movedItem] = criteriaArray.splice(fromIndex, 1);
    criteriaArray.splice(toIndex, 0, movedItem);

    if (sqIndex !== undefined) {
      newQuestions[qIndex].sub_questions[sqIndex].criteria = criteriaArray;
    } else {
      newQuestions[qIndex].criteria = criteriaArray;
    }

    onQuestionsChange(newQuestions);
  };

  const recalculateTotals = (qs: ExtractedQuestion[]) => {
    qs.forEach((q) => {
      if (q.sub_questions.length > 0) {
        q.sub_questions.forEach((sq) => {
          // Use total_points from enhanced format
          sq.total_points = sq.criteria.reduce((sum, c) => sum + (c.total_points || c.points || 0), 0);
        });
        q.total_points = q.sub_questions.reduce((sum, sq) => sum + sq.total_points, 0);
      } else {
        // Use total_points from enhanced format
        q.total_points = q.criteria.reduce((sum, c) => sum + (c.total_points || c.points || 0), 0);
      }
    });
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

  const totalPoints = questions.reduce((sum, q) => sum + q.total_points, 0);
  const totalCriteria = questions.reduce((sum, q) => {
    return sum + q.criteria.length + q.sub_questions.reduce((s, sq) => s + sq.criteria.length, 0);
  }, 0);

  return (
    <div className="space-y-4">
      {/* Summary header */}
      <div className="flex items-center justify-between p-4 bg-primary-50 border border-primary-200 rounded-lg">
        <div>
          <h3 className="font-semibold text-lg text-primary-800">סיכום מחוון</h3>
          <p className="text-sm text-primary-600">
            {questions.length} שאלות · {totalCriteria} קריטריונים · {totalPoints} נקודות
          </p>
        </div>
      </div>

      {/* Questions */}
      <div className="space-y-3">
        {questions.map((question, qIndex) => (
          <div
            key={qIndex}
            className="border border-surface-200 rounded-lg bg-white overflow-hidden shadow-sm"
          >
            {/* Question header */}
            <div
              className="flex items-center justify-between p-4 bg-surface-50 cursor-pointer"
              onClick={() => toggleExpanded(qIndex)}
            >
              <div className="flex items-center gap-3">
                {expandedQuestions.has(qIndex) ? (
                  <ChevronUp size={20} className="text-gray-400" />
                ) : (
                  <ChevronDown size={20} className="text-gray-400" />
                )}
                <div>
                  <span className="font-semibold text-lg">שאלה {question.question_number}</span>
                  <span className="mr-3 text-sm text-gray-500">
                    ({question.total_points} נקודות)
                  </span>
                </div>
              </div>
            </div>

            {/* Question content */}
            {expandedQuestions.has(qIndex) && (
              <div className="p-4 space-y-4 border-t border-surface-200">
                {/* PDF Pages for Question Text */}
                <PdfPagesDisplay
                  pages={pages}
                  pageIndexes={getQuestionPageIndexes(question.question_number)}
                  label="עמודי השאלה במקור"
                />

                {/* Question text */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    טקסט השאלה
                  </label>
                  <textarea
                    value={question.question_text || ''}
                    onChange={(e) => {
                      updateQuestion(qIndex, { question_text: e.target.value });
                      // Auto-resize
                      e.target.style.height = 'auto';
                      e.target.style.height = Math.min(e.target.scrollHeight, 240) + 'px';
                    }}
                    onFocus={(e) => {
                      // Ensure proper height on focus
                      e.target.style.height = 'auto';
                      e.target.style.height = Math.min(e.target.scrollHeight, 240) + 'px';
                    }}
                    ref={(el) => {
                      // Auto-resize on initial render
                      if (el) {
                        el.style.height = 'auto';
                        el.style.height = Math.min(el.scrollHeight, 240) + 'px';
                      }
                    }}
                    className="w-full p-3 border border-surface-300 rounded-lg text-sm resize-none focus:ring-2 focus:ring-primary-300 focus:border-primary-400 overflow-y-auto min-h-[60px] max-h-[240px]"
                    placeholder="טקסט השאלה..."
                    dir="rtl"
                  />
                </div>

                {/* Sub-questions or direct criteria */}
                {question.sub_questions.length > 0 ? (
                  <div className="space-y-4">
                    {question.sub_questions.map((subQ, sqIndex) => (
                      <div
                        key={sqIndex}
                        className="mr-4 border-r-2 border-primary-200 pr-4 space-y-3"
                      >
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-primary-700">
                            סעיף {subQ.sub_question_id}
                          </span>
                          <span className="text-sm text-gray-500">
                            ({subQ.total_points} נקודות)
                          </span>
                        </div>

                        {/* Sub-question text */}
                        <textarea
                          value={subQ.sub_question_text || ''}
                          onChange={(e) => {
                            updateSubQuestion(qIndex, sqIndex, { sub_question_text: e.target.value });
                            // Auto-resize
                            e.target.style.height = 'auto';
                            e.target.style.height = Math.min(e.target.scrollHeight, 180) + 'px';
                          }}
                          onFocus={(e) => {
                            e.target.style.height = 'auto';
                            e.target.style.height = Math.min(e.target.scrollHeight, 180) + 'px';
                          }}
                          ref={(el) => {
                            if (el) {
                              el.style.height = 'auto';
                              el.style.height = Math.min(el.scrollHeight, 180) + 'px';
                            }
                          }}
                          className="w-full p-2 border border-surface-300 rounded-lg text-sm resize-none focus:ring-2 focus:ring-primary-300 overflow-y-auto min-h-[40px] max-h-[180px]"
                          placeholder="טקסט הסעיף..."
                          dir="rtl"
                        />

                        {/* PDF Pages for Sub-question Criteria */}
                        <PdfPagesDisplay
                          pages={pages}
                          pageIndexes={getSubQuestionCriteriaPageIndexes(question.question_number, subQ.sub_question_id)}
                          label="טבלת קריטריונים במקור"
                        />

                        {/* Sub-question criteria */}
                        <CriteriaList
                          criteria={subQ.criteria}
                          onUpdateCriterion={(cIndex, updates) =>
                            updateCriterion(qIndex, cIndex, updates, sqIndex)
                          }
                          onAddCriterion={() => addCriterion(qIndex, sqIndex)}
                          onRemoveCriterion={(cIndex) => removeCriterion(qIndex, cIndex, sqIndex)}
                          onReorderCriteria={(fromIndex, toIndex) => reorderCriteria(qIndex, fromIndex, toIndex, sqIndex)}
                          extractionStatus={subQ.extraction_status}
                          extractionError={subQ.extraction_error}
                        />
                      </div>
                    ))}
                  </div>
                ) : (
                  <>
                    {/* PDF Pages for Direct Criteria */}
                    <PdfPagesDisplay
                      pages={pages}
                      pageIndexes={getCriteriaPageIndexes(question.question_number)}
                      label="טבלת קריטריונים במקור"
                    />

                    {/* Direct criteria */}
                    <CriteriaList
                      criteria={question.criteria}
                      onUpdateCriterion={(cIndex, updates) => updateCriterion(qIndex, cIndex, updates)}
                      onAddCriterion={() => addCriterion(qIndex)}
                      onRemoveCriterion={(cIndex) => removeCriterion(qIndex, cIndex)}
                      onReorderCriteria={(fromIndex, toIndex) => reorderCriteria(qIndex, fromIndex, toIndex)}
                      extractionStatus={question.extraction_status}
                      extractionError={question.extraction_error}
                    />
                  </>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
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
  const scrollContainerRef = useRef<HTMLDivElement>(null);

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
          // Fallback to thumbnail display
          <div className="relative">
            <img
              src={`data:image/png;base64,${relevantPages[currentPageIdx].thumbnail_base64}`}
              alt={`עמוד ${relevantPages[currentPageIdx].page_number}`}
              className="w-full max-h-[320px] object-contain"
            />
            {/* Expand button */}
            <button
              onClick={() => setExpandedPage(currentPageIdx)}
              className="absolute top-2 left-2 p-1.5 bg-white/90 hover:bg-white rounded-lg shadow-md transition-colors"
              title="הגדל"
            >
              <Maximize2 size={16} className="text-gray-600" />
            </button>
            {/* Note about text selection */}
            <div className="absolute bottom-2 right-2 px-2 py-1 bg-amber-100/90 rounded text-xs text-amber-700">
              תצוגה מקדימה - העתקת טקסט לא זמינה
            </div>
          </div>
        )}
      </div>

      {/* Page indicator dots for multiple pages */}
      {hasMultiplePages && (
        <div className="flex items-center justify-center gap-1.5 mt-2">
          {relevantPages.map((_, idx) => (
            <button
              key={idx}
              onClick={() => setCurrentPageIdx(idx)}
              className={`w-2 h-2 rounded-full transition-colors ${idx === currentPageIdx
                ? 'bg-primary-500'
                : 'bg-surface-300 hover:bg-surface-400'
                }`}
            />
          ))}
        </div>
      )}

      {/* Expanded Modal */}
      {expandedPage !== null && (
        <PageExpandedModal
          page={relevantPages[expandedPage]}
          hasPdfUrl={!!relevantPages[expandedPage].page_pdf_url}
          onClose={() => setExpandedPage(null)}
        />
      )}
    </div>
  );
}

// =============================================================================
// Page Expanded Modal Component
// =============================================================================

interface PageExpandedModalProps {
  page: PagePreview;
  hasPdfUrl: boolean;
  onClose: () => void;
}

function PageExpandedModal({ page, hasPdfUrl, onClose }: PageExpandedModalProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
    >
      <div
        className="relative bg-white rounded-xl overflow-hidden max-w-[95vw] max-h-[95vh] shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-3 left-3 z-10 p-2 bg-white/90 hover:bg-white rounded-full shadow-lg transition-colors"
        >
          <X size={20} className="text-gray-600" />
        </button>

        {/* Page number badge */}
        <div className="absolute top-3 right-3 z-10 px-3 py-1 bg-white/90 rounded-full shadow text-sm font-medium text-gray-700">
          עמוד {page.page_number}
        </div>

        {/* Content */}
        {hasPdfUrl && page.page_pdf_url ? (
          <iframe
            src={`${page.page_pdf_url}#toolbar=1&navpanes=0`}
            className="w-[90vw] h-[90vh] border-0"
            title={`עמוד ${page.page_number}`}
          />
        ) : (
          <img
            src={`data:image/png;base64,${page.thumbnail_base64}`}
            alt={`עמוד ${page.page_number}`}
            className="max-w-[90vw] max-h-[90vh] object-contain"
          />
        )}
      </div>
    </div>
  );
}

// =============================================================================
// Editable Reduction Rules Component - Full CRUD Support
// =============================================================================

interface EditableReductionRulesProps {
  rules: ReductionRule[];
  totalPoints: number;
  onRulesChange: (rules: ReductionRule[]) => void;
}

function EditableReductionRules({ rules, totalPoints, onRulesChange }: EditableReductionRulesProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const totalDeduction = rules.reduce((sum, r) => sum + r.reduction_value, 0);
  const hasRules = rules && rules.length > 0;

  // Add a new reduction rule
  const addRule = () => {
    const remainingPoints = Math.max(0, totalPoints - totalDeduction);
    const newRule: ReductionRule = {
      description: '',
      reduction_value: remainingPoints > 0 ? Math.min(1, remainingPoints) : 1,
      is_explicit: false,
    };
    onRulesChange([...rules, newRule]);
    setIsExpanded(true);
  };

  // Update a rule's description or value
  const updateRule = (index: number, updates: Partial<ReductionRule>) => {
    const newRules = [...rules];
    newRules[index] = { ...newRules[index], ...updates };
    onRulesChange(newRules);
  };

  // Delete a rule and redistribute its points to remaining rules
  const deleteRule = (index: number) => {
    const deletedRule = rules[index];
    const remainingRules = rules.filter((_, i) => i !== index);

    if (remainingRules.length === 0) {
      // No rules left - that's fine, criterion has no detailed deduction rules
      onRulesChange([]);
      return;
    }

    // Smart redistribution: distribute deleted points proportionally
    const deletedPoints = deletedRule.reduction_value;
    const currentTotal = remainingRules.reduce((sum, r) => sum + r.reduction_value, 0);

    if (currentTotal > 0 && deletedPoints > 0) {
      // Distribute proportionally based on each rule's share
      const redistributedRules = remainingRules.map(rule => ({
        ...rule,
        reduction_value: Math.round((rule.reduction_value + (rule.reduction_value / currentTotal) * deletedPoints) * 100) / 100
      }));

      // Fix rounding errors - adjust last rule to match total
      const newTotal = redistributedRules.reduce((sum, r) => sum + r.reduction_value, 0);
      const targetTotal = currentTotal + deletedPoints;
      if (Math.abs(newTotal - targetTotal) > 0.01) {
        redistributedRules[redistributedRules.length - 1].reduction_value +=
          Math.round((targetTotal - newTotal) * 100) / 100;
      }

      onRulesChange(redistributedRules);
    } else {
      onRulesChange(remainingRules);
    }
  };

  // Clear all rules
  const clearAllRules = () => {
    onRulesChange([]);
    setIsExpanded(false);
  };

  return (
    <div className="mt-3" dir="rtl">
      {/* Header with expand/collapse and add button */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="group flex items-center gap-2 flex-1 px-3 py-2 rounded-lg bg-gradient-to-l from-slate-50 to-slate-100 hover:from-slate-100 hover:to-slate-150 border border-slate-200 transition-all duration-200"
        >
          <div className="flex items-center gap-2 flex-1">
            {isExpanded ? (
              <ChevronUp size={14} className="text-slate-400 group-hover:text-slate-600 transition-colors" />
            ) : (
              <ChevronDown size={14} className="text-slate-400 group-hover:text-slate-600 transition-colors" />
            )}
            <span className="text-sm font-medium text-slate-600">
              כללי הורדה ({rules.length})
            </span>
          </div>

          {/* Total deduction badge */}
          {hasRules ? (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-gradient-to-l from-red-500 to-rose-500 text-white text-xs font-bold shadow-sm">
              <span>סה״כ</span>
              <span className="font-mono">{totalDeduction}</span>
              <span>נק׳</span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-200 text-slate-500 text-xs font-medium">
              <span>ללא כללים</span>
            </div>
          )}
        </button>

        {/* Add rule button */}
        <button
          onClick={addRule}
          className="p-2 rounded-lg bg-primary-50 hover:bg-primary-100 border border-primary-200 text-primary-600 hover:text-primary-700 transition-colors"
          title="הוסף כלל הורדה"
        >
          <Plus size={14} />
        </button>
      </div>

      {/* Expanded Content - Editable Rules */}
      {isExpanded && (
        <div className="mt-2 rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
          {!hasRules ? (
            // Empty state
            <div className="px-4 py-6 text-center">
              <div className="flex items-center justify-center gap-2 text-slate-400 mb-3">
                <Info size={18} />
                <span className="text-sm">אין כללי הורדה מוגדרים</span>
              </div>
              <p className="text-xs text-slate-400 mb-3">
                ניתן להוסיף כללי הורדה ספציפיים או להשאיר ריק - במקרה זה הקריטריון ייבחן כיחידה אחת
              </p>
              <button
                onClick={addRule}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary-50 hover:bg-primary-100 text-primary-600 text-sm font-medium transition-colors"
              >
                <Plus size={14} />
                <span>הוסף כלל הורדה</span>
              </button>
            </div>
          ) : (
            <div className="p-3 space-y-2">
              {rules.map((rule, idx) => (
                <div
                  key={idx}
                  className={`flex items-center gap-2 p-2.5 rounded-lg border ${rule.is_explicit
                    ? 'bg-red-50 border-red-100'
                    : 'bg-amber-50/70 border-amber-100'
                    }`}
                >
                  {/* Explicit/Inferred indicator */}
                  <div
                    className={`w-2 h-2 rounded-full flex-shrink-0 ${rule.is_explicit ? 'bg-red-500' : 'bg-amber-400'
                      }`}
                    title={rule.is_explicit ? 'מהמחוון המקורי' : 'כלל מוסק'}
                  />

                  {/* Description input */}
                  <input
                    type="text"
                    value={rule.description}
                    onChange={(e) => updateRule(idx, { description: e.target.value })}
                    className="flex-1 bg-transparent border-none outline-none text-sm text-slate-700 placeholder-slate-400"
                    placeholder="תיאור הכלל..."
                    dir="rtl"
                  />

                  {/* Points input */}
                  <div className="flex items-center gap-1 flex-shrink-0">
                    <span className="text-slate-400 text-sm">-</span>
                    <input
                      type="number"
                      value={rule.reduction_value}
                      onChange={(e) => updateRule(idx, { reduction_value: parseFloat(e.target.value) || 0 })}
                      className={`w-14 text-center text-xs font-bold rounded-md px-2 py-1 ${rule.is_explicit
                        ? 'bg-red-500 text-white'
                        : 'bg-amber-400 text-amber-900'
                        }`}
                      min={0}
                      step={0.5}
                    />
                  </div>

                  {/* Delete button */}
                  <button
                    onClick={() => deleteRule(idx)}
                    className="p-1 text-slate-400 hover:text-red-500 transition-colors flex-shrink-0"
                    title="מחק כלל"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}

              {/* Footer actions */}
              <div className="flex items-center justify-between pt-2 border-t border-slate-100">
                <button
                  onClick={addRule}
                  className="inline-flex items-center gap-1 text-xs text-primary-600 hover:text-primary-700"
                >
                  <Plus size={12} />
                  <span>הוסף כלל</span>
                </button>

                {/* Warning if rules don't sum to total */}
                {hasRules && Math.abs(totalDeduction - totalPoints) > 0.01 && (
                  <div className="flex items-center gap-1 text-xs text-amber-600">
                    <AlertTriangle size={12} />
                    <span>סה״כ ({totalDeduction}) ≠ נקודות ({totalPoints})</span>
                  </div>
                )}

                <button
                  onClick={clearAllRules}
                  className="text-xs text-slate-400 hover:text-red-500"
                >
                  נקה הכל
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Criteria List Component
// =============================================================================

interface CriteriaListProps {
  criteria: ExtractedCriterion[];
  onUpdateCriterion: (index: number, updates: Partial<ExtractedCriterion>) => void;
  onAddCriterion: () => void;
  onRemoveCriterion: (index: number) => void;
  onReorderCriteria: (fromIndex: number, toIndex: number) => void;
  // Extraction status for showing warnings
  extractionStatus?: 'success' | 'partial' | 'failed';
  extractionError?: string | null;
}

function CriteriaList({
  criteria,
  onUpdateCriterion,
  onAddCriterion,
  onRemoveCriterion,
  onReorderCriteria,
  extractionStatus = 'success',
  extractionError,
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
            // Get display values (support both old and new format)
            const displayDescription = criterion.criterion_description || criterion.description || '';
            const displayPoints = criterion.total_points ?? criterion.points ?? 0;

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
                        criterion_description: e.target.value,
                        description: e.target.value
                      })}
                      className="flex-1 bg-transparent border-none outline-none text-sm text-right"
                      placeholder="תיאור הקריטריון..."
                      dir="rtl"
                      style={{ unicodeBidi: 'plaintext' }}
                    />

                    <input
                      type="number"
                      value={displayPoints}
                      onChange={(e) => {
                        const value = parseFloat(e.target.value) || 0;
                        onUpdateCriterion(cIndex, {
                          total_points: value,
                          points: value
                        });
                      }}
                      className="w-16 text-center bg-white border border-surface-300 rounded px-2 py-1 text-sm font-medium"
                      min={0}
                      step={0.5}
                    />

                    <button
                      onClick={() => onRemoveCriterion(cIndex)}
                      className="text-red-400 hover:text-red-600 p-1"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>

                  {/* Reduction rules section (always shown so teachers can add/edit) */}
                  <EditableReductionRules
                    rules={criterion.reduction_rules || []}
                    totalPoints={displayPoints}
                    onRulesChange={(newRules) => onUpdateCriterion(cIndex, { reduction_rules: newRules })}
                  />
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
    </div>
  );
}