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
import { SidebarLayout } from '@/components/SidebarLayout';
import TranscriptionReviewPage from '@/components/TranscriptionReviewPage';
import PdfProcessingPage from '@/components/PdfProcessingPage';
import { useStreamingTranscription } from '@/lib/useStreamingTranscription';
import {
  previewRubricPdf,
  extractRubric,
  saveRubric,
  previewStudentTestPdf,
  gradeSingleTest,
  gradeHandwrittenTest,
  transcribeHandwrittenTest,
  gradeWithTranscription,
  PagePreview,
  QuestionPageMapping,
  ExtractedQuestion,
  RubricListItem,
  AnswerPageMapping,
  GradedTestResult,
  TranscriptionReviewResponse,
  StudentAnswerInput,
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
  PenTool,
  Printer,
} from 'lucide-react';

type MainMode = 'select' | 'rubric' | 'grading';
type RubricStep = 'upload' | 'map' | 'extracting' | 'review' | 'saved';
// UPDATED: Added 'pdf_processing' step
type GradingStep = 'select_rubric' | 'upload_batch' | 'map_answers' | 'pdf_processing' | 'review_transcription' | 'grading' | 'results';
type TranscriptionMode = 'handwritten' | 'printed' | null;

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
  stage?: 'transcribing' | 'grading';
}

// Store mapping for each test
interface TestMapping {
  file: File;
  pages: PagePreview[];
  answerMappings: AnswerPageMapping[];
  isLoaded: boolean;
}

// Store per-test question selections for handwritten mode
interface HandwrittenTestConfig {
  file: File;
  answeredQuestions: number[]; // Which questions the student answered (empty = all)
}

// =============================================================================
// Transcription Mode Toggle Component
// =============================================================================

interface TranscriptionModeToggleProps {
  mode: TranscriptionMode;
  onChange: (mode: TranscriptionMode) => void;
}

function TranscriptionModeToggle({ mode, onChange }: TranscriptionModeToggleProps) {
  return (
    <div className="mb-6 p-4 bg-surface-50 border border-surface-200 rounded-lg">
      <label className="block text-sm font-medium text-gray-700 mb-3">
        סוג המבחנים לבדיקה <span className="text-red-500">*</span>
      </label>
      <div className="flex gap-3">
        <button
          onClick={() => onChange('handwritten')}
          className={`flex-1 flex items-center justify-center gap-2 p-4 rounded-lg border-2 transition-all ${mode === 'handwritten'
            ? 'border-primary-500 bg-primary-50 text-primary-700'
            : 'border-surface-300 bg-white text-gray-600 hover:border-surface-400'
            }`}
        >
          <PenTool size={20} />
          <span className="font-medium">תמלול כתב יד</span>
        </button>
        <button
          onClick={() => onChange('printed')}
          className={`flex-1 flex items-center justify-center gap-2 p-4 rounded-lg border-2 transition-all ${mode === 'printed'
            ? 'border-primary-500 bg-primary-50 text-primary-700'
            : 'border-surface-300 bg-white text-gray-600 hover:border-surface-400'
            }`}
        >
          <Printer size={20} />
          <span className="font-medium">תמלול דפוס</span>
        </button>
      </div>
      {!mode && (
        <p className="mt-2 text-sm text-amber-600 flex items-center gap-1">
          <AlertCircle size={14} />
          יש לבחור סוג מבחנים כדי להמשיך
        </p>
      )}
    </div>
  );
}

// =============================================================================
// Question Selection Component (for handwritten mode)
// =============================================================================

interface QuestionSelectionProps {
  rubric: RubricListItem;
  selectedQuestions: number[];
  onChange: (questions: number[]) => void;
  testName: string;
}

function QuestionSelection({ rubric, selectedQuestions, onChange, testName }: QuestionSelectionProps) {
  const allQuestions = rubric.rubric_json.questions.map(q => q.question_number);
  const allSelected = selectedQuestions.length === 0 || selectedQuestions.length === allQuestions.length;

  const toggleQuestion = (qNum: number) => {
    if (selectedQuestions.includes(qNum)) {
      onChange(selectedQuestions.filter(q => q !== qNum));
    } else {
      onChange([...selectedQuestions, qNum].sort((a, b) => a - b));
    }
  };

  const selectAll = () => {
    onChange([]); // Empty means all questions
  };

  return (
    <div className="p-3 bg-surface-50 rounded-lg border border-surface-200">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-gray-700 truncate max-w-[200px]" title={testName}>
          {testName}
        </span>
        <button
          onClick={selectAll}
          className={`text-xs px-2 py-1 rounded ${allSelected
            ? 'bg-primary-100 text-primary-700'
            : 'bg-surface-200 text-gray-600 hover:bg-surface-300'
            }`}
        >
          כל השאלות
        </button>
      </div>
      <div className="flex flex-wrap gap-2">
        {allQuestions.map(qNum => {
          const isSelected = allSelected || selectedQuestions.includes(qNum);
          return (
            <button
              key={qNum}
              onClick={() => toggleQuestion(qNum)}
              className={`px-3 py-1 text-sm rounded-full border transition-colors ${isSelected
                ? 'bg-primary-500 text-white border-primary-500'
                : 'bg-white text-gray-600 border-surface-300 hover:border-primary-300'
                }`}
            >
              שאלה {qNum}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// =============================================================================
// Back Button Component
// =============================================================================

function BackButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-2 text-gray-500 hover:text-gray-700"
    >
      חזור
      <ArrowRight size={18} />
    </button>
  );
}

// =============================================================================
// Main Component
// =============================================================================

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

  // Grading Flow State
  const [gradingStep, setGradingStep] = useState<GradingStep>('select_rubric');
  const [selectedRubric, setSelectedRubric] = useState<RubricListItem | null>(null);
  const [testFiles, setTestFiles] = useState<File[]>([]);
  const [studentName, setStudentName] = useState('');

  // Transcription mode
  const [transcriptionMode, setTranscriptionMode] = useState<TranscriptionMode>(null);

  // Per-test question selection for handwritten mode
  const [handwrittenConfigs, setHandwrittenConfigs] = useState<HandwrittenTestConfig[]>([]);

  // Per-test mapping state (for printed mode)
  const [testMappings, setTestMappings] = useState<TestMapping[]>([]);
  const [currentTestIndex, setCurrentTestIndex] = useState(0);
  const [activeAnswerAssignment, setActiveAnswerAssignment] = useState<ActiveAnswerAssignment | null>(null);

  // Grading results
  const [gradingResults, setGradingResults] = useState<GradedTestResult[]>([]);
  const [gradingStats, setGradingStats] = useState({ total: 0, successful: 0, failed: 0, errors: [] as string[] });
  const [gradingProgress, setGradingProgress] = useState<GradingProgress | null>(null);
  // Store test page thumbnails for validation in results view
  const [testPagesMap, setTestPagesMap] = useState<Map<string, PagePreview[]>>(new Map());

  // Current test file being processed (for handwritten mode)
  const [currentTestFile, setCurrentTestFile] = useState<File | null>(null);

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // =============================================================================
  // NEW: Streaming Transcription Hook
  // =============================================================================
  const streaming = useStreamingTranscription({
    // Called when PDF processing is complete and pages are ready
    // This triggers navigation from loading screen to review page
    onPagesReady: ({ pages, studentName, filename }) => {
      console.log(`PDF processed: ${pages} pages, student: ${studentName}`);
      // Navigate to review page
      setGradingStep('review_transcription');
    },
    onComplete: (data) => {
      console.log('Transcription complete:', data.student_name, data.answers.length, 'answers');
    },
    onError: (err) => {
      console.error('Streaming error:', err);
      setError(err);
      // Go back to upload step on error
      setGradingStep('upload_batch');
    },
  });

  // Current test being mapped (printed mode)
  const currentTest = testMappings[currentTestIndex];

  // Initialize handwritten configs when files change
  useEffect(() => {
    if (transcriptionMode === 'handwritten' && testFiles.length > 0) {
      setHandwrittenConfigs(
        testFiles.map(file => ({
          file,
          answeredQuestions: [], // Empty = all questions
        }))
      );
    }
  }, [testFiles, transcriptionMode]);

  // Reset transcription mode when going back to rubric selection
  const handleBackToRubricSelect = () => {
    streaming.reset();
    setGradingStep('select_rubric');
    setSelectedRubric(null);
    setTestFiles([]);
    setTranscriptionMode(null);
    setHandwrittenConfigs([]);
  };

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

  const handleExtractRubric = async () => {
    if (!rubricFile || !canExtractRubric) return;
    setRubricStep('extracting');
    setIsLoading(true);
    setError(null);
    try {
      const response = await extractRubric(rubricFile, { name: rubricName || undefined, question_mappings: rubricMappings });
      setExtractedQuestions(response.questions);
      setRubricStep('review');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'שגיאה בחילוץ המחוון');
      setRubricStep('map');
    } finally {
      setIsLoading(false);
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

  // Handle proceed based on transcription mode
  const handleProceedFromUpload = async () => {
    if (testFiles.length === 0 || !transcriptionMode) return;

    if (transcriptionMode === 'handwritten') {
      // Skip page mapping, start streaming transcription
      await handleGradeHandwritten();
    } else {
      // Printed mode - go to page mapping
      await handleProceedToMapping();
    }
  };


  // =============================================================================
  // NEW: Handwritten transcription with two-phase streaming
  // Flow: Upload → PDF Processing Page → Review Page (with streaming)
  // =============================================================================
  const handleGradeHandwritten = async () => {
    if (!selectedRubric || handwrittenConfigs.length === 0) return;

    // For now, process first test only (can be extended to batch later)
    const config = handwrittenConfigs[0];

    setCurrentTestFile(config.file);
    setError(null);

    // Step 1: Show PDF processing loading page
    setGradingStep('pdf_processing');

    // Step 2: Start streaming transcription
    // The hook will call onPagesReady when PDF is processed, which navigates to review page
    streaming.startTranscription(selectedRubric.id, config.file, {
      firstPageIndex: 0,
      answeredQuestions: config.answeredQuestions.length > 0 ? config.answeredQuestions : undefined,
    });
  };

  // Handle continue from transcription review (grade with edited answers)
  const handleContinueFromReview = async (editedAnswers: StudentAnswerInput[]) => {
    if (!selectedRubric || !streaming.transcriptionData || !currentTestFile) return;

    setGradingStep('grading');
    setGradingProgress({
      current: 1,
      total: handwrittenConfigs.length,
      currentFileName: currentTestFile.name,
      stage: 'grading'
    });

    try {
      // Call grade_with_transcription endpoint
      const result = await gradeWithTranscription({
        rubric_id: selectedRubric.id,
        student_name: streaming.transcriptionData.student_name,
        filename: streaming.transcriptionData.filename,
        answers: editedAnswers,
      });

      // Store page thumbnails for results view
      const pagesMap = new Map<string, PagePreview[]>();
      pagesMap.set(streaming.transcriptionData.filename, streaming.transcriptionData.pages);
      setTestPagesMap(pagesMap);

      setGradingResults([result]);
      setGradingStats({ total: 1, successful: 1, failed: 0, errors: [] });
      setGradingProgress(null);
      setGradingStep('results');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'שגיאה בהערכת המבחן');
      setGradingProgress(null);
      setGradingStep('review_transcription');
    }
  };

  // Handle back from PDF processing - return to upload
  const handleBackFromPdfProcessing = () => {
    streaming.abort();
    streaming.reset();
    setCurrentTestFile(null);
    setGradingStep('upload_batch');
  };

  // Handle back from review - return to upload
  const handleBackFromReview = () => {
    streaming.abort();
    streaming.reset();
    setCurrentTestFile(null);
    setGradingStep('upload_batch');
  };


  // Initialize test mappings when files are uploaded and user proceeds (printed mode)
  const handleProceedToMapping = async () => {
    if (testFiles.length === 0) return;

    const initialMappings: TestMapping[] = testFiles.map(file => ({
      file,
      pages: [],
      answerMappings: [],
      isLoaded: false,
    }));

    setTestMappings(initialMappings);
    setCurrentTestIndex(0);
    setGradingStep('map_answers');

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

  // Update handwritten config for a specific test
  const updateHandwrittenConfig = (index: number, answeredQuestions: number[]) => {
    setHandwrittenConfigs(prev => {
      const updated = [...prev];
      updated[index] = { ...updated[index], answeredQuestions };
      return updated;
    });
  };

  // Navigation for printed mode
  const handlePrevTest = () => {
    if (currentTestIndex > 0) {
      setCurrentTestIndex(currentTestIndex - 1);
      setActiveAnswerAssignment(null);
    } else {
      setGradingStep('upload_batch');
      setTestMappings([]);
    }
  };

  const handleNextTest = async () => {
    if (currentTestIndex < testMappings.length - 1) {
      const nextIndex = currentTestIndex + 1;
      setCurrentTestIndex(nextIndex);
      setActiveAnswerAssignment(null);
      await loadTestPages(nextIndex, testMappings);
    } else {
      await handleStartGrading();
    }
  };

  // Start grading (printed mode)
  const handleStartGrading = async () => {
    if (!selectedRubric) return;

    setGradingStep('grading');
    setGradingProgress({ current: 0, total: testMappings.length, currentFileName: '' });

    const results: GradedTestResult[] = [];
    const errors: string[] = [];
    let successful = 0;
    let failed = 0;

    for (let i = 0; i < testMappings.length; i++) {
      const testMapping = testMappings[i];
      setGradingProgress({
        current: i + 1,
        total: testMappings.length,
        currentFileName: testMapping.file.name,
      });

      try {
        const result = await gradeSingleTest(
          selectedRubric.id,
          testMapping.answerMappings,
          testMapping.file,
          0  // firstPageIndex no longer used
        );
        results.push(result);
        successful++;
      } catch (err) {
        const errorMsg = `${testMapping.file.name}: ${err instanceof Error ? err.message : 'שגיאה לא ידועה'}`;
        errors.push(errorMsg);
        failed++;
      }
    }

    setGradingResults(results);
    setGradingStats({ total: testMappings.length, successful, failed, errors });
    setGradingProgress(null);
    setGradingStep('results');
  };

  // Answer page click handler (printed mode)
  const handleAnswerPageClick = useCallback((pageIndex: number) => {
    if (!activeAnswerAssignment || !currentTest) return;

    const newMappings = [...currentTest.answerMappings];
    const mapping = newMappings[activeAnswerAssignment.mappingIndex];
    if (!mapping) return;

    const idx = mapping.page_indexes.indexOf(pageIndex);
    if (idx >= 0) {
      mapping.page_indexes.splice(idx, 1);
    } else {
      mapping.page_indexes.push(pageIndex);
      mapping.page_indexes.sort((a, b) => a - b);
    }

    updateCurrentTestMappings(newMappings);
  }, [activeAnswerAssignment, currentTest]);

  const updateCurrentTestMappings = (newMappings: AnswerPageMapping[]) => {
    setTestMappings(prev => {
      const updated = [...prev];
      updated[currentTestIndex] = {
        ...updated[currentTestIndex],
        answerMappings: newMappings,
      };
      return updated;
    });
  };

  const getAnswerPageSelections = useCallback(() => {
    if (!currentTest) return new Map();
    const selections = new Map<number, { label: string; color: string }>();
    currentTest.answerMappings.forEach((mapping) => {
      mapping.page_indexes.forEach((pageIdx) => {
        const existing = selections.get(pageIdx);
        let label = `ש${mapping.question_number}`;
        if (mapping.sub_question_id) label += mapping.sub_question_id;
        selections.set(pageIdx, {
          label: existing ? `${existing.label}, ${label}` : label,
          color: 'bg-green-500',
        });
      });
    });
    return selections;
  }, [currentTest]);

  const isCurrentMappingValid = currentTest?.answerMappings.every(m => m.page_indexes.length > 0) ?? false;

  const goToHome = () => {
    streaming.reset();
    setMainMode('select');
    setRubricStep('upload');
    setGradingStep('select_rubric');
    setRubricFile(null);
    setRubricPages([]);
    setRubricMappings([]);
    setExtractedQuestions([]);
    setSelectedRubric(null);
    setTestFiles([]);
    setTestMappings([]);
    setGradingResults([]);
    setTranscriptionMode(null);
    setHandwrittenConfigs([]);
    setCurrentTestFile(null);
    setError(null);
  };

  // Can proceed from upload page
  const canProceedFromUpload = testFiles.length > 0 && transcriptionMode !== null;

  return (
    <SidebarLayout>
      <div className="max-w-7xl mx-auto">
        {/* MODE SELECTION */}
        {mainMode === 'select' && (
          <div className="max-w-3xl mx-auto animate-fade-in">
            <div className="text-center mb-8">
              <h2 className="text-3xl font-bold text-gray-800 mb-2">במה אני יכולה לעזור?</h2>
              <p className="text-gray-500"> בחרי את הפעולה הרצויה</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <button
                onClick={() => setMainMode('rubric')}
                className="bg-white rounded-xl shadow-lg p-8 text-center hover:shadow-xl hover:scale-[1.02] transition-all group"
              >
                <div className="bg-primary-100 text-primary-600 p-4 rounded-full w-fit mx-auto mb-4 group-hover:bg-primary-200 transition-colors">
                  <BookOpen size={32} />
                </div>
                <h3 className="text-xl font-semibold text-gray-800 mb-2">העלאת מחוון חדש</h3>
                <p className="text-gray-500 text-sm">העלי PDF של מחוון וחלץ את הקריטריונים</p>
              </button>
              <button
                onClick={() => setMainMode('grading')}
                className="bg-white rounded-xl shadow-lg p-8 text-center hover:shadow-xl hover:scale-[1.02] transition-all group"
              >
                <div className="bg-[#aa77f7]/20 text-[#aa77f7] p-4 rounded-full w-fit mx-auto mb-4 group-hover:bg-[#aa77f7]/30 transition-colors">
                  <GraduationCap size={32} />
                </div>
                <h3 className="text-xl font-semibold text-gray-800 mb-2">בדיקת מבחנים</h3>
                <p className="text-gray-500 text-sm">בדקי מבחני תלמידים עם מחוון קיים</p>
              </button>
            </div>
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
                    <p className="text-gray-500 mt-1">העלי קובץ PDF של המחוון</p>
                  </div>
                  <FileUpload file={rubricFile} onFileChange={handleRubricFileChange} accept=".pdf" label="גרור קובץ PDF לכאן או לחץ לבחירה" />
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

            {rubricStep === 'extracting' && (
              <div className="max-w-xl mx-auto animate-fade-in">
                <div className="bg-white rounded-xl shadow-lg p-8 text-center">
                  <Loader2 className="mx-auto text-primary-500 mb-4 animate-spin" size={64} />
                  <h2 className="text-xl font-semibold text-gray-800">מחלץ מחוון...</h2>
                  <p className="text-gray-500 mt-2">אנא המתיני בזמן שהמערכת מחלצת את המחוון</p>
                </div>
              </div>
            )}

            {rubricStep === 'review' && (
              <div className="animate-fade-in">
                <div className="bg-white rounded-xl shadow-lg p-6">
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
                    <p className="text-gray-500 mt-1">בחרי מחוון קיים לבדיקת מבחנים</p>
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
                    <p className="text-gray-500 mt-1">העלי את כל מבחני התלמידים לבדיקה</p>
                  </div>

                  {/* Transcription mode toggle */}
                  <TranscriptionModeToggle
                    mode={transcriptionMode}
                    onChange={setTranscriptionMode}
                  />

                  {/* Student name input */}
                  <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                    <div className="flex items-center gap-2 text-sm">
                      <User size={16} className="text-blue-500" />
                      <span className="font-medium text-blue-700">שם התלמיד:</span>
                      <input
                        type="text"
                        value={studentName}
                        onChange={(e) => setStudentName(e.target.value)}
                        placeholder="הכנס שם תלמיד"
                        className="bg-white border border-blue-300 rounded px-3 py-1 text-sm flex-1"
                        dir="rtl"
                      />
                    </div>
                  </div>

                  <MultiFileUpload files={testFiles} onFilesChange={setTestFiles} label="העלי מבחני תלמידים" maxFiles={50} />

                  {/* Question selection for handwritten mode */}
                  {transcriptionMode === 'handwritten' && testFiles.length > 0 && (
                    <div className="mt-4 p-4 bg-amber-50 border border-amber-200 rounded-lg">
                      <div className="flex items-center gap-2 mb-3">
                        <PenTool size={16} className="text-amber-600" />
                        <span className="font-medium text-amber-800">בחירת שאלות לכל מבחן (אופציונלי)</span>
                      </div>
                      <p className="text-sm text-amber-700 mb-3">
                        אם התלמיד לא ענה על כל השאלות, בחר את השאלות שהוא ענה עליהן. השאר ריק אם ענה על כולן.
                      </p>
                      <div className="space-y-2 max-h-48 overflow-y-auto">
                        {handwrittenConfigs.map((config, index) => (
                          <QuestionSelection
                            key={index}
                            rubric={selectedRubric}
                            selectedQuestions={config.answeredQuestions}
                            onChange={(questions) => updateHandwrittenConfig(index, questions)}
                            testName={config.file.name}
                          />
                        ))}
                      </div>
                    </div>
                  )}

                  {error && <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{error}</div>}

                  <div className="mt-6 flex items-center justify-between">
                    <BackButton onClick={handleBackToRubricSelect} />
                    <button
                      onClick={handleProceedFromUpload}
                      disabled={!canProceedFromUpload || isLoading}
                      className="flex items-center gap-2 bg-primary-500 text-white px-6 py-2 rounded-lg hover:bg-primary-600 disabled:opacity-50 transition-colors"
                    >
                      {transcriptionMode === 'handwritten' ? (
                        <>
                          <GraduationCap size={18} />
                          התחל בדיקה ({testFiles.length} מבחנים)
                        </>
                      ) : (
                        <>
                          המשך למיפוי תשובות
                          <ArrowLeft size={18} />
                        </>
                      )}
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
                      firstPageIndex={0}
                      onFirstPageIndexChange={() => { }}
                      hideFirstPageSelector={true}
                    />

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

            {/* NEW: PDF Processing step - show loading while PDF is being parsed */}
            {gradingStep === 'pdf_processing' && currentTestFile && (
              <PdfProcessingPage
                filename={currentTestFile.name}
                onPagesReady={() => setGradingStep('review_transcription')}
                onError={(msg) => {
                  setError(msg);
                  setGradingStep('upload_batch');
                }}
                progress={{
                  currentPage: streaming.pagesReceived,
                  totalPages: streaming.totalPages,
                }}
              />
            )}

            {/* Review transcription step - show TranscriptionReviewPage with streaming */}
            {gradingStep === 'review_transcription' && selectedRubric && currentTestFile && (
              <TranscriptionReviewPage
                rubricId={selectedRubric.id}
                testFile={currentTestFile}
                answeredQuestions={handwrittenConfigs[0]?.answeredQuestions}
                studentName={studentName}
                onContinueToGrading={handleContinueFromReview}
                onBack={handleBackFromReview}
                isGrading={false}
                externalStreamState={streaming.state}
                externalTranscriptionData={streaming.transcriptionData}
              />
            )}

            {(gradingStep === 'grading') && (
              <div className="max-w-xl mx-auto animate-fade-in">
                <div className="bg-white rounded-xl shadow-lg p-8 text-center">
                  <Loader2 className="mx-auto text-primary-500 mb-4 animate-spin" size={64} />
                  <h2 className="text-xl font-semibold text-gray-800">
                    בודק מבחנים...
                  </h2>

                  {gradingProgress && (
                    <div className="mt-6 space-y-3">
                      <div className="w-full bg-surface-200 rounded-full h-3 overflow-hidden">
                        <div
                          className="bg-primary-500 h-3 transition-all duration-300"
                          style={{ width: `${(gradingProgress.current / gradingProgress.total) * 100}%` }}
                        />
                      </div>
                      <p className="text-sm text-gray-600">
                        {gradingProgress.current} / {gradingProgress.total}
                      </p>
                      <p className="text-xs text-gray-400 truncate">
                        {gradingProgress.currentFileName}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            )}


            {gradingStep === 'results' && (
              <div className="animate-fade-in">
                <GradingResults
                  results={gradingResults}
                  stats={gradingStats}
                  onBack={goToHome}
                  testPages={testPagesMap}
                />
              </div>
            )}
          </>
        )}
      </div>
    </SidebarLayout>
  );
}