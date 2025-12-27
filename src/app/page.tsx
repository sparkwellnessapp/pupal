'use client';

import { useState, useCallback } from 'react';
import { FileUpload } from '@/components/FileUpload';
import { PageGrid } from '@/components/PageThumbnail';
import { QuestionMappingPanel } from '@/components/QuestionMappingPanel';
import { RubricEditor } from '@/components/RubricEditor';
import {
  previewRubricPdf,
  extractRubric,
  saveRubric,
  PagePreview,
  QuestionPageMapping,
  ExtractedQuestion,
  ExtractRubricResponse,
} from '@/lib/api';
import {
  Upload,
  Settings,
  CheckCircle,
  Loader2,
  ArrowLeft,
  ArrowRight,
  Save,
  AlertCircle,
} from 'lucide-react';

type Step = 'upload' | 'map' | 'review' | 'saved';

interface ActiveAssignment {
  questionIndex: number;
  type: 'question' | 'criteria' | 'sub_question_criteria';
  subQuestionId?: string;
}

export default function Home() {
  // Step state
  const [currentStep, setCurrentStep] = useState<Step>('upload');

  // Upload step state
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Map step state
  const [pages, setPages] = useState<PagePreview[]>([]);
  const [mappings, setMappings] = useState<QuestionPageMapping[]>([]);
  const [activeAssignment, setActiveAssignment] = useState<ActiveAssignment | null>(null);
  const [isExtracting, setIsExtracting] = useState(false);
  const [extractError, setExtractError] = useState<string | null>(null);

  // Review step state
  const [extractedQuestions, setExtractedQuestions] = useState<ExtractedQuestion[]>([]);
  const [rubricName, setRubricName] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Saved step state
  const [savedRubricId, setSavedRubricId] = useState<string | null>(null);

  // =============================================================================
  // Step 1: Upload PDF
  // =============================================================================

  const handleFileChange = async (newFile: File | null) => {
    setFile(newFile);
    setUploadError(null);

    if (newFile) {
      setIsUploading(true);
      try {
        const response = await previewRubricPdf(newFile);
        setPages(response.pages);
        setMappings([]);
        setCurrentStep('map');
      } catch (error) {
        setUploadError(error instanceof Error ? error.message : 'שגיאה בהעלאת הקובץ');
      } finally {
        setIsUploading(false);
      }
    }
  };

  // =============================================================================
  // Step 2: Map Pages to Questions
  // =============================================================================

  const handlePageClick = useCallback(
    (pageIndex: number) => {
      if (!activeAssignment) return;

      const newMappings = [...mappings];
      const question = newMappings[activeAssignment.questionIndex];
      if (!question) return;

      if (activeAssignment.type === 'question') {
        // Toggle page in question_page_indexes
        const idx = question.question_page_indexes.indexOf(pageIndex);
        if (idx >= 0) {
          question.question_page_indexes.splice(idx, 1);
        } else {
          question.question_page_indexes.push(pageIndex);
          question.question_page_indexes.sort((a, b) => a - b);
        }
      } else if (activeAssignment.type === 'criteria') {
        // Toggle page in criteria_page_indexes
        const idx = question.criteria_page_indexes.indexOf(pageIndex);
        if (idx >= 0) {
          question.criteria_page_indexes.splice(idx, 1);
        } else {
          question.criteria_page_indexes.push(pageIndex);
          question.criteria_page_indexes.sort((a, b) => a - b);
        }
      } else if (activeAssignment.type === 'sub_question_criteria') {
        // Toggle page in sub-question criteria_page_indexes
        const subQ = question.sub_questions.find(
          (sq) => sq.sub_question_id === activeAssignment.subQuestionId
        );
        if (subQ) {
          const idx = subQ.criteria_page_indexes.indexOf(pageIndex);
          if (idx >= 0) {
            subQ.criteria_page_indexes.splice(idx, 1);
          } else {
            subQ.criteria_page_indexes.push(pageIndex);
            subQ.criteria_page_indexes.sort((a, b) => a - b);
          }
        }
      }

      setMappings(newMappings);
    },
    [activeAssignment, mappings]
  );

  const getPageSelections = useCallback(() => {
    const selections = new Map<number, { label: string; color: string }>();

    mappings.forEach((q, qIndex) => {
      // Question pages
      q.question_page_indexes.forEach((pageIdx) => {
        const existing = selections.get(pageIdx);
        const label = `ש${q.question_number}`;
        selections.set(pageIdx, {
          label: existing ? `${existing.label}, ${label}` : label,
          color: 'bg-blue-500',
        });
      });

      // Direct criteria pages
      q.criteria_page_indexes.forEach((pageIdx) => {
        const existing = selections.get(pageIdx);
        const label = `מ${q.question_number}`;
        selections.set(pageIdx, {
          label: existing ? `${existing.label}, ${label}` : label,
          color: 'bg-green-500',
        });
      });

      // Sub-question criteria pages
      q.sub_questions.forEach((sq) => {
        sq.criteria_page_indexes.forEach((pageIdx) => {
          const existing = selections.get(pageIdx);
          const label = `מ${q.question_number}${sq.sub_question_id}`;
          selections.set(pageIdx, {
            label: existing ? `${existing.label}, ${label}` : label,
            color: 'bg-purple-500',
          });
        });
      });
    });

    return selections;
  }, [mappings]);

  const canExtract = mappings.length > 0 && mappings.every((m) => {
    const hasQuestionPages = m.question_page_indexes.length > 0;
    const hasCriteria = m.criteria_page_indexes.length > 0 || m.sub_questions.length > 0;
    const subQuestionsValid = m.sub_questions.every((sq) => sq.criteria_page_indexes.length > 0);
    return hasQuestionPages && hasCriteria && subQuestionsValid;
  });

  const handleExtract = async () => {
    if (!file || !canExtract) return;

    setIsExtracting(true);
    setExtractError(null);

    try {
      const response = await extractRubric(file, {
        name: rubricName || undefined,
        question_mappings: mappings,
      });

      setExtractedQuestions(response.questions);
      setCurrentStep('review');
    } catch (error) {
      setExtractError(error instanceof Error ? error.message : 'שגיאה בחילוץ המחוון');
    } finally {
      setIsExtracting(false);
    }
  };

  // =============================================================================
  // Step 3: Review and Edit
  // =============================================================================

  const handleSave = async () => {
    setIsSaving(true);
    setSaveError(null);

    try {
      const response = await saveRubric({
        name: rubricName || undefined,
        questions: extractedQuestions,
      });

      setSavedRubricId(response.id);
      setCurrentStep('saved');
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : 'שגיאה בשמירת המחוון');
    } finally {
      setIsSaving(false);
    }
  };

  // =============================================================================
  // Navigation
  // =============================================================================

  const goBack = () => {
    if (currentStep === 'map') {
      setCurrentStep('upload');
      setPages([]);
      setMappings([]);
    } else if (currentStep === 'review') {
      setCurrentStep('map');
    }
  };

  const startOver = () => {
    setCurrentStep('upload');
    setFile(null);
    setPages([]);
    setMappings([]);
    setExtractedQuestions([]);
    setRubricName('');
    setSavedRubricId(null);
  };

  // =============================================================================
  // Render
  // =============================================================================

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-50 to-surface-100">
      {/* Header */}
      <header className="bg-white border-b border-surface-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-800">Grader Vision</h1>
              <p className="text-sm text-gray-500">מערכת חילוץ מחוונים חכמה</p>
            </div>

            {/* Step indicator */}
            <div className="flex items-center gap-2">
              <StepIndicator step={1} label="העלאה" active={currentStep === 'upload'} completed={currentStep !== 'upload'} />
              <div className="w-8 h-0.5 bg-surface-300" />
              <StepIndicator step={2} label="מיפוי" active={currentStep === 'map'} completed={currentStep === 'review' || currentStep === 'saved'} />
              <div className="w-8 h-0.5 bg-surface-300" />
              <StepIndicator step={3} label="עריכה" active={currentStep === 'review'} completed={currentStep === 'saved'} />
              <div className="w-8 h-0.5 bg-surface-300" />
              <StepIndicator step={4} label="שמירה" active={currentStep === 'saved'} completed={false} />
            </div>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* Step 1: Upload */}
        {currentStep === 'upload' && (
          <div className="max-w-xl mx-auto animate-fade-in">
            <div className="bg-white rounded-xl shadow-lg p-8">
              <div className="text-center mb-6">
                <Upload className="mx-auto text-primary-500 mb-3" size={48} />
                <h2 className="text-xl font-semibold">העלאת מחוון</h2>
                <p className="text-gray-500 mt-1">העלה קובץ PDF של המחוון לחילוץ</p>
              </div>

              <FileUpload
                file={file}
                onFileChange={handleFileChange}
                label="העלה קובץ PDF של המחוון"
              />

              {isUploading && (
                <div className="mt-4 flex items-center justify-center gap-2 text-primary-600">
                  <Loader2 className="animate-spin" size={20} />
                  <span>מעבד את הקובץ...</span>
                </div>
              )}

              {uploadError && (
                <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm flex items-center gap-2">
                  <AlertCircle size={18} />
                  {uploadError}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Step 2: Map pages */}
        {currentStep === 'map' && (
          <div className="animate-fade-in">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Left panel: Page thumbnails */}
              <div className="bg-white rounded-xl shadow-lg p-6">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold">עמודי המחוון</h2>
                  <span className="text-sm text-gray-500">{pages.length} עמודים</span>
                </div>

                <div className="max-h-[600px] overflow-y-auto">
                  <PageGrid
                    pages={pages}
                    selections={getPageSelections()}
                    onPageClick={handlePageClick}
                  />
                </div>

                {/* Legend */}
                <div className="mt-4 pt-4 border-t border-surface-200 flex flex-wrap gap-3 text-xs">
                  <div className="flex items-center gap-1">
                    <div className="w-3 h-3 bg-blue-500 rounded" />
                    <span>טקסט שאלה</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="w-3 h-3 bg-green-500 rounded" />
                    <span>מחוון ישיר</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="w-3 h-3 bg-purple-500 rounded" />
                    <span>מחוון סעיף</span>
                  </div>
                </div>
              </div>

              {/* Right panel: Question mappings */}
              <div className="bg-white rounded-xl shadow-lg p-6">
                <QuestionMappingPanel
                  mappings={mappings}
                  onMappingsChange={setMappings}
                  activeAssignment={activeAssignment}
                  onSetActiveAssignment={setActiveAssignment}
                />

                {/* Rubric name input */}
                <div className="mt-6 pt-4 border-t border-surface-200">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    שם המחוון (אופציונלי)
                  </label>
                  <input
                    type="text"
                    value={rubricName}
                    onChange={(e) => setRubricName(e.target.value)}
                    className="w-full p-2 border border-surface-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-300"
                    placeholder="לדוגמה: מבחן C# תשפ״ד"
                    dir="rtl"
                  />
                </div>

                {extractError && (
                  <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm flex items-center gap-2">
                    <AlertCircle size={18} />
                    {extractError}
                  </div>
                )}

                {/* Actions */}
                <div className="mt-6 flex items-center justify-between">
                  <button
                    onClick={goBack}
                    className="flex items-center gap-1 text-gray-600 hover:text-gray-800"
                  >
                    <ArrowRight size={18} />
                    חזור
                  </button>

                  <button
                    onClick={handleExtract}
                    disabled={!canExtract || isExtracting}
                    className="flex items-center gap-2 bg-primary-500 text-white px-6 py-2 rounded-lg hover:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {isExtracting ? (
                      <>
                        <Loader2 className="animate-spin" size={18} />
                        מחלץ...
                      </>
                    ) : (
                      <>
                        <Settings size={18} />
                        חלץ מחוון
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Step 3: Review and Edit */}
        {currentStep === 'review' && (
          <div className="animate-fade-in">
            <div className="bg-white rounded-xl shadow-lg p-6">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-xl font-semibold">עריכת המחוון</h2>
                  <p className="text-sm text-gray-500">
                    בדוק ועדכן את התוצאות לפני השמירה
                  </p>
                </div>

                {rubricName && (
                  <div className="text-sm text-gray-600">
                    <span className="font-medium">שם: </span>
                    {rubricName}
                  </div>
                )}
              </div>

              <RubricEditor
                questions={extractedQuestions}
                onQuestionsChange={setExtractedQuestions}
              />

              {saveError && (
                <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm flex items-center gap-2">
                  <AlertCircle size={18} />
                  {saveError}
                </div>
              )}

              {/* Actions */}
              <div className="mt-6 pt-4 border-t border-surface-200 flex items-center justify-between">
                <button
                  onClick={goBack}
                  className="flex items-center gap-1 text-gray-600 hover:text-gray-800"
                >
                  <ArrowRight size={18} />
                  חזור למיפוי
                </button>

                <button
                  onClick={handleSave}
                  disabled={isSaving || extractedQuestions.length === 0}
                  className="flex items-center gap-2 bg-green-500 text-white px-6 py-2 rounded-lg hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {isSaving ? (
                    <>
                      <Loader2 className="animate-spin" size={18} />
                      שומר...
                    </>
                  ) : (
                    <>
                      <Save size={18} />
                      שמור מחוון
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Step 4: Saved */}
        {currentStep === 'saved' && (
          <div className="max-w-xl mx-auto animate-fade-in">
            <div className="bg-white rounded-xl shadow-lg p-8 text-center">
              <CheckCircle className="mx-auto text-green-500 mb-4" size={64} />
              <h2 className="text-2xl font-semibold text-green-700">המחוון נשמר בהצלחה!</h2>
              <p className="text-gray-500 mt-2">
                מזהה המחוון: <code className="bg-surface-100 px-2 py-1 rounded">{savedRubricId}</code>
              </p>

              <div className="mt-8">
                <button
                  onClick={startOver}
                  className="flex items-center gap-2 mx-auto bg-primary-500 text-white px-6 py-2 rounded-lg hover:bg-primary-600 transition-colors"
                >
                  <ArrowRight size={18} />
                  התחל מחדש
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

// =============================================================================
// Step Indicator Component
// =============================================================================

function StepIndicator({
  step,
  label,
  active,
  completed,
}: {
  step: number;
  label: string;
  active: boolean;
  completed: boolean;
}) {
  return (
    <div className="flex items-center gap-2">
      <div
        className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-colors ${
          active
            ? 'bg-primary-500 text-white'
            : completed
            ? 'bg-green-500 text-white'
            : 'bg-surface-200 text-gray-500'
        }`}
      >
        {completed ? <CheckCircle size={16} /> : step}
      </div>
      <span className={`text-sm ${active ? 'text-primary-700 font-medium' : 'text-gray-500'}`}>
        {label}
      </span>
    </div>
  );
}
