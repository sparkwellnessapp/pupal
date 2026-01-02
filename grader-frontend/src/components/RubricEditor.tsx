'use client';

import { useState, useRef } from 'react';
import { ExtractedQuestion, ExtractedSubQuestion, ExtractedCriterion, PagePreview, QuestionPageMapping } from '@/lib/api';
import { Plus, Trash2, ChevronDown, ChevronUp, GripVertical, AlertCircle, FileText, ChevronLeft, ChevronRight, Maximize2, X } from 'lucide-react';

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
    const newCriterion: ExtractedCriterion = {
      description: '',
      points: 0,
      extraction_confidence: 'high',
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
          sq.total_points = sq.criteria.reduce((sum, c) => sum + c.points, 0);
        });
        q.total_points = q.sub_questions.reduce((sum, sq) => sum + sq.total_points, 0);
      } else {
        q.total_points = q.criteria.reduce((sum, c) => sum + c.points, 0);
      }
    });
  };

  // Get page indexes for a question's text
  const getQuestionPageIndexes = (questionNumber: number): number[] => {
    if (!questionMappings) return [];
    const mapping = questionMappings.find(m => m.question_number === questionNumber);
    return mapping?.question_page_indexes || [];
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
// Criteria List Component
// =============================================================================

interface CriteriaListProps {
  criteria: ExtractedCriterion[];
  onUpdateCriterion: (index: number, updates: Partial<ExtractedCriterion>) => void;
  onAddCriterion: () => void;
  onRemoveCriterion: (index: number) => void;
  onReorderCriteria: (fromIndex: number, toIndex: number) => void;
}

function CriteriaList({
  criteria,
  onUpdateCriterion,
  onAddCriterion,
  onRemoveCriterion,
  onReorderCriteria,
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

      {criteria.length === 0 ? (
        <div className="text-center py-4 text-gray-400 text-sm bg-surface-50 rounded-lg">
          אין קריטריונים. לחץ על &quot;הוסף קריטריון&quot; כדי להוסיף.
        </div>
      ) : (
        <div className="space-y-0">
          {criteria.map((criterion, cIndex) => {
            const dropIndicator = getDropIndicator(cIndex);
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
                  className={`flex items-center gap-2 p-2 my-1 bg-surface-50 rounded-lg border transition-all duration-150 ${criterion.extraction_confidence === 'low'
                    ? 'border-amber-300 bg-amber-50'
                    : criterion.extraction_confidence === 'medium'
                      ? 'border-yellow-200 bg-yellow-50'
                      : 'border-surface-200'
                    } ${draggedIndex === cIndex ? 'opacity-40 scale-[0.98]' : ''
                    }`}
                >
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
                    value={criterion.description}
                    onChange={(e) => onUpdateCriterion(cIndex, { description: e.target.value })}
                    className="flex-1 bg-transparent border-none outline-none text-sm"
                    placeholder="תיאור הקריטריון..."
                    dir="rtl"
                  />

                  <input
                    type="number"
                    value={criterion.points}
                    onChange={(e) => onUpdateCriterion(cIndex, { points: parseFloat(e.target.value) || 0 })}
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