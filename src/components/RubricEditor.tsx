'use client';

import { useState } from 'react';
import { ExtractedQuestion, ExtractedSubQuestion, ExtractedCriterion } from '@/lib/api';
import { Plus, Trash2, ChevronDown, ChevronUp, GripVertical, AlertCircle } from 'lucide-react';

interface RubricEditorProps {
  questions: ExtractedQuestion[];
  onQuestionsChange: (questions: ExtractedQuestion[]) => void;
}

export function RubricEditor({ questions, onQuestionsChange }: RubricEditorProps) {
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
                {/* Question text */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    טקסט השאלה
                  </label>
                  <textarea
                    value={question.question_text || ''}
                    onChange={(e) => updateQuestion(qIndex, { question_text: e.target.value })}
                    className="w-full p-3 border border-surface-300 rounded-lg text-sm resize-none focus:ring-2 focus:ring-primary-300 focus:border-primary-400"
                    rows={3}
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
                          onChange={(e) =>
                            updateSubQuestion(qIndex, sqIndex, { sub_question_text: e.target.value })
                          }
                          className="w-full p-2 border border-surface-300 rounded-lg text-sm resize-none focus:ring-2 focus:ring-primary-300"
                          rows={2}
                          placeholder="טקסט הסעיף..."
                          dir="rtl"
                        />

                        {/* Sub-question criteria */}
                        <CriteriaList
                          criteria={subQ.criteria}
                          onUpdateCriterion={(cIndex, updates) =>
                            updateCriterion(qIndex, cIndex, updates, sqIndex)
                          }
                          onAddCriterion={() => addCriterion(qIndex, sqIndex)}
                          onRemoveCriterion={(cIndex) => removeCriterion(qIndex, cIndex, sqIndex)}
                        />
                      </div>
                    ))}
                  </div>
                ) : (
                  /* Direct criteria */
                  <CriteriaList
                    criteria={question.criteria}
                    onUpdateCriterion={(cIndex, updates) => updateCriterion(qIndex, cIndex, updates)}
                    onAddCriterion={() => addCriterion(qIndex)}
                    onRemoveCriterion={(cIndex) => removeCriterion(qIndex, cIndex)}
                  />
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
// Criteria List Component
// =============================================================================

interface CriteriaListProps {
  criteria: ExtractedCriterion[];
  onUpdateCriterion: (index: number, updates: Partial<ExtractedCriterion>) => void;
  onAddCriterion: () => void;
  onRemoveCriterion: (index: number) => void;
}

function CriteriaList({
  criteria,
  onUpdateCriterion,
  onAddCriterion,
  onRemoveCriterion,
}: CriteriaListProps) {
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
          אין קריטריונים. לחץ על "הוסף קריטריון" כדי להוסיף.
        </div>
      ) : (
        <div className="space-y-2">
          {criteria.map((criterion, cIndex) => (
            <div
              key={cIndex}
              className={`flex items-center gap-2 p-2 bg-surface-50 rounded-lg border ${
                criterion.extraction_confidence === 'low'
                  ? 'border-amber-300 bg-amber-50'
                  : criterion.extraction_confidence === 'medium'
                  ? 'border-yellow-200 bg-yellow-50'
                  : 'border-surface-200'
              }`}
            >
              <GripVertical size={16} className="text-gray-300 cursor-grab" />
              
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
          ))}
        </div>
      )}
    </div>
  );
}
