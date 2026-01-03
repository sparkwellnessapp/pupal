'use client';

import React, { useState } from 'react';
import { GradedTestResult, StudentAnswer, PagePreview, GradeItem, QuestionGrade as APIQuestionGrade, ExtraObservation, CodeEvidence } from '@/lib/api';
import {
  ChevronDown,
  ChevronUp,
  CheckCircle,
  XCircle,
  AlertCircle,
  User,
  FileText,
  Code,
  Eye,
  EyeOff,
  AlertTriangle,
  Check,
  X,
  Edit3,
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

// Use the imported types, but keep local alias for compatibility
type QuestionGrade = APIQuestionGrade;
type Grade = GradeItem;

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
  // Track applied extra deductions per test result (key: testId-questionNumber, value: total deduction)
  const [appliedDeductions, setAppliedDeductions] = useState<Map<string, number>>(new Map());

  // Calculate adjusted score for a result
  const getAdjustedScore = (result: GradedTestResult) => {
    let totalDeduction = 0;
    // Sum all deductions for this test's questions
    appliedDeductions.forEach((deduction, key) => {
      if (key.startsWith(result.id + '-')) {
        totalDeduction += deduction;
      }
    });
    const adjustedScore = Math.max(0, result.total_score - totalDeduction);
    const adjustedPercentage = result.total_possible > 0 ? (adjustedScore / result.total_possible) * 100 : 0;
    return { adjustedScore, adjustedPercentage, totalDeduction };
  };

  // Callback to update deductions for a specific question
  const handleDeductionChange = (testId: string, questionNumber: number, deduction: number) => {
    const key = `${testId}-${questionNumber}`;
    setAppliedDeductions(prev => {
      const newMap = new Map(prev);
      if (deduction === 0) {
        newMap.delete(key);
      } else {
        newMap.set(key, deduction);
      }
      return newMap;
    });
  };

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
                      {(() => {
                        const { adjustedScore, adjustedPercentage, totalDeduction } = getAdjustedScore(result);
                        return (
                          <>
                            <div className="text-sm text-gray-500">
                              {totalDeduction > 0 ? (
                                <span>
                                  <span className="line-through text-gray-400">{result.total_score}</span>
                                  <span className="text-red-600 font-medium ml-1">{adjustedScore}</span>
                                  /{result.total_possible}
                                </span>
                              ) : (
                                <span>{result.total_score}/{result.total_possible}</span>
                              )}
                            </div>
                            <div className={`px-3 py-1 rounded-full text-sm font-medium ${getScoreColor(adjustedPercentage)}`}>
                              {adjustedPercentage.toFixed(1)}%
                            </div>
                          </>
                        );
                      })()}
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

                                      {isCodeExpanded && (() => {
                                        // Calculate cumulative line offsets for each answer block
                                        let cumulativeLineOffset = 0;
                                        const answerOffsets = questionAnswers.map((answer) => {
                                          const offset = cumulativeLineOffset;
                                          cumulativeLineOffset += (answer.answer_text || '').split('\n').length;
                                          return offset;
                                        });

                                        return (
                                          <div className="p-3 bg-slate-900 max-h-[400px] overflow-auto">
                                            {questionAnswers.map((answer, idx) => {
                                              const lineOffset = answerOffsets[idx];
                                              return (
                                                <div key={idx} className="mb-4 last:mb-0">
                                                  {answer.sub_question_id && (
                                                    <div className="text-xs text-slate-400 mb-1">
                                                      סעיף {answer.sub_question_id}
                                                    </div>
                                                  )}
                                                  <div className="flex" dir="ltr">
                                                    {/* Line numbers - cumulative across all answer blocks */}
                                                    <div className="select-none text-right pr-3 border-r border-slate-700 text-slate-500 text-xs font-mono">
                                                      {(answer.answer_text || '').split('\n').map((_, lineIdx) => (
                                                        <div key={lineIdx} className="leading-5">{lineOffset + lineIdx + 1}</div>
                                                      ))}
                                                    </div>
                                                    {/* Code content */}
                                                    <pre className="text-sm text-slate-100 font-mono whitespace-pre-wrap break-words pl-3 flex-1">
                                                      {answer.answer_text || '(ללא תשובה)'}
                                                    </pre>
                                                  </div>
                                                </div>
                                              );
                                            })}
                                          </div>
                                        );
                                      })()}
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
                                          <th className="text-right py-2 px-3 font-medium text-gray-600">הסבר וראיות</th>
                                        </tr>
                                      </thead>
                                      <tbody>
                                        {qg.grades.map((grade, i) => {
                                          const evidenceKey = `${qKey}-evidence-${i}`;
                                          const isEvidenceExpanded = expandedQuestions.has(evidenceKey);
                                          return (
                                            <React.Fragment key={i}>
                                              <tr
                                                className={`border-b border-surface-100 hover:bg-surface-50 cursor-pointer ${grade.confidence === 'low' ? 'bg-amber-50/50' : ''}`}
                                                onClick={() => toggleQuestion(evidenceKey)}
                                              >
                                                <td className="py-2 px-3">
                                                  <div className="flex items-start gap-2">
                                                    {isEvidenceExpanded ? (
                                                      <ChevronUp size={14} className="text-gray-400 mt-0.5 flex-shrink-0" />
                                                    ) : (
                                                      <ChevronDown size={14} className="text-gray-400 mt-0.5 flex-shrink-0" />
                                                    )}
                                                    <div>
                                                      {grade.sub_question_id && (
                                                        <span className="text-xs text-gray-400 font-medium">
                                                          ({grade.sub_question_id})
                                                        </span>
                                                      )}
                                                      <span className="text-gray-700">{grade.criterion || 'קריטריון לא מזוהה'}</span>
                                                    </div>
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
                                                <td className="py-2 px-3 text-gray-500 text-xs max-w-[300px]">
                                                  <div className="flex items-start gap-1 group">
                                                    <span className="line-clamp-2 group-hover:line-clamp-none transition-all cursor-help">{grade.explanation || '-'}</span>
                                                    {grade.confidence && grade.confidence !== 'high' && (
                                                      <span className="text-amber-500 whitespace-nowrap" title={grade.low_confidence_reason}>
                                                        ({grade.confidence})
                                                      </span>
                                                    )}
                                                    {grade.evidence && (
                                                      <Eye size={14} className="text-blue-400 flex-shrink-0" />
                                                    )}
                                                  </div>
                                                </td>
                                              </tr>
                                              {/* Expanded Evidence Row */}
                                              {isEvidenceExpanded && grade.evidence && (
                                                <tr className="bg-blue-50/50">
                                                  <td colSpan={4} className="p-3">
                                                    <EvidenceDisplay evidence={grade.evidence} />
                                                  </td>
                                                </tr>
                                              )}
                                            </React.Fragment>
                                          );
                                        })}
                                      </tbody>
                                    </table>
                                  </div>

                                  {/* Extra Observations (Beyond Rubric Errors) */}
                                  {qg.extra_observations && qg.extra_observations.length > 0 && (
                                    <ExtraObservationsPanel
                                      observations={qg.extra_observations}
                                      onDeductionChange={(deduction) => handleDeductionChange(result.id, qg.question_number, deduction)}
                                    />
                                  )}
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

// =============================================================================
// Evidence Display Component
// =============================================================================

interface EvidenceDisplayProps {
  evidence: CodeEvidence;
}

function EvidenceDisplay({ evidence }: EvidenceDisplayProps) {
  return (
    <div className="space-y-3">
      {/* Quoted Code */}
      {evidence.quoted_code && (
        <div>
          <div className="flex items-center gap-2 text-xs font-medium text-blue-700 mb-1">
            <Code size={14} />
            <span>קוד רלוונטי</span>
            {evidence.line_numbers && evidence.line_numbers.length > 0 && (
              <span className="text-blue-500">(שורות {evidence.line_numbers.join(', ')})</span>
            )}
          </div>
          <pre className="bg-slate-900 text-slate-100 p-3 rounded-lg text-xs font-mono whitespace-pre-wrap overflow-x-auto" dir="ltr">
            {evidence.quoted_code}
          </pre>
        </div>
      )}

      {/* Reasoning Chain */}
      {evidence.reasoning_chain && evidence.reasoning_chain.length > 0 && (
        <div>
          <div className="flex items-center gap-2 text-xs font-medium text-blue-700 mb-1">
            <Eye size={14} />
            <span>ניתוח</span>
          </div>
          <ul className="space-y-1 text-xs text-gray-700 bg-white rounded-lg p-2 border border-blue-100">
            {evidence.reasoning_chain.map((step, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className="text-gray-400">•</span>
                <span>{step}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Extra Observations Panel (Beyond Rubric Errors with Apply Button)
// =============================================================================

interface ExtraObservationsPanelProps {
  observations: ExtraObservation[];
  onDeductionChange?: (totalDeduction: number) => void;
}

function ExtraObservationsPanel({ observations, onDeductionChange }: ExtraObservationsPanelProps) {
  const [appliedDeductions, setAppliedDeductions] = useState<Map<number, number>>(new Map());
  const [dismissedIndexes, setDismissedIndexes] = useState<Set<number>>(new Set());
  const [editingIndex, setEditingIndex] = useState<number | null>(null);

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'syntax_error': return <XCircle size={14} className="text-red-500" />;
      case 'logic_error': return <AlertTriangle size={14} className="text-orange-500" />;
      case 'style_warning': return <AlertCircle size={14} className="text-yellow-500" />;
      case 'missing_feature': return <X size={14} className="text-purple-500" />;
      default: return <AlertCircle size={14} className="text-gray-500" />;
    }
  };

  const getTypeLabel = (type: string) => {
    switch (type) {
      case 'syntax_error': return 'שגיאת תחביר';
      case 'logic_error': return 'שגיאת לוגיקה';
      case 'style_warning': return 'הערת סגנון';
      case 'missing_feature': return 'פיצ\'ר חסר';
      case 'security_issue': return 'בעיית אבטחה';
      default: return type;
    }
  };

  // Notify parent of deduction changes
  const notifyParent = (newMap: Map<number, number>) => {
    if (onDeductionChange) {
      const total = Array.from(newMap.values()).reduce((sum, d) => sum + d, 0);
      onDeductionChange(total);
    }
  };

  const toggleApply = (index: number, suggestedDeduction: number) => {
    const newMap = new Map(appliedDeductions);
    if (newMap.has(index)) {
      newMap.delete(index);
    } else {
      newMap.set(index, suggestedDeduction);
    }
    setAppliedDeductions(newMap);
    notifyParent(newMap);
    // Remove from dismissed if applying
    if (dismissedIndexes.has(index)) {
      const newDismissed = new Set(dismissedIndexes);
      newDismissed.delete(index);
      setDismissedIndexes(newDismissed);
    }
  };

  const toggleDismiss = (index: number) => {
    const newDismissed = new Set(dismissedIndexes);
    if (newDismissed.has(index)) {
      newDismissed.delete(index);
    } else {
      newDismissed.add(index);
      // Remove from applied if dismissing
      if (appliedDeductions.has(index)) {
        const newMap = new Map(appliedDeductions);
        newMap.delete(index);
        setAppliedDeductions(newMap);
        notifyParent(newMap);
      }
    }
    setDismissedIndexes(newDismissed);
  };

  const updateDeduction = (index: number, value: number) => {
    const newMap = new Map(appliedDeductions);
    newMap.set(index, value);
    setAppliedDeductions(newMap);
    notifyParent(newMap);
  };

  const totalDeduction = Array.from(appliedDeductions.values()).reduce((sum, d) => sum + d, 0);

  return (
    <div className="mt-3 p-3 bg-amber-50 rounded-lg border border-amber-200">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2 text-md font-medium text-amber-700">
          <AlertTriangle size={18} />
          <span>הערות נוספות (מחוץ למחוון)</span>
        </div>
        {totalDeduction > 0 && (
          <div className="text-sm font-medium text-red-600">
            סה"כ ניכוי: -{totalDeduction} נקודות
          </div>
        )}
      </div>

      <div className="space-y-2">
        {observations.map((obs, i) => {
          const isApplied = appliedDeductions.has(i);
          const isDismissed = dismissedIndexes.has(i);
          const currentDeduction = appliedDeductions.get(i) ?? obs.suggested_deduction;

          return (
            <div key={i} className={`flex items-start gap-3 p-2 rounded-lg transition-all ${isDismissed
              ? 'bg-gray-100 border border-gray-200 opacity-50'
              : isApplied
                ? 'bg-red-50 border border-red-200'
                : 'bg-white border border-amber-100'
              }`}>
              <div className="flex-shrink-0 mt-0.5">
                {getTypeIcon(obs.type)}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 text-xs">
                  <span className={`font-medium ${isDismissed ? 'text-gray-400 line-through' : 'text-gray-700'}`}>{getTypeLabel(obs.type)}</span>
                  {obs.line_number && (
                    <span className="text-gray-400">שורה {obs.line_number}</span>
                  )}
                </div>
                <p className={`text-xs mt-0.5 ${isDismissed ? 'text-gray-400' : 'text-gray-600'}`}>{obs.description}</p>
                {obs.quoted_code && !isDismissed && (
                  <pre className="mt-1 text-xs bg-gray-100 p-1 rounded font-mono text-gray-700" dir="ltr">
                    {obs.quoted_code}
                  </pre>
                )}
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                {!isDismissed && (
                  <>
                    {editingIndex === i ? (
                      <input
                        type="number"
                        value={currentDeduction}
                        onChange={(e) => updateDeduction(i, Math.abs(Number(e.target.value)))}
                        onBlur={() => setEditingIndex(null)}
                        className="w-12 text-center text-xs border rounded px-1 py-0.5"
                        autoFocus
                        min={0}
                        max={20}
                      />
                    ) : (
                      <button
                        onClick={() => setEditingIndex(i)}
                        className="text-xs text-gray-500 hover:text-gray-700 flex items-center gap-1"
                        title="ערוך ניכוי"
                      >
                        <Edit3 size={12} />
                        -{currentDeduction}
                      </button>
                    )}
                    <button
                      onClick={() => toggleApply(i, obs.suggested_deduction)}
                      className={`text-xs px-2 py-1 rounded flex items-center gap-1 transition-colors ${isApplied
                        ? 'bg-red-100 text-red-700 hover:bg-red-200'
                        : 'bg-green-100 text-green-700 hover:bg-green-200'
                        }`}
                    >
                      {isApplied ? (
                        <><X size={12} /> הסר</>
                      ) : (
                        <><Check size={12} /> החל</>
                      )}
                    </button>
                  </>
                )}
                <button
                  onClick={() => toggleDismiss(i)}
                  className={`text-xs px-2 py-1 rounded flex items-center gap-1 transition-colors ${isDismissed
                    ? 'bg-gray-200 text-gray-600 hover:bg-gray-300'
                    : 'bg-red-100 text-red-600 hover:bg-red-200'
                    }`}
                >
                  {isDismissed ? (
                    <><Eye size={12} /> הצג</>
                  ) : (
                    <><EyeOff size={12} /> דחה</>
                  )}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}