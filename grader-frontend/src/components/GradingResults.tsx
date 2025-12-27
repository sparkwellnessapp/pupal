'use client';

import { useState } from 'react';
import { GradedTestResult } from '@/lib/api';
import { 
  ChevronDown, 
  ChevronUp, 
  CheckCircle, 
  XCircle, 
  AlertCircle,
  User,
  FileText,
  Award
} from 'lucide-react';

interface GradingResultsProps {
  results: GradedTestResult[];
  totalTests: number;
  successful: number;
  failed: number;
  errors: string[];
}

export function GradingResults({
  results,
  totalTests,
  successful,
  failed,
  errors,
}: GradingResultsProps) {
  const [expandedTests, setExpandedTests] = useState<Set<string>>(new Set());

  const toggleExpanded = (testId: string) => {
    const newExpanded = new Set(expandedTests);
    if (newExpanded.has(testId)) {
      newExpanded.delete(testId);
    } else {
      newExpanded.add(testId);
    }
    setExpandedTests(newExpanded);
  };

  const getScoreColor = (percentage: number) => {
    if (percentage >= 80) return 'text-green-600 bg-green-50';
    if (percentage >= 60) return 'text-yellow-600 bg-yellow-50';
    return 'text-red-600 bg-red-50';
  };

  const getMarkIcon = (mark: string) => {
    if (mark === '✓') return <CheckCircle size={16} className="text-green-500" />;
    if (mark === '✗') return <XCircle size={16} className="text-red-500" />;
    return <AlertCircle size={16} className="text-yellow-500" />;
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
            .map((result) => (
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
                        {result.filename}
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
                    {/* Low confidence items */}
                    {result.graded_json.low_confidence_items && result.graded_json.low_confidence_items.length > 0 && (
                      <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                        <h5 className="font-medium text-amber-700 text-sm mb-1">
                          ⚠️ פריטים לבדיקה ידנית:
                        </h5>
                        <ul className="text-xs text-amber-600 space-y-1">
                          {result.graded_json.low_confidence_items.map((item, i) => (
                            <li key={i}>• {item}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Grades table */}
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-surface-200">
                            <th className="text-right py-2 px-2 font-medium text-gray-600">קריטריון</th>
                            <th className="text-center py-2 px-2 font-medium text-gray-600 w-16">ציון</th>
                            <th className="text-center py-2 px-2 font-medium text-gray-600 w-20">נקודות</th>
                            <th className="text-right py-2 px-2 font-medium text-gray-600">הסבר</th>
                          </tr>
                        </thead>
                        <tbody>
                          {result.graded_json.grades.map((grade, i) => (
                            <tr key={i} className="border-b border-surface-100 hover:bg-white">
                              <td className="py-2 px-2">
                                <div className="flex items-start gap-2">
                                  {grade.question_number && (
                                    <span className="text-xs text-gray-400 whitespace-nowrap">
                                      ש{grade.question_number}
                                      {grade.sub_question_id && `-${grade.sub_question_id}`}
                                    </span>
                                  )}
                                  <span className="text-gray-700">{grade.criterion}</span>
                                </div>
                              </td>
                              <td className="py-2 px-2 text-center">
                                <div className="flex items-center justify-center">
                                  {getMarkIcon(grade.mark)}
                                </div>
                              </td>
                              <td className="py-2 px-2 text-center">
                                <span className={grade.points_earned === grade.points_possible ? 'text-green-600' : grade.points_earned === 0 ? 'text-red-600' : 'text-yellow-600'}>
                                  {grade.points_earned}/{grade.points_possible}
                                </span>
                              </td>
                              <td className="py-2 px-2 text-gray-500 text-xs">
                                {grade.explanation}
                                {grade.confidence !== 'high' && (
                                  <span className="text-amber-500 mr-1">
                                    ({grade.confidence})
                                  </span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            ))
        )}
      </div>
    </div>
  );
}
