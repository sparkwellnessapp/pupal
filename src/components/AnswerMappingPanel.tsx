'use client';

import { useState } from 'react';
import { AnswerPageMapping, RubricListItem } from '@/lib/api';
import { Plus, Trash2, ChevronDown, ChevronUp, Code, FileText } from 'lucide-react';

interface AnswerMappingPanelProps {
  rubric: RubricListItem;
  mappings: AnswerPageMapping[];
  onMappingsChange: (mappings: AnswerPageMapping[]) => void;
  activeAssignment: {
    mappingIndex: number;
  } | null;
  onSetActiveAssignment: (assignment: AnswerMappingPanelProps['activeAssignment']) => void;
  firstPageIndex: number;
  onFirstPageIndexChange: (index: number) => void;
  hideFirstPageSelector?: boolean;
}

export function AnswerMappingPanel({
  rubric,
  mappings,
  onMappingsChange,
  activeAssignment,
  onSetActiveAssignment,
  firstPageIndex,
  onFirstPageIndexChange,
  hideFirstPageSelector = false,
}: AnswerMappingPanelProps) {
  // Initialize mappings from rubric structure if empty
  const initializeMappings = () => {
    const newMappings: AnswerPageMapping[] = [];

    for (const question of rubric.rubric_json.questions) {
      if (question.sub_questions && question.sub_questions.length > 0) {
        // Question has sub-questions
        for (const sq of question.sub_questions) {
          newMappings.push({
            question_number: question.question_number,
            sub_question_id: sq.sub_question_id,
            page_indexes: [],
          });
        }
      } else {
        // Question without sub-questions
        newMappings.push({
          question_number: question.question_number,
          sub_question_id: null,
          page_indexes: [],
        });
      }
    }

    onMappingsChange(newMappings);
  };

  const isAssignmentActive = (mappingIndex: number) => {
    return activeAssignment?.mappingIndex === mappingIndex;
  };

  const getButtonStyle = (mappingIndex: number) => {
    const isActive = isAssignmentActive(mappingIndex);
    if (isActive) {
      return 'bg-green-500 text-white border-green-500';
    }
    return 'bg-white text-gray-700 border-surface-300 hover:border-green-400 hover:bg-green-50';
  };

  const getMappingLabel = (mapping: AnswerPageMapping) => {
    if (mapping.sub_question_id) {
      return `תשובה ${mapping.question_number} סעיף ${mapping.sub_question_id}`;
    }
    return `תשובה ${mapping.question_number}`;
  };

  const getQuestionPoints = (mapping: AnswerPageMapping) => {
    const question = rubric.rubric_json.questions.find(
      (q) => q.question_number === mapping.question_number
    );
    if (!question) return 0;

    if (mapping.sub_question_id && question.sub_questions) {
      const sq = question.sub_questions.find(
        (s) => s.sub_question_id === mapping.sub_question_id
      );
      return sq?.criteria?.reduce((sum, c) => sum + c.points, 0) || 0;
    }

    return question.total_points || 0;
  };

  if (mappings.length === 0) {
    return (
      <div className="space-y-4">
        <h3 className="font-semibold text-lg">מיפוי תשובות</h3>
        <div className="text-center py-8 bg-surface-100 rounded-lg">
          <p className="text-gray-500 mb-4">
            המחוון מכיל {rubric.rubric_json.questions.length} שאלות
          </p>
          <button
            onClick={initializeMappings}
            className="flex items-center gap-2 mx-auto bg-green-500 text-white px-4 py-2 rounded-lg hover:bg-green-600 transition-colors"
          >
            <Plus size={18} />
            צור מיפוי מהמחוון
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-lg">מיפוי תשובות</h3>
        <span className="text-sm text-gray-500">
          {mappings.length} שאלות/סעיפים
        </span>
      </div>

      {/* First page (student name) selector - only show if not hidden */}
      {!hideFirstPageSelector && (
        <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-center gap-2 text-sm">
            <FileText size={16} className="text-blue-500" />
            <span className="font-medium text-blue-700">עמוד שם התלמיד:</span>
            <select
              value={firstPageIndex}
              onChange={(e) => onFirstPageIndexChange(parseInt(e.target.value))}
              className="bg-white border border-blue-300 rounded px-2 py-1 text-sm"
            >
              {[...Array(10)].map((_, i) => (
                <option key={i} value={i}>
                  עמוד {i + 1}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}

      {/* Answer mappings */}
      <div className="space-y-2">
        {mappings.map((mapping, index) => (
          <div
            key={index}
            className={`flex items-center gap-3 p-3 rounded-lg border transition-all ${isAssignmentActive(index)
                ? 'bg-green-50 border-green-300'
                : 'bg-white border-surface-200'
              }`}
          >
            <button
              onClick={() =>
                onSetActiveAssignment(
                  isAssignmentActive(index) ? null : { mappingIndex: index }
                )
              }
              className={`flex items-center gap-2 px-3 py-1.5 text-sm border rounded-lg transition-colors ${getButtonStyle(index)}`}
            >
              <Code size={14} />
              {getMappingLabel(mapping)}
            </button>

            <span className="text-xs text-gray-400">
              ({getQuestionPoints(mapping)} נק׳)
            </span>

            <span className="flex-1 text-xs text-gray-500">
              {mapping.page_indexes.length > 0
                ? `עמודים: ${mapping.page_indexes.map((p) => p + 1).join(', ')}`
                : 'לחץ ובחר עמודים'}
            </span>
          </div>
        ))}
      </div>

      {/* Active assignment indicator */}
      {activeAssignment && (
        <div className="p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700">
          <span className="font-medium">מצב בחירה פעיל: </span>
          {getMappingLabel(mappings[activeAssignment.mappingIndex])}
          <br />
          <span className="text-xs">לחץ על עמודים משמאל כדי להוסיף/להסיר</span>
        </div>
      )}

      {/* Validation */}
      {mappings.some((m) => m.page_indexes.length === 0) && (
        <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-700">
          ⚠️ יש שאלות ללא עמודים מוגדרים
        </div>
      )}
    </div>
  );
}
