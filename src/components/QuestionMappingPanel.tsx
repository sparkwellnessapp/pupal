'use client';

import { useState } from 'react';
import { QuestionPageMapping, SubQuestionPageMapping } from '@/lib/api';
import { Plus, Trash2, ChevronDown, ChevronUp, FileText, Table } from 'lucide-react';

interface QuestionMappingPanelProps {
  mappings: QuestionPageMapping[];
  onMappingsChange: (mappings: QuestionPageMapping[]) => void;
  activeAssignment: {
    questionIndex: number;
    type: 'question' | 'criteria' | 'sub_question_criteria';
    subQuestionId?: string;
  } | null;
  onSetActiveAssignment: (assignment: QuestionMappingPanelProps['activeAssignment']) => void;
}

const SUB_QUESTION_IDS = ['א', 'ב', 'ג', 'ד', 'ה', 'ו', 'ז', 'ח', 'ט', 'י'];

export function QuestionMappingPanel({
  mappings,
  onMappingsChange,
  activeAssignment,
  onSetActiveAssignment,
}: QuestionMappingPanelProps) {
  const [expandedQuestions, setExpandedQuestions] = useState<Set<number>>(new Set([0]));

  const toggleExpanded = (index: number) => {
    const newExpanded = new Set(expandedQuestions);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedQuestions(newExpanded);
  };

  const addQuestion = () => {
    const newQuestionNumber = mappings.length + 1;
    onMappingsChange([
      ...mappings,
      {
        question_number: newQuestionNumber,
        question_page_indexes: [],
        criteria_page_indexes: [],
        sub_questions: [],
      },
    ]);
    setExpandedQuestions(new Set([...expandedQuestions, mappings.length]));
  };

  const removeQuestion = (index: number) => {
    const newMappings = mappings.filter((_, i) => i !== index);
    // Renumber questions
    newMappings.forEach((m, i) => {
      m.question_number = i + 1;
    });
    onMappingsChange(newMappings);
  };

  const addSubQuestion = (questionIndex: number) => {
    const newMappings = [...mappings];
    const question = newMappings[questionIndex];
    const nextId = SUB_QUESTION_IDS[question.sub_questions.length] || `${question.sub_questions.length + 1}`;
    question.sub_questions.push({
      sub_question_id: nextId,
      sub_question_page_indexes: [],
      criteria_page_indexes: [],
    });
    // Clear direct criteria when adding sub-questions
    question.criteria_page_indexes = [];
    onMappingsChange(newMappings);
  };

  const removeSubQuestion = (questionIndex: number, subIndex: number) => {
    const newMappings = [...mappings];
    newMappings[questionIndex].sub_questions.splice(subIndex, 1);
    onMappingsChange(newMappings);
  };

  const isAssignmentActive = (
    questionIndex: number,
    type: 'question' | 'criteria' | 'sub_question_criteria',
    subQuestionId?: string
  ) => {
    if (!activeAssignment) return false;
    return (
      activeAssignment.questionIndex === questionIndex &&
      activeAssignment.type === type &&
      activeAssignment.subQuestionId === subQuestionId
    );
  };

  const getButtonStyle = (
    questionIndex: number,
    type: 'question' | 'criteria' | 'sub_question_criteria',
    subQuestionId?: string
  ) => {
    const isActive = isAssignmentActive(questionIndex, type, subQuestionId);
    if (isActive) {
      return 'bg-primary-500 text-white border-primary-500';
    }
    return 'bg-white text-gray-700 border-surface-300 hover:border-primary-400 hover:bg-primary-50';
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-lg">מיפוי שאלות</h3>
        <button
          onClick={addQuestion}
          className="flex items-center gap-1 text-sm bg-primary-500 text-white px-3 py-1.5 rounded-lg hover:bg-primary-600 transition-colors"
        >
          <Plus size={16} />
          הוסף שאלה
        </button>
      </div>

      {mappings.length === 0 ? (
        <div className="text-center py-8 text-gray-500 bg-surface-100 rounded-lg">
          <p>לחץ על "הוסף שאלה" כדי להתחיל</p>
        </div>
      ) : (
        <div className="space-y-2">
          {mappings.map((mapping, qIndex) => (
            <div
              key={qIndex}
              className="border border-surface-200 rounded-lg bg-white overflow-hidden"
            >
              {/* Question header */}
              <div
                className="flex items-center justify-between p-3 bg-surface-50 cursor-pointer"
                onClick={() => toggleExpanded(qIndex)}
              >
                <div className="flex items-center gap-2">
                  {expandedQuestions.has(qIndex) ? (
                    <ChevronUp size={18} className="text-gray-400" />
                  ) : (
                    <ChevronDown size={18} className="text-gray-400" />
                  )}
                  <span className="font-medium">שאלה {mapping.question_number}</span>
                  <span className="text-xs text-gray-500">
                    ({mapping.question_page_indexes.length} עמודי שאלה,{' '}
                    {mapping.sub_questions.length > 0
                      ? `${mapping.sub_questions.length} סעיפים`
                      : `${mapping.criteria_page_indexes.length} עמודי מחוון`}
                    )
                  </span>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    removeQuestion(qIndex);
                  }}
                  className="text-red-500 hover:text-red-700 p-1"
                >
                  <Trash2 size={16} />
                </button>
              </div>

              {/* Question content */}
              {expandedQuestions.has(qIndex) && (
                <div className="p-3 space-y-3 border-t border-surface-200">
                  {/* Question pages assignment */}
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() =>
                        onSetActiveAssignment(
                          isAssignmentActive(qIndex, 'question')
                            ? null
                            : { questionIndex: qIndex, type: 'question' }
                        )
                      }
                      className={`flex items-center gap-1.5 px-3 py-1.5 text-sm border rounded-lg transition-colors ${getButtonStyle(qIndex, 'question')}`}
                    >
                      <FileText size={14} />
                      עמודי שאלה
                    </button>
                    <span className="text-xs text-gray-500">
                      {mapping.question_page_indexes.length > 0
                        ? `עמודים: ${mapping.question_page_indexes.map((p) => p + 1).join(', ')}`
                        : 'לא נבחרו עמודים'}
                    </span>
                  </div>

                  {/* Sub-questions or direct criteria */}
                  {mapping.sub_questions.length === 0 ? (
                    <>
                      {/* Direct criteria pages */}
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() =>
                            onSetActiveAssignment(
                              isAssignmentActive(qIndex, 'criteria')
                                ? null
                                : { questionIndex: qIndex, type: 'criteria' }
                            )
                          }
                          className={`flex items-center gap-1.5 px-3 py-1.5 text-sm border rounded-lg transition-colors ${getButtonStyle(qIndex, 'criteria')}`}
                        >
                          <Table size={14} />
                          עמודי מחוון
                        </button>
                        <span className="text-xs text-gray-500">
                          {mapping.criteria_page_indexes.length > 0
                            ? `עמודים: ${mapping.criteria_page_indexes.map((p) => p + 1).join(', ')}`
                            : 'לא נבחרו עמודים'}
                        </span>
                      </div>
                      <button
                        onClick={() => addSubQuestion(qIndex)}
                        className="text-sm text-primary-600 hover:text-primary-700 flex items-center gap-1"
                      >
                        <Plus size={14} />
                        הוסף תת-שאלות (א, ב, ג...)
                      </button>
                    </>
                  ) : (
                    <>
                      {/* Sub-questions list */}
                      <div className="space-y-2 mr-4 border-r-2 border-surface-200 pr-3">
                        {mapping.sub_questions.map((subQ, sIndex) => (
                          <div key={sIndex} className="flex items-center gap-2">
                            <span className="font-medium text-sm w-6">{subQ.sub_question_id}.</span>
                            <button
                              onClick={() =>
                                onSetActiveAssignment(
                                  isAssignmentActive(qIndex, 'sub_question_criteria', subQ.sub_question_id)
                                    ? null
                                    : {
                                        questionIndex: qIndex,
                                        type: 'sub_question_criteria',
                                        subQuestionId: subQ.sub_question_id,
                                      }
                                )
                              }
                              className={`flex items-center gap-1.5 px-2 py-1 text-xs border rounded transition-colors ${getButtonStyle(qIndex, 'sub_question_criteria', subQ.sub_question_id)}`}
                            >
                              <Table size={12} />
                              מחוון
                            </button>
                            <span className="text-xs text-gray-500 flex-1">
                              {subQ.criteria_page_indexes.length > 0
                                ? `עמודים: ${subQ.criteria_page_indexes.map((p) => p + 1).join(', ')}`
                                : 'לא נבחרו'}
                            </span>
                            <button
                              onClick={() => removeSubQuestion(qIndex, sIndex)}
                              className="text-red-400 hover:text-red-600 p-0.5"
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        ))}
                      </div>
                      <button
                        onClick={() => addSubQuestion(qIndex)}
                        className="text-sm text-primary-600 hover:text-primary-700 flex items-center gap-1 mr-4"
                      >
                        <Plus size={14} />
                        הוסף סעיף
                      </button>
                    </>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Active assignment indicator */}
      {activeAssignment && (
        <div className="mt-4 p-3 bg-primary-50 border border-primary-200 rounded-lg text-sm text-primary-700">
          <span className="font-medium">מצב בחירה פעיל: </span>
          {activeAssignment.type === 'question' && `בחר עמודי שאלה ${mappings[activeAssignment.questionIndex]?.question_number}`}
          {activeAssignment.type === 'criteria' && `בחר עמודי מחוון לשאלה ${mappings[activeAssignment.questionIndex]?.question_number}`}
          {activeAssignment.type === 'sub_question_criteria' &&
            `בחר עמודי מחוון לסעיף ${activeAssignment.subQuestionId} בשאלה ${mappings[activeAssignment.questionIndex]?.question_number}`}
          <br />
          <span className="text-xs">לחץ על עמודים בצד שמאל כדי להוסיף/להסיר</span>
        </div>
      )}
    </div>
  );
}
