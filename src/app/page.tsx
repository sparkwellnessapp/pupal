'use client';

import { useState, useCallback, useEffect } from 'react';
import { FileUpload } from '@/components/FileUpload';
import { MultiFileUpload } from '@/components/MultiFileUpload';
import { PageGrid } from '@/components/PageThumbnail';
import { QuestionMappingPanel } from '@/components/QuestionMappingPanel';
import { RubricEditor } from '@/components/RubricEditor';
import { AnswerMappingPanel } from '@/components/AnswerMappingPanel';
import { GradingResults } from '@/components/GradingResults';
import { RubricSelector } from '@/components/RubricSelector';
import {
  previewRubricPdf,
  extractRubric,
  saveRubric,
  previewStudentTestPdf,
  gradeSingleTest,
  PagePreview,
  QuestionPageMapping,
  ExtractedQuestion,
  RubricListItem,
  AnswerPageMapping,
  GradedTestResult,
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
  BookOpen,
  GraduationCap,
  FileText,
  ClipboardCheck,
  Home as HomeIcon,
  User,
} from 'lucide-react';

type MainMode = 'select' | 'rubric' | 'grading';
// Added 'extracting' step between 'map' and 'review'
type RubricStep = 'upload' | 'map' | 'extracting' | 'review' | 'saved';
type GradingStep = 'select_rubric' | 'upload_batch' | 'map_answers' | 'grading' | 'results';

interface ActiveRubricAssignment {
  questionIndex: number;
  type: 'question' | 'criteria' | 'sub_question_criteria';
  subQuestionId?: string;
}

interface ActiveAnswerAssignment {
  mappingIndex: number;
}

interface GradingProgress {
  current: number;
  total: number;
  currentFileName: string;
}

// NEW: Extraction progress tracking
interface ExtractionProgress {
  currentQuestion: number;
  totalQuestions: number;
  stage: 'preparing' | 'extracting_question' | 'extracting_criteria' | 'finalizing';
}

// Store mapping for each test
interface TestMapping {
  file: File;
  pages: PagePreview[];
  answerMappings: AnswerPageMapping[];
  isLoaded: boolean;
}

export default function Home() {
  const [mainMode, setMainMode] = useState<MainMode>('select');

  // Rubric Flow State
  const [rubricStep, setRubricStep] = useState<RubricStep>('upload');
  const [rubricFile, setRubricFile] = useState<File | null>(null);
  const [rubricPages, setRubricPages] = useState<PagePreview[]>([]);
  const [rubricMappings, setRubricMappings] = useState<QuestionPageMapping[]>([]);
  const [activeRubricAssignment, setActiveRubricAssignment] = useState<ActiveRubricAssignment | null>(null);
  const [extractedQuestions, setExtractedQuestions] = useState<ExtractedQuestion[]>([]);
  const [rubricName, setRubricName] = useState('');
  const [savedRubricId, setSavedRubricId] = useState<string | null>(null);
  // NEW: Extraction progress
  const [extractionProgress, setExtractionProgress] = useState<ExtractionProgress | null>(null);

  // Grading Flow State
  const [gradingStep, setGradingStep] = useState<GradingStep>('select_rubric');
  const [selectedRubric, setSelectedRubric] = useState<RubricListItem | null>(null);
  const [testFiles, setTestFiles] = useState<File[]>([]);
  const [firstPageIndex, setFirstPageIndex] = useState(0);

  // Per-test mapping state
  const [testMappings, setTestMappings] = useState<TestMapping[]>([]);
  const [currentTestIndex, setCurrentTestIndex] = useState(0);
  const [activeAnswerAssignment, setActiveAnswerAssignment] = useState<ActiveAnswerAssignment | null>(null);

  // Grading results
  const [gradingResults, setGradingResults] = useState<GradedTestResult[]>([]);
  const [gradingStats, setGradingStats] = useState({ total: 0, successful: 0, failed: 0, errors: [] as string[] });
  const [gradingProgress, setGradingProgress] = useState<GradingProgress | null>(null);

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Current test being mapped
  const currentTest = testMappings[currentTestIndex];

  // Rubric Handlers
  const handleRubricFileChange = async (file: File | null) => {
    setRubricFile(file);
    setError(null);
    if (file) {
      setIsLoading(true);
      try {
        const response = await previewRubricPdf(file);
        setRubricPages(response.pages);
        setRubricMappings([]);
        setRubricStep('map');
      } catch (err) {
        setError(err instanceof Error ? err.message : 'שגיאה בהעלאת הקובץ');
      } finally {
        setIsLoading(false);
      }
    }
  };

  const handleRubricPageClick = useCallback((pageIndex: number) => {
    if (!activeRubricAssignment) return;
    const newMappings = [...rubricMappings];
    const question = newMappings[activeRubricAssignment.questionIndex];
    if (!question) return;

    if (activeRubricAssignment.type === 'question') {
      const idx = question.question_page_indexes.indexOf(pageIndex);
      if (idx >= 0) question.question_page_indexes.splice(idx, 1);
      else { question.question_page_indexes.push(pageIndex); question.question_page_indexes.sort((a, b) => a - b); }
    } else if (activeRubricAssignment.type === 'criteria') {
      const idx = question.criteria_page_indexes.indexOf(pageIndex);
      if (idx >= 0) question.criteria_page_indexes.splice(idx, 1);
      else { question.criteria_page_indexes.push(pageIndex); question.criteria_page_indexes.sort((a, b) => a - b); }
    } else if (activeRubricAssignment.type === 'sub_question_criteria') {
      const subQ = question.sub_questions.find(sq => sq.sub_question_id === activeRubricAssignment.subQuestionId);
      if (subQ) {
        const idx = subQ.criteria_page_indexes.indexOf(pageIndex);
        if (idx >= 0) subQ.criteria_page_indexes.splice(idx, 1);
        else { subQ.criteria_page_indexes.push(pageIndex); subQ.criteria_page_indexes.sort((a, b) => a - b); }
      }
    }
    setRubricMappings(newMappings);
  }, [activeRubricAssignment, rubricMappings]);

  const getRubricPageSelections = useCallback(() => {
    const selections = new Map<number, { label: string; color: string }>();
    rubricMappings.forEach((q) => {
      q.question_page_indexes.forEach((pageIdx) => {
        const existing = selections.get(pageIdx);
        const label = `ש${q.question_number}`;
        selections.set(pageIdx, { label: existing ? `${existing.label}, ${label}` : label, color: 'bg-primary-500' });
      });
      q.criteria_page_indexes.forEach((pageIdx) => {
        const existing = selections.get(pageIdx);
        const label = `מ${q.question_number}`;
        selections.set(pageIdx, { label: existing ? `${existing.label}, ${label}` : label, color: 'bg-purple-500' });
      });
      q.sub_questions.forEach((sq) => {
        sq.criteria_page_indexes.forEach((pageIdx) => {
          const existing = selections.get(pageIdx);
          const label = `מ${q.question_number}${sq.sub_question_id}`;
          selections.set(pageIdx, { label: existing ? `${existing.label}, ${label}` : label, color: 'bg-purple-500' });
        });
      });
    });
    return selections;
  }, [rubricMappings]);

  const canExtractRubric = rubricMappings.length > 0 && rubricMappings.every((m) => {
    const hasQuestionPages = m.question_page_indexes.length > 0;
    const hasCriteria = m.criteria_page_indexes.length > 0 || m.sub_questions.length > 0;
    const subQuestionsValid = m.sub_questions.every((sq) => sq.criteria_page_indexes.length > 0);
    return hasQuestionPages && hasCriteria && subQuestionsValid;
  });

  // UPDATED: Extract rubric with progress tracking
  const handleExtractRubric = async () => {
    if (!rubricFile || !canExtractRubric) return;

    // Switch to extracting step first
    setRubricStep('extracting');
    setError(null);

    // Initialize progress
    const totalQuestions = rubricMappings.length;
    setExtractionProgress({
      currentQuestion: 0,
      totalQuestions,
      stage: 'preparing'
    });

    // Simulate progress updates while extraction happens
    // (The actual extraction is a single API call, but we show estimated progress)
    const progressInterval = setInterval(() => {
      setExtractionProgress(prev => {
        if (!prev) return null;

        // Cycle through stages with estimated timing
        if (prev.stage === 'preparing') {
          return { ...prev, stage: 'extracting_question', currentQuestion: 1 };
        }

        if (prev.stage === 'extracting_question') {
          return { ...prev, stage: 'extracting_criteria' };
        }

        if (prev.stage === 'extracting_criteria') {
          if (prev.currentQuestion < prev.totalQuestions) {
            return {
              ...prev,
              stage: 'extracting_question',
              currentQuestion: prev.currentQuestion + 1
            };
          } else {
            return { ...prev, stage: 'finalizing' };
          }
        }

        return prev;
      });
    }, 2000); // Update every 2 seconds

    try {
      const response = await extractRubric(rubricFile, {
        name: rubricName || undefined,
        question_mappings: rubricMappings
      });

      clearInterval(progressInterval);
      setExtractedQuestions(response.questions);
      setExtractionProgress(null);
      setRubricStep('review');
    } catch (err) {
      clearInterval(progressInterval);
      setExtractionProgress(null);
      setError(err instanceof Error ? err.message : 'שגיאה בחילוץ המחוון');
      setRubricStep('map'); // Go back to mapping on error
    }
  };

  const handleSaveRubric = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await saveRubric({ name: rubricName || undefined, questions: extractedQuestions });
      setSavedRubricId(response.id);
      setRubricStep('saved');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'שגיאה בשמירת המחוון');
    } finally {
      setIsLoading(false);
    }
  };

  // Grading Handlers
  const handleRubricSelect = (rubric: RubricListItem) => {
    setSelectedRubric(rubric);
    setGradingStep('upload_batch');
  };

  // Initialize test mappings when files are uploaded and user proceeds
  const handleProceedToMapping = async () => {
    if (testFiles.length === 0) return;

    // Initialize mappings array with empty mappings
    const initialMappings: TestMapping[] = testFiles.map(file => ({
      file,
      pages: [],
      answerMappings: [],
      isLoaded: false,
    }));

    setTestMappings(initialMappings);
    setCurrentTestIndex(0);
    setGradingStep('map_answers');

    // Load first test pages
    await loadTestPages(0, initialMappings);
  };

  // Load pages for a specific test
  const loadTestPages = async (index: number, mappings: TestMapping[]) => {
    if (mappings[index].isLoaded) return;

    setIsLoading(true);
    setError(null);

    try {
      const response = await previewStudentTestPdf(mappings[index].file);

      const newMappings = [...mappings];
      newMappings[index] = {
        ...newMappings[index],
        pages: response.pages,
        isLoaded: true,
        // Pre-fill with previous test's mapping if available
        answerMappings: index > 0 && newMappings[index - 1].answerMappings.length > 0
          ? JSON.parse(JSON.stringify(newMappings[index - 1].answerMappings))
          : [],
      };

      setTestMappings(newMappings);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'שגיאה בטעינת המבחן');
    } finally {
      setIsLoading(false);
    }
  };

  // Handle page click for current test
  const handleAnswerPageClick = useCallback((pageIndex: number) => {
    if (!activeAnswerAssignment || !currentTest) return;

    const newMappings = [...testMappings];
    const currentMapping = newMappings[currentTestIndex];
    const answerMapping = currentMapping.answerMappings[activeAnswerAssignment.mappingIndex];

    if (!answerMapping) return;

    const idx = answerMapping.page_indexes.indexOf(pageIndex);
    if (idx >= 0) {
      answerMapping.page_indexes.splice(idx, 1);
    } else {
      answerMapping.page_indexes.push(pageIndex);
      answerMapping.page_indexes.sort((a, b) => a - b);
    }

    setTestMappings(newMappings);
  }, [activeAnswerAssignment, currentTestIndex, testMappings, currentTest]);

  // Get page selections for current test
  const getAnswerPageSelections = useCallback(() => {
    const selections = new Map<number, { label: string; color: string }>();
    if (!currentTest) return selections;

    currentTest.answerMappings.forEach((mapping) => {
      mapping.page_indexes.forEach((pageIdx) => {
        const label = mapping.sub_question_id
          ? `${mapping.question_number}${mapping.sub_question_id}`
          : `${mapping.question_number}`;
        selections.set(pageIdx, { label, color: 'bg-primary-500' });
      });
    });
    return selections;
  }, [currentTest]);

  // Update current test's mappings
  const updateCurrentTestMappings = (newAnswerMappings: AnswerPageMapping[]) => {
    const newMappings = [...testMappings];
    newMappings[currentTestIndex] = {
      ...newMappings[currentTestIndex],
      answerMappings: newAnswerMappings,
    };
    setTestMappings(newMappings);
  };

  // Check if current test mapping is valid
  const isCurrentMappingValid = currentTest?.answerMappings.length > 0 &&
    currentTest.answerMappings.every((m) => m.page_indexes.length > 0);

  // Navigate to next test
  const handleNextTest = async () => {
    if (currentTestIndex < testMappings.length - 1) {
      const nextIndex = currentTestIndex + 1;
      setCurrentTestIndex(nextIndex);
      setActiveAnswerAssignment(null);

      // Load next test's pages if not loaded
      if (!testMappings[nextIndex].isLoaded) {
        await loadTestPages(nextIndex, testMappings);
      }
    } else {
      // All tests mapped, proceed to grading
      handleStartGrading();
    }
  };

  // Navigate to previous test
  const handlePrevTest = () => {
    if (currentTestIndex > 0) {
      setCurrentTestIndex(currentTestIndex - 1);
      setActiveAnswerAssignment(null);
    } else {
      // Go back to batch upload
      setGradingStep('upload_batch');
      setTestMappings([]);
      setCurrentTestIndex(0);
    }
  };

  // Grade all tests
  const handleStartGrading = async () => {
    if (!selectedRubric || testMappings.length === 0) return;

    setIsLoading(true);
    setError(null);
    setGradingStep('grading');
    setGradingProgress({ current: 0, total: testMappings.length, currentFileName: '' });

    const results: GradedTestResult[] = [];
    const errors: string[] = [];

    for (let i = 0; i < testMappings.length; i++) {
      const testMapping = testMappings[i];
      setGradingProgress({
        current: i,
        total: testMappings.length,
        currentFileName: testMapping.file.name
      });

      try {
        const result = await gradeSingleTest(
          selectedRubric.id,
          testMapping.answerMappings,
          testMapping.file,
          firstPageIndex
        );
        results.push(result);
      } catch (err) {
        errors.push(`${testMapping.file.name}: ${err instanceof Error ? err.message : 'שגיאה לא ידועה'}`);
      }

      setGradingProgress({
        current: i + 1,
        total: testMappings.length,
        currentFileName: i + 1 < testMappings.length ? testMappings[i + 1].file.name : ''
      });
    }

    setGradingResults(results);
    setGradingStats({
      total: testMappings.length,
      successful: results.length,
      failed: errors.length,
      errors: errors,
    });
    setGradingProgress(null);
    setGradingStep('results');
    setIsLoading(false);
  };

  // Navigation - go to home (reset everything)
  const goToHome = () => {
    setMainMode('select');
    setRubricStep('upload');
    setRubricFile(null);
    setRubricPages([]);
    setRubricMappings([]);
    setExtractedQuestions([]);
    setRubricName('');
    setExtractionProgress(null);
    setGradingStep('select_rubric');
    setSelectedRubric(null);
    setTestFiles([]);
    setTestMappings([]);
    setCurrentTestIndex(0);
    setGradingResults([]);
    setGradingProgress(null);
    setError(null);
  };

  // Get stage message for extraction progress
  const getExtractionStageMessage = (progress: ExtractionProgress): string => {
    switch (progress.stage) {
      case 'preparing':
        return 'מכין את החילוץ...';
      case 'extracting_question':
        return `מחלץ טקסט שאלה ${progress.currentQuestion}...`;
      case 'extracting_criteria':
        return `מחלץ קריטריונים לשאלה ${progress.currentQuestion}...`;
      case 'finalizing':
        return 'מסיים את החילוץ...';
      default:
        return 'מחלץ מחוון...';
    }
  };

  // Back button component
  const BackButton = ({ onClick }: { onClick: () => void }) => (
    <button
      onClick={onClick}
      className="flex items-center gap-1 text-gray-500 hover:text-gray-700 transition-colors"
    >
      <ArrowRight size={18} />
      <span className="text-sm">חזור</span>
    </button>
  );

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-50 to-surface-100">
      {/* Header */}
      <header className="bg-white border-b border-surface-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-bold text-primary-600">Pupil</h1>
              {mainMode !== 'select' && (
                <span className="text-sm text-gray-400 border-r border-gray-200 pr-3 mr-1">
                  {mainMode === 'rubric' && 'יצירת מחוון'}
                  {mainMode === 'grading' && 'בדיקת מבחנים'}
                </span>
              )}
            </div>

            {mainMode !== 'select' && (
              <button
                onClick={goToHome}
                className="flex items-center gap-2 text-gray-500 hover:text-primary-600 transition-colors px-3 py-1.5 rounded-lg hover:bg-primary-50"
              >
                <HomeIcon size={18} />
                <span className="text-sm">לדף הבית</span>
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* Mode Selection */}
        {mainMode === 'select' && (
          <div className="max-w-3xl mx-auto animate-fade-in">
            <div className="text-center mb-8">
              <h2 className="text-2xl font-semibold text-gray-800 mb-2">מה תרצה לעשות?</h2>
              <p className="text-gray-500">בחר פעולה כדי להתחיל</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <button onClick={() => setMainMode('rubric')} className="bg-white rounded-2xl p-8 border-2 border-surface-200 hover:border-primary-400 hover:shadow-lg transition-all text-right group">
                <div className="w-16 h-16 bg-primary-100 rounded-2xl flex items-center justify-center mb-4 group-hover:bg-primary-200 transition-colors">
                  <BookOpen size={32} className="text-primary-600" />
                </div>
                <h3 className="text-xl font-semibold text-gray-800 mb-2">יצירת מחוון</h3>
                <p className="text-gray-500 text-sm">העלה PDF של מחוון, מפה את השאלות והקריטריונים, ושמור למערכת</p>
              </button>
              <button onClick={() => setMainMode('grading')} className="bg-white rounded-2xl p-8 border-2 border-surface-200 hover:border-primary-400 hover:shadow-lg transition-all text-right group">
                <div className="w-16 h-16 bg-primary-100 rounded-2xl flex items-center justify-center mb-4 group-hover:bg-primary-200 transition-colors">
                  <GraduationCap size={32} className="text-primary-600" />
                </div>
                <h3 className="text-xl font-semibold text-gray-800 mb-2">בדיקת מבחנים</h3>
                <p className="text-gray-500 text-sm">בחר מחוון קיים, העלה מבחני תלמידים, וקבל ציונים אוטומטיים</p>
              </button>
            </div>
            {savedRubricId && (
              <div className="mt-8 p-4 bg-primary-50 border border-primary-200 rounded-xl text-center">
                <p className="text-primary-700 text-sm mb-2">מחוון אחרון שנשמר: <code className="bg-primary-100 px-2 py-0.5 rounded">{savedRubricId}</code></p>
                <button onClick={() => setMainMode('grading')} className="text-primary-600 hover:text-primary-800 text-sm font-medium">המשך לבדיקת מבחנים →</button>
              </div>
            )}
          </div>
        )}

        {/* RUBRIC FLOW */}
        {mainMode === 'rubric' && (
          <>
            {rubricStep === 'upload' && (
              <div className="max-w-xl mx-auto animate-fade-in">
                <div className="bg-white rounded-xl shadow-lg p-8">
                  <div className="text-center mb-6">
                    <Upload className="mx-auto text-primary-500 mb-3" size={48} />
                    <h2 className="text-xl font-semibold">העלאת מחוון</h2>
                    <p className="text-gray-500 mt-1">העלה קובץ PDF של המחוון לחילוץ</p>
                  </div>
                  <FileUpload file={rubricFile} onFileChange={handleRubricFileChange} label="העלה קובץ PDF של המחוון" />
                  {isLoading && <div className="mt-4 flex items-center justify-center gap-2 text-primary-600"><Loader2 className="animate-spin" size={20} /><span>מעבד את הקובץ...</span></div>}
                  {error && <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm flex items-center gap-2"><AlertCircle size={18} />{error}</div>}
                </div>
              </div>
            )}

            {rubricStep === 'map' && (
              <div className="animate-fade-in">
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <div className="bg-white rounded-xl shadow-lg p-6">
                    <div className="flex items-center justify-between mb-4">
                      <h2 className="text-lg font-semibold">עמודי המחוון</h2>
                      <span className="text-sm text-gray-500">{rubricPages.length} עמודים</span>
                    </div>
                    <div className="max-h-[600px] overflow-y-auto">
                      <PageGrid pages={rubricPages} selections={getRubricPageSelections()} onPageClick={handleRubricPageClick} />
                    </div>
                  </div>
                  <div className="bg-white rounded-xl shadow-lg p-6">
                    <QuestionMappingPanel mappings={rubricMappings} onMappingsChange={setRubricMappings} activeAssignment={activeRubricAssignment} onSetActiveAssignment={setActiveRubricAssignment} />
                    <div className="mt-6 pt-4 border-t border-surface-200">
                      <label className="block text-sm font-medium text-gray-700 mb-1">שם המחוון</label>
                      <input type="text" value={rubricName} onChange={(e) => setRubricName(e.target.value)} className="w-full p-2 border border-surface-300 rounded-lg text-sm" placeholder="לדוגמה: מבחן C# תשפ״ד" dir="rtl" />
                    </div>
                    {error && <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{error}</div>}
                    <div className="mt-6 flex items-center justify-between">
                      <BackButton onClick={() => { setRubricStep('upload'); setRubricFile(null); }} />
                      <button onClick={handleExtractRubric} disabled={!canExtractRubric || isLoading} className="flex items-center gap-2 bg-primary-500 text-white px-6 py-2 rounded-lg hover:bg-primary-600 disabled:opacity-50 transition-colors">
                        {isLoading ? <Loader2 className="animate-spin" size={18} /> : <Settings size={18} />}
                        {isLoading ? 'מחלץ...' : 'חלץ מחוון'}
                        <ArrowLeft size={18} />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* NEW: Extracting step with progress */}
            {rubricStep === 'extracting' && (
              <div className="max-w-xl mx-auto animate-fade-in">
                <div className="bg-white rounded-xl shadow-lg p-8 text-center">
                  <Loader2 className="mx-auto text-primary-500 mb-4 animate-spin" size={64} />
                  <h2 className="text-xl font-semibold text-gray-800">מחלץ מחוון...</h2>

                  {extractionProgress && (
                    <div className="mt-6 space-y-4">
                      {/* Progress bar */}
                      <div className="w-full bg-surface-200 rounded-full h-3 overflow-hidden">
                        <div
                          className="bg-primary-500 h-3 rounded-full transition-all duration-500 ease-out"
                          style={{
                            width: `${Math.min(
                              ((extractionProgress.currentQuestion - 0.5 +
                                (extractionProgress.stage === 'extracting_criteria' ? 0.5 : 0)) /
                                extractionProgress.totalQuestions) * 100,
                              95
                            )}%`
                          }}
                        />
                      </div>

                      {/* Progress text */}
                      <div className="flex items-center justify-center gap-2">
                        <span className="text-2xl font-bold text-primary-600">
                          {extractionProgress.currentQuestion}
                        </span>
                        <span className="text-gray-400">/</span>
                        <span className="text-lg text-gray-500">
                          {extractionProgress.totalQuestions}
                        </span>
                        <span className="text-sm text-gray-400 mr-2">שאלות</span>
                      </div>

                      {/* Stage message */}
                      <p className="text-sm text-gray-500">
                        {getExtractionStageMessage(extractionProgress)}
                      </p>
                    </div>
                  )}

                  <p className="mt-6 text-xs text-gray-400">
                    החילוץ עשוי לקחת מספר דקות בהתאם למספר השאלות
                  </p>
                </div>
              </div>
            )}

            {rubricStep === 'review' && (
              <div className="animate-fade-in">
                <div className="bg-white rounded-xl shadow-lg p-6">
                  {/* Pass rubricPages and rubricMappings to RubricEditor */}
                  <RubricEditor
                    questions={extractedQuestions}
                    onQuestionsChange={setExtractedQuestions}
                    pages={rubricPages}
                    questionMappings={rubricMappings}
                  />
                  {error && <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{error}</div>}
                  <div className="mt-6 pt-4 border-t border-surface-200 flex items-center justify-between">
                    <BackButton onClick={() => setRubricStep('map')} />
                    <button onClick={handleSaveRubric} disabled={isLoading} className="flex items-center gap-2 bg-primary-500 text-white px-6 py-2 rounded-lg hover:bg-primary-600 disabled:opacity-50 transition-colors">
                      {isLoading ? <Loader2 className="animate-spin" size={18} /> : <Save size={18} />}
                      {isLoading ? 'שומר...' : 'שמור מחוון'}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {rubricStep === 'saved' && (
              <div className="max-w-xl mx-auto animate-fade-in">
                <div className="bg-white rounded-xl shadow-lg p-8 text-center">
                  <CheckCircle className="mx-auto text-primary-500 mb-4" size={64} />
                  <h2 className="text-2xl font-semibold text-primary-700">המחוון נשמר בהצלחה!</h2>
                  <p className="text-gray-500 mt-2">מזהה: <code className="bg-surface-100 px-2 py-1 rounded">{savedRubricId}</code></p>
                  <div className="mt-8 flex flex-col gap-3">
                    <button onClick={() => { setMainMode('grading'); setGradingStep('select_rubric'); }} className="flex items-center gap-2 mx-auto bg-primary-500 text-white px-6 py-2 rounded-lg hover:bg-primary-600">
                      <GraduationCap size={18} />המשך לבדיקת מבחנים
                    </button>
                    <button onClick={goToHome} className="text-gray-500 hover:text-gray-700 text-sm">חזור לדף הבית</button>
                  </div>
                </div>
              </div>
            )}
          </>
        )}

        {/* GRADING FLOW */}
        {mainMode === 'grading' && (
          <>
            {gradingStep === 'select_rubric' && (
              <div className="max-w-3xl mx-auto animate-fade-in">
                <div className="bg-white rounded-xl shadow-lg p-8">
                  <div className="text-center mb-6">
                    <BookOpen className="mx-auto text-primary-500 mb-3" size={48} />
                    <h2 className="text-xl font-semibold">בחירת מחוון</h2>
                    <p className="text-gray-500 mt-1">בחר מחוון קיים לבדיקת מבחנים</p>
                  </div>
                  <RubricSelector onSelect={handleRubricSelect} />
                  {error && <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm flex items-center gap-2"><AlertCircle size={18} />{error}</div>}
                </div>
              </div>
            )}

            {gradingStep === 'upload_batch' && selectedRubric && (
              <div className="max-w-2xl mx-auto animate-fade-in">
                <div className="bg-white rounded-xl shadow-lg p-8">
                  {/* Rubric info */}
                  <div className="mb-6 p-4 bg-primary-50 border border-primary-200 rounded-lg">
                    <h3 className="font-medium text-primary-800">{selectedRubric.name || 'מחוון ללא שם'}</h3>
                    <p className="text-sm text-primary-600">{selectedRubric.rubric_json.questions.length} שאלות · {selectedRubric.total_points} נקודות</p>
                  </div>

                  <div className="text-center mb-6">
                    <ClipboardCheck className="mx-auto text-primary-500 mb-3" size={48} />
                    <h2 className="text-xl font-semibold">העלאת מבחנים</h2>
                    <p className="text-gray-500 mt-1">העלה את כל מבחני התלמידים לבדיקה</p>
                  </div>

                  {/* First page index selector */}
                  <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                    <div className="flex items-center gap-2 text-sm">
                      <User size={16} className="text-blue-500" />
                      <span className="font-medium text-blue-700">עמוד שם התלמיד (בכל המבחנים):</span>
                      <select
                        value={firstPageIndex}
                        onChange={(e) => setFirstPageIndex(parseInt(e.target.value))}
                        className="bg-white border border-blue-300 rounded px-2 py-1 text-sm"
                      >
                        {[...Array(10)].map((_, i) => (
                          <option key={i} value={i}>עמוד {i + 1}</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <MultiFileUpload files={testFiles} onFilesChange={setTestFiles} label="העלה מבחני תלמידים" maxFiles={50} />

                  {error && <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{error}</div>}

                  <div className="mt-6 flex items-center justify-between">
                    <BackButton onClick={() => { setGradingStep('select_rubric'); setSelectedRubric(null); setTestFiles([]); }} />
                    <button
                      onClick={handleProceedToMapping}
                      disabled={testFiles.length === 0 || isLoading}
                      className="flex items-center gap-2 bg-primary-500 text-white px-6 py-2 rounded-lg hover:bg-primary-600 disabled:opacity-50 transition-colors"
                    >
                      המשך למיפוי תשובות
                      <ArrowLeft size={18} />
                    </button>
                  </div>
                </div>
              </div>
            )}

            {gradingStep === 'map_answers' && selectedRubric && currentTest && (
              <div className="animate-fade-in">
                {/* Progress indicator */}
                <div className="mb-4 bg-white rounded-xl shadow-sm p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-gray-700">מיפוי מבחן {currentTestIndex + 1} מתוך {testMappings.length}</span>
                    <span className="text-sm text-gray-500 truncate max-w-xs">{currentTest.file.name}</span>
                  </div>
                  <div className="w-full bg-surface-200 rounded-full h-2">
                    <div
                      className="bg-primary-500 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${((currentTestIndex + 1) / testMappings.length) * 100}%` }}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <div className="bg-white rounded-xl shadow-lg p-6">
                    <div className="flex items-center justify-between mb-4">
                      <h2 className="text-lg font-semibold">עמודי המבחן</h2>
                      <span className="text-sm text-gray-500">{currentTest.pages.length} עמודים</span>
                    </div>
                    {isLoading ? (
                      <div className="flex items-center justify-center py-12">
                        <Loader2 className="animate-spin text-primary-500" size={32} />
                      </div>
                    ) : (
                      <div className="max-h-[600px] overflow-y-auto">
                        <PageGrid pages={currentTest.pages} selections={getAnswerPageSelections()} onPageClick={handleAnswerPageClick} />
                      </div>
                    )}
                  </div>

                  <div className="bg-white rounded-xl shadow-lg p-6">
                    <AnswerMappingPanel
                      rubric={selectedRubric}
                      mappings={currentTest.answerMappings}
                      onMappingsChange={updateCurrentTestMappings}
                      activeAssignment={activeAnswerAssignment}
                      onSetActiveAssignment={setActiveAnswerAssignment}
                      firstPageIndex={firstPageIndex}
                      onFirstPageIndexChange={setFirstPageIndex}
                      hideFirstPageSelector={true}
                    />

                    {/* Navigation buttons */}
                    <div className="mt-6 flex items-center justify-between">
                      <BackButton onClick={handlePrevTest} />

                      <button
                        onClick={handleNextTest}
                        disabled={!isCurrentMappingValid || isLoading}
                        className="flex items-center gap-2 bg-primary-500 text-white px-6 py-2 rounded-lg hover:bg-primary-600 disabled:opacity-50 transition-colors"
                      >
                        {currentTestIndex < testMappings.length - 1 ? (
                          <>
                            המשך למבחן הבא
                            <ArrowLeft size={18} />
                          </>
                        ) : (
                          <>
                            <GraduationCap size={18} />
                            התחל בדיקה ({testMappings.length} מבחנים)
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {gradingStep === 'grading' && (
              <div className="max-w-xl mx-auto animate-fade-in">
                <div className="bg-white rounded-xl shadow-lg p-8 text-center">
                  <Loader2 className="mx-auto text-primary-500 mb-4 animate-spin" size={64} />
                  <h2 className="text-xl font-semibold text-gray-800">בודק מבחנים...</h2>

                  {gradingProgress && (
                    <div className="mt-6 space-y-3">
                      <div className="w-full bg-surface-200 rounded-full h-3 overflow-hidden">
                        <div
                          className="bg-primary-500 h-3 rounded-full transition-all duration-500 ease-out"
                          style={{ width: `${(gradingProgress.current / gradingProgress.total) * 100}%` }}
                        />
                      </div>

                      <div className="flex items-center justify-center gap-2">
                        <span className="text-2xl font-bold text-primary-600">{gradingProgress.current}</span>
                        <span className="text-gray-400">/</span>
                        <span className="text-lg text-gray-500">{gradingProgress.total}</span>
                        <span className="text-sm text-gray-400 mr-2">מבחנים נבדקו</span>
                      </div>

                      {gradingProgress.currentFileName && gradingProgress.current < gradingProgress.total && (
                        <p className="text-sm text-gray-400 truncate max-w-xs mx-auto">
                          בודק: {gradingProgress.currentFileName}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}

            {gradingStep === 'results' && (
              <div className="animate-fade-in">
                <div className="bg-white rounded-xl shadow-lg p-6">
                  <div className="flex items-center justify-between mb-6">
                    <h2 className="text-xl font-semibold">תוצאות הבדיקה</h2>
                    <button onClick={goToHome} className="flex items-center gap-2 text-gray-500 hover:text-primary-600 transition-colors">
                      <HomeIcon size={18} />
                      <span className="text-sm">לדף הבית</span>
                    </button>
                  </div>
                  <GradingResults results={gradingResults} totalTests={gradingStats.total} successful={gradingStats.successful} failed={gradingStats.failed} errors={gradingStats.errors} />
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}