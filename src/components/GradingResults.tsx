'use client';

import { useState } from 'react';
import { GradedTestResult, StudentAnswer, PagePreview } from '@/lib/api';
import {
  ChevronDown,
  ChevronUp,
  CheckCircle,
  XCircle,
  AlertCircle,
  User,
  FileText,
  Code,
} from 'lucide-react';

interface GradingResultsProps {
  results: GradedTestResult[];
  stats: {
    total: number;
    successful: number;
    failed: number;
    errors: string[];
  };
  onBack: () => void;
  // Optional: PDF page thumbnails keyed by filename for handwritten test validation
  testPages?: Map<string, PagePreview[]>;
}

interface QuestionGrade {
  question_number: number;
  grades: Grade[];
}

interface Grade {
  criterion_index?: number;
  criterion: string;
  mark: string;
  points_earned: number;
  points_possible: number;
  explanation?: string;
  confidence: string;
  low_confidence_reason?: string;
  question_number?: number;
  sub_question_id?: string;
}

export function GradingResults({
  results,
  stats,
  onBack,
  testPages,
}: GradingResultsProps) {
  const { total: totalTests, successful, failed, errors } = stats;
  const [expandedTests, setExpandedTests] = useState<Set<string>>(new Set());
  const [expandedQuestions, setExpandedQuestions] = useState<Set<string>>(new Set());
  // Changed: track COLLAPSED code sections instead of expanded (so default = shown)
  const [collapsedCode, setCollapsedCode] = useState<Set<string>>(new Set());

  const toggleExpanded = (testId: string) => {
    const newExpanded = new Set(Array.from(expandedTests));
    if (newExpanded.has(testId)) {
      newExpanded.delete(testId);
    } else {
      newExpanded.add(testId);
    }
    setExpandedTests(newExpanded);
  };

  const toggleQuestion = (key: string) => {
    const newExpanded = new Set(Array.from(expandedQuestions));
    if (newExpanded.has(key)) {
      newExpanded.delete(key);
    } else {
      newExpanded.add(key);
    }
    setExpandedQuestions(newExpanded);
  };

  const toggleCode = (key: string) => {
    // Changed: toggle in collapsedCode set (inverted logic)
    const newCollapsed = new Set(Array.from(collapsedCode));
    if (newCollapsed.has(key)) {
      newCollapsed.delete(key);
    } else {
      newCollapsed.add(key);
    }
    setCollapsedCode(newCollapsed);
  };

  const getScoreColor = (percentage: number) => {
    if (percentage >= 80) return 'text-green-600 bg-green-50';
    if (percentage >= 60) return 'text-yellow-600 bg-yellow-50';
    return 'text-red-600 bg-red-50';
  };

  const getScoreBorderColor = (percentage: number) => {
    if (percentage >= 80) return 'border-green-200';
    if (percentage >= 60) return 'border-yellow-200';
    return 'border-red-200';
  };

  const getMarkIcon = (mark: string) => {
    if (mark === '✓' || mark === 'V' || mark === '✔') {
      return <CheckCircle size={16} className="text-green-500" />;
    }
    if (mark === '✗' || mark === 'X' || mark === '✘') {
      return <XCircle size={16} className="text-red-500" />;
    }
    return <AlertCircle size={16} className="text-yellow-500" />;
  };

  // Get all answers for a question (including sub-questions)
  const getQuestionAnswers = (
    result: GradedTestResult,
    questionNumber: number
  ): StudentAnswer[] => {
    if (!result.student_answers_json?.answers) return [];

    return result.student_answers_json.answers.filter(
      (a: StudentAnswer) => a.question_number === questionNumber
    );
  };

  // Group grades by question if not already grouped
  const getQuestionGrades = (result: GradedTestResult): QuestionGrade[] => {
    // Check if already grouped (new format)
    if (result.graded_json.question_grades && result.graded_json.question_grades.length > 0) {
      return result.graded_json.question_grades;
    }

    // Fall back to flat grades list (old format) - group by question_number
    const grades = result.graded_json.grades || [];
    const grouped: { [key: number]: Grade[] } = {};

    grades.forEach((grade: Grade) => {
      const qNum = grade.question_number || 0;
      if (!grouped[qNum]) {
        grouped[qNum] = [];
      }
      grouped[qNum].push(grade);
    });

    return Object.entries(grouped)
      .map(([qNum, qGrades]) => ({
        question_number: parseInt(qNum),
        grades: qGrades
      }))
      .sort((a, b) => a.question_number - b.question_number);
  };

  // Calculate question score
  const getQuestionScore = (grades: Grade[]) => {
    const earned = grades.reduce((sum, g) => sum + (g.points_earned || 0), 0);
    const possible = grades.reduce((sum, g) => sum + (g.points_possible || 0), 0);
    return { earned, possible, percentage: possible > 0 ? (earned / possible * 100) : 0 };
  };

  // Calculate statistics
  const avgScore = results.length > 0
    ? results.reduce((sum, r) => sum + r.percentage, 0) / results.length
    : 0;

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-white rounded-xl p-4 border border-surface-200 shadow-sm">
          <div className="text-2xl font-bold text-gray-800">{totalTests}</div>
          <div className="text-sm text-gray-500">סה״כ מבחנים</div>
        </div>
        <div className="bg-green-50 rounded-xl p-4 border border-green-200">
          <div className="text-2xl font-bold text-green-600">{successful}</div>
          <div className="text-sm text-green-600">נבדקו בהצלחה</div>
        </div>
        <div className="bg-red-50 rounded-xl p-4 border border-red-200">
          <div className="text-2xl font-bold text-red-600">{failed}</div>
          <div className="text-sm text-red-600">נכשלו</div>
        </div>
        <div className="bg-blue-50 rounded-xl p-4 border border-blue-200">
          <div className="text-2xl font-bold text-blue-600">{avgScore.toFixed(1)}%</div>
          <div className="text-sm text-blue-600">ממוצע</div>
        </div>
      </div>

      {/* Errors */}
      {errors.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <h4 className="font-medium text-red-700 mb-2">שגיאות:</h4>
          <ul className="list-disc list-inside text-sm text-red-600 space-y-1">
            {errors.map((error, i) => (
              <li key={i}>{error}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Results List */}
      <div className="space-y-3">
        <h3 className="font-semibold text-lg">תוצאות מפורטות</h3>

        {results.length === 0 ? (
          <div className="text-center py-8 text-gray-500 bg-surface-50 rounded-lg">
            אין תוצאות להצגה
          </div>
        ) : (
          results
            .sort((a, b) => b.percentage - a.percentage)
            .map((result) => {
              const questionGrades = getQuestionGrades(result);

              return (
                <div
                  key={result.id}
                  className="bg-white rounded-xl border border-surface-200 shadow-sm overflow-hidden"
                >
                  {/* Header */}
                  <div
                    className="flex items-center justify-between p-4 cursor-pointer hover:bg-surface-50 transition-colors"
                    onClick={() => toggleExpanded(result.id)}
                  >
                    <div className="flex items-center gap-4">
                      {expandedTests.has(result.id) ? (
                        <ChevronUp size={20} className="text-gray-400" />
                      ) : (
                        <ChevronDown size={20} className="text-gray-400" />
                      )}

                      <div className="flex items-center gap-2">
                        <User size={18} className="text-gray-400" />
                        <span className="font-medium">{result.student_name}</span>
                      </div>

                      {result.filename && (
                        <div className="flex items-center gap-1 text-xs text-gray-400">
                          <FileText size={14} />
                          <span className="truncate max-w-[200px]">{result.filename}</span>
                        </div>
                      )}

                      {/* Mismatch Warning Badge - visible in header */}
                      {result.graded_json.rubric_mismatch_detected && (
                        <div className="flex items-center gap-1 px-2 py-1 bg-orange-100 border border-orange-300 rounded-md text-orange-700 text-xs font-medium">
                          <AlertCircle size={14} />
                          <span>חוסר התאמה!</span>
                        </div>
                      )}
                    </div>

                    <div className="flex items-center gap-4">
                      <div className="text-sm text-gray-500">
                        {result.total_score}/{result.total_possible}
                      </div>
                      <div className={`px-3 py-1 rounded-full text-sm font-medium ${getScoreColor(result.percentage)}`}>
                        {result.percentage.toFixed(1)}%
                      </div>
                    </div>
                  </div>

                  {/* Expanded Details */}
                  {expandedTests.has(result.id) && (
                    <div className="border-t border-surface-200 p-4 bg-surface-50">
                      {result.graded_json.low_confidence_items && result.graded_json.low_confidence_items.length > 0 && (
                        <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                          <h5 className="font-medium text-amber-700 text-sm mb-1">
                            ⚠️ פריטים לבדיקה ידנית:
                          </h5>
                          <ul className="text-xs text-amber-600 space-y-1">
                            {result.graded_json.low_confidence_items.map((item: string, i: number) => (
                              <li key={i}>• {item}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Rubric Mismatch Warning */}
                      {result.graded_json.rubric_mismatch_detected && (
                        <div className="mb-4 p-3 bg-orange-50 border border-orange-300 rounded-lg">
                          <h5 className="font-medium text-orange-700 text-sm mb-1 flex items-center gap-2">
                            <AlertCircle size={16} />
                            אזהרה: חוסר התאמה בין המחוון לתשובות
                          </h5>
                          <p className="text-xs text-orange-600">
                            {result.graded_json.rubric_mismatch_reason ||
                              'נראה שהתשובות לא תואמות למחוון שנבחר. אנא וודאו שנבחר המחוון הנכון.'}
                          </p>
                        </div>
                      )}

                      {/* Handwritten Pages Gallery */}
                      {testPages && result.filename && testPages.get(result.filename) && (
                        <HandwrittenPagesGallery pages={testPages.get(result.filename)!} />
                      )}

                      {/* Question-grouped grades */}
                      <div className="space-y-3">
                        {questionGrades.map((qg) => {
                          const qScore = getQuestionScore(qg.grades);
                          const qKey = `${result.id}-q${qg.question_number}`;
                          const codeKey = `${result.id}-code${qg.question_number}`;
                          const isExpanded = expandedQuestions.has(qKey);
                          // Changed: code is shown by default (when NOT in collapsedCode set)
                          const isCodeExpanded = !collapsedCode.has(codeKey);
                          const questionAnswers = getQuestionAnswers(result, qg.question_number);

                          return (
                            <div
                              key={qKey}
                              className={`bg-white rounded-lg border ${getScoreBorderColor(qScore.percentage)} overflow-hidden`}
                            >
                              {/* Question header */}
                              <div
                                className="flex items-center justify-between p-3 cursor-pointer hover:bg-surface-50"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  toggleQuestion(qKey);
                                }}
                              >
                                <div className="flex items-center gap-3">
                                  {isExpanded ? (
                                    <ChevronUp size={16} className="text-gray-400" />
                                  ) : (
                                    <ChevronDown size={16} className="text-gray-400" />
                                  )}
                                  <span className="font-medium text-gray-700">
                                    שאלה {qg.question_number}
                                  </span>
                                  <span className="text-xs text-gray-400">
                                    ({qg.grades.length} קריטריונים)
                                  </span>
                                </div>
                                <div className="flex items-center gap-3">
                                  <span className="text-sm text-gray-500">
                                    {qScore.earned.toFixed(1)}/{qScore.possible.toFixed(1)}
                                  </span>
                                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${getScoreColor(qScore.percentage)}`}>
                                    {qScore.percentage.toFixed(0)}%
                                  </span>
                                </div>
                              </div>

                              {/* Expanded question content */}
                              {isExpanded && (
                                <div className="border-t border-surface-100">
                                  {/* Student Code Section */}
                                  {questionAnswers.length > 0 && (
                                    <div className="border-b border-surface-100">
                                      <button
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          toggleCode(codeKey);
                                        }}
                                        className="w-full flex items-center justify-between p-3 bg-slate-50 hover:bg-slate-100 transition-colors"
                                      >
                                        <div className="flex items-center gap-2 text-slate-600">
                                          <Code size={16} />
                                          <span className="text-sm font-medium">תשובת התלמיד</span>
                                        </div>
                                        {isCodeExpanded ? (
                                          <ChevronUp size={16} className="text-slate-400" />
                                        ) : (
                                          <ChevronDown size={16} className="text-slate-400" />
                                        )}
                                      </button>

                                      {isCodeExpanded && (
                                        <div className="p-3 bg-slate-900 max-h-[400px] overflow-auto">
                                          {questionAnswers.map((answer, idx) => (
                                            <div key={idx} className="mb-4 last:mb-0">
                                              {answer.sub_question_id && (
                                                <div className="text-xs text-slate-400 mb-1">
                                                  סעיף {answer.sub_question_id}
                                                </div>
                                              )}
                                              <pre
                                                className="text-sm text-slate-100 font-mono whitespace-pre-wrap break-words"
                                                dir="ltr"
                                              >
                                                {answer.answer_text || '(ללא תשובה)'}
                                              </pre>
                                            </div>
                                          ))}
                                        </div>
                                      )}
                                    </div>
                                  )}

                                  {/* Grades table */}
                                  <div className="overflow-x-auto">
                                    <table className="w-full text-sm">
                                      <thead>
                                        <tr className="border-b border-surface-200 bg-surface-50">
                                          <th className="text-right py-2 px-3 font-medium text-gray-600">קריטריון</th>
                                          <th className="text-center py-2 px-2 font-medium text-gray-600 w-12">ציון</th>
                                          <th className="text-center py-2 px-2 font-medium text-gray-600 w-20">נקודות</th>
                                          <th className="text-right py-2 px-3 font-medium text-gray-600">הסבר</th>
                                        </tr>
                                      </thead>
                                      <tbody>
                                        {qg.grades.map((grade, i) => (
                                          <tr
                                            key={i}
                                            className={`border-b border-surface-100 hover:bg-surface-50 ${grade.confidence === 'low' ? 'bg-amber-50/50' : ''
                                              }`}
                                          >
                                            <td className="py-2 px-3">
                                              <div className="flex items-start gap-1">
                                                {grade.sub_question_id && (
                                                  <span className="text-xs text-gray-400 font-medium">
                                                    ({grade.sub_question_id})
                                                  </span>
                                                )}
                                                <span className="text-gray-700">{grade.criterion || 'קריטריון לא מזוהה'}</span>
                                              </div>
                                            </td>
                                            <td className="py-2 px-2 text-center">
                                              <div className="flex items-center justify-center">
                                                {getMarkIcon(grade.mark)}
                                              </div>
                                            </td>
                                            <td className="py-2 px-2 text-center">
                                              <span className={
                                                grade.points_earned === grade.points_possible
                                                  ? 'text-green-600 font-medium'
                                                  : grade.points_earned === 0
                                                    ? 'text-red-600'
                                                    : 'text-yellow-600'
                                              }>
                                                {grade.points_earned}/{grade.points_possible}
                                              </span>
                                            </td>
                                            <td className="py-2 px-3 text-gray-500 text-xs">
                                              <div className="flex items-start gap-1">
                                                <span>{grade.explanation || '-'}</span>
                                                {grade.confidence && grade.confidence !== 'high' && (
                                                  <span className="text-amber-500 whitespace-nowrap" title={grade.low_confidence_reason}>
                                                    ({grade.confidence})
                                                  </span>
                                                )}
                                              </div>
                                            </td>
                                          </tr>
                                        ))}
                                      </tbody>
                                    </table>
                                  </div>
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              );
            })
        )}
      </div>
    </div>
  );
}

// =============================================================================
// Handwritten Pages Gallery Component
// =============================================================================

interface HandwrittenPagesGalleryProps {
  pages: PagePreview[];
}

function HandwrittenPagesGallery({ pages }: HandwrittenPagesGalleryProps) {
  const [expandedPage, setExpandedPage] = useState<number | null>(null);

  if (!pages || pages.length === 0) return null;

  return (
    <div className="border-b border-surface-200 p-3 bg-amber-50">
      <div className="flex items-center gap-2 mb-2 text-amber-700 text-sm font-medium">
        <FileText size={16} />
        <span>עמודים מקוריים (כתב יד)</span>
        <span className="text-amber-600 text-xs">({pages.length} עמודים)</span>
      </div>

      {/* Thumbnail grid - centered */}
      <div className="flex gap-4 overflow-x-auto pb-2 justify-center">
        {pages.map((page, idx) => (
          <div
            key={page.page_index}
            className="relative flex-shrink-0 cursor-pointer hover:opacity-90 transition-opacity border-2 border-amber-200 rounded-lg overflow-hidden shadow-md"
            onClick={() => setExpandedPage(idx)}
          >
            {/* Page number badge */}
            <div className="absolute top-2 left-2 z-10 bg-amber-600 text-white text-sm px-2 py-1 rounded font-medium">
              {page.page_number}
            </div>
            <img
              src={`data:image/png;base64,${page.thumbnail_base64}`}
              alt={`עמוד ${page.page_number}`}
              className="h-[480px] w-auto object-contain"
            />
          </div>
        ))}
      </div>

      {/* Expanded modal */}
      {expandedPage !== null && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
          onClick={() => setExpandedPage(null)}
        >
          <button
            onClick={() => setExpandedPage(null)}
            className="absolute top-4 right-4 z-50 bg-white/10 hover:bg-white/20 text-white p-2 rounded-full"
          >
            <ChevronUp size={24} />
          </button>
          <div className="absolute top-4 left-4 z-50 bg-white/10 text-white px-3 py-1.5 rounded-lg text-sm">
            עמוד {pages[expandedPage].page_number} מתוך {pages.length}
          </div>
          {/* Navigation buttons */}
          {expandedPage > 0 && (
            <button
              onClick={(e) => { e.stopPropagation(); setExpandedPage(expandedPage - 1); }}
              className="absolute right-4 top-1/2 -translate-y-1/2 z-50 bg-white/10 hover:bg-white/20 text-white p-3 rounded-full"
            >
              <ChevronDown size={24} className="rotate-90" />
            </button>
          )}
          {expandedPage < pages.length - 1 && (
            <button
              onClick={(e) => { e.stopPropagation(); setExpandedPage(expandedPage + 1); }}
              className="absolute left-4 top-1/2 -translate-y-1/2 z-50 bg-white/10 hover:bg-white/20 text-white p-3 rounded-full"
            >
              <ChevronDown size={24} className="-rotate-90" />
            </button>
          )}
          <img
            src={`data:image/png;base64,${pages[expandedPage].thumbnail_base64}`}
            alt={`עמוד ${pages[expandedPage].page_number}`}
            className="max-w-[90vw] max-h-[90vh] object-contain rounded-lg shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </div>
  );
}