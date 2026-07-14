'use client';

import { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { FileUpload } from '@/components/FileUpload';
import { MultiFileUpload } from '@/components/MultiFileUpload';
import { PageGrid } from '@/components/PageThumbnail';
import { RubricEditor } from '@/components/RubricEditor';
import { AnswerMappingPanel } from '@/components/AnswerMappingPanel';
import { GradingResults } from '@/components/GradingResults';
import { RubricSelector } from '@/components/RubricSelector';
import { SidebarLayout } from '@/components/SidebarLayout';
import PdfProcessingPage from '@/components/PdfProcessingPage';
import { TranscriptionReviewPanel } from '@/components/TranscriptionReviewPanel';
import { GradedTestReviewPanel } from '@/components/GradedTestReviewPanel';
import { useStreamingTranscription } from '@/lib/useStreamingTranscription';
import {
  saveOntologyRubric,
  isWarningsResponse,
  previewStudentTestPdf,
  PagePreview,
  RubricListItem,
  AnswerPageMapping,
  GradedTestResult,
  StudentAnswerInput,
  isDocxFile,
  ExtractionMetadata,
  Annotation,
  transcribe,
  submitGrade,
  getGradedTest,
  listClasses,
  createBatch,
  // PR-1: async extraction jobs (submit → poll → result → retry)
  submitExtractionJob,
  getExtractionJobResult,
  retryExtractionJob,
  listExtractionJobs,
  ExtractRubricResponse,
  RubricSaveError,
  type SelectionGroup,
} from '@/lib/api';
import { useExtractionJob, getExtractionStageLabel } from '@/hooks/useExtractionJob';
import { toast } from 'sonner';
import { ApiAuthError } from '@/lib/api';
import { authErrorMessage, toMessage } from '@/lib/errorSurface';
import {
  clearUnsavedWork,
  peekUnsavedWork,
  stashUnsavedWork,
  type UnsavedWork,
} from '@/lib/session';
import type { TranscribeResponse } from '@/types/transcription';
import type { GradedTestDraftResponse } from '@/types/graded_test';
import type { DocxPreflightQuestion } from '@/lib/api';
import { RubricPurpose, RubricPurposeValues } from '@/components/RubricPurpose';
import { RubricErrorDisplay } from '@/components/RubricSaveFlow';
import type { RubricQuestion } from '@/types/rubric';
import { hydrateAnyQuestions, dehydrateQuestions } from '@/utils/rubric-transform';
import { validateAllQuestions, validateRubricTotalPoints } from '@/utils/rubric-validation';
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
  X,
} from 'lucide-react';

type MainMode = 'select' | 'rubric' | 'grading';
type RubricStep = 'upload' | 'purpose' | 'extracting' | 'review' | 'saved';
type GradingStep = 'select_rubric' | 'upload_batch' | 'map_answers' | 'pdf_processing' | 'review_transcription' | 'grading_queued' | 'grading' | 'results' | 'draft_review' | 'grading_failed';
type TranscriptionMode = 'handwritten' | 'printed' | null;

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
  const allQuestions: number[] = [];
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
  const [extractedQuestions, setExtractedQuestions] = useState<RubricQuestion[]>([]);
  // Rubric-level declared total — the fixed anchor INV-R3 validates against.
  // Set from response.total_points at extraction time. Without this anchor,
  // INV-R3 degenerates to "Σ q.total_points equals itself" and never fires.
  const [rubricDeclaredTotal, setRubricDeclaredTotal] = useState<number | undefined>(undefined);
  // PR-3: "choose k of N" groups from the extraction. These MUST survive the round trip:
  // total_points is the ACHIEVABLE total, and the backend recomputes achievable from the
  // groups. Send the total without the groups and it recomputes the full OFFERED sum
  // instead, then rejects the rubric on INV-4 — which is exactly why a selection exam
  // could never be saved before this.
  const [selectionGroups, setSelectionGroups] = useState<SelectionGroup[]>([]);
  const [rubricName, setRubricName] = useState('');
  const [savedRubricId, setSavedRubricId] = useState<string | null>(null);
  // DOCX pipeline state
  const [extractionMetadata, setExtractionMetadata] = useState<ExtractionMetadata | null>(null);
  const [extractionAnnotations, setExtractionAnnotations] = useState<Annotation[]>([]);
  // Save-blocking: ref passed to RubricEditor so the blocked save button can scroll to the error banner
  const errorBannerRef = useRef<HTMLDivElement>(null);
  const [programmingLanguage, setProgrammingLanguage] = useState<string>('Java');
  // Preflight / purpose-input state (DOCX only)
  const [preflightQuestions, setPreflightQuestions] = useState<DocxPreflightQuestion[]>([]);
  const [preflightDetectedTitle, setPreflightDetectedTitle] = useState<string | null>(null);
  /** Held across the preflight → purpose → extraction steps so we don't ask the user to re-pick */
  const [pendingDocxFile, setPendingDocxFile] = useState<File | null>(null);

  // Grading Flow State
  const [gradingStep, setGradingStep] = useState<GradingStep>('select_rubric');
  const [selectedRubric, setSelectedRubric] = useState<RubricListItem | null>(null);
  const [testFiles, setTestFiles] = useState<File[]>([]);
  const [studentName, setStudentName] = useState('');

  // S11: Batch upload state
  const router = useRouter();
  const [batchClassId, setBatchClassId] = useState<string | null>(null);
  const [batchClasses, setBatchClasses] = useState<{ id: string; name: string }[]>([]);
  const [batchUploading, setBatchUploading] = useState(false);

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

  // S4 blocking transcription flow
  const [transcribeResponse, setTranscribeResponse] = useState<TranscribeResponse | null>(null);
  const [submittingGrade, setSubmittingGrade] = useState(false);

  // S8 grading polling + draft-review
  const [gradedTestId, setGradedTestId] = useState<string | null>(null);
  const [pollingActive, setPollingActive] = useState(false);
  const [gradedTestDetail, setGradedTestDetail] = useState<GradedTestDraftResponse | null>(null);
  const [gradingError, setGradingError] = useState<string | null>(null);

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  /** PR-3: structured compile rejection (node + invariant + expected/actual + Hebrew). */
  const [saveError, setSaveError] = useState<RubricSaveError | null>(null);

// ---------------------------------------------------------------------------
  // Extraction error modal
  // ---------------------------------------------------------------------------
  const [errorModal, setErrorModal] = useState<{
    title: string;
    message: string;
    details?: string;
  } | null>(null);

  /** Map raw backend errors to friendly Hebrew messages */
  function translateExtractionError(raw: string): { title: string; message: string; details?: string } {
    // Test document without rubric (total_points=0)
    if (raw.includes('total_points') && raw.includes('greater_than')) {
      return {
        title: 'לא נמצא מחוון בקובץ',
        message: 'נראה שהקובץ שהועלה הוא מבחן ללא טבלת מחוון (ללא קריטריונים וניקוד). כדי לחלץ מחוון, העלי קובץ שמכיל טבלאות ניקוד.',
      };
    }
    // Empty document / parse failure
    if (raw.includes('Failed to parse DOCX') || raw.includes('Empty file')) {
      return {
        title: 'שגיאה בקריאת הקובץ',
        message: 'לא הצלחנו לקרוא את הקובץ. ודאי שמדובר בקובץ DOCX תקין ולא פגום.',
      };
    }
    // LLM / API failure
    if (raw.includes('Pipeline failed') || raw.includes('LLM') || raw.includes('openai') || raw.includes('anthropic')) {
      return {
        title: 'שגיאה בעיבוד המחוון',
        message: 'אירעה שגיאה בעת ניתוח המחוון. נסי שוב בעוד מספר שניות.',
        details: raw,
      };
    }
    // Fallback — show raw message with friendly wrapper
    return {
      title: 'שגיאה בחילוץ המחוון',
      message: 'אירעה שגיאה לא צפויה. אם הבעיה חוזרת, פני לתמיכה.',
      details: raw,
    };
  }

  // =============================================================================
  // S8: Grading poll loop — fires when pollingActive + gradedTestId are set
  // =============================================================================
  useEffect(() => {
    if (!pollingActive || !gradedTestId) return;
    let stopped = false;
    const startTime = Date.now();
    const POLL_INTERVAL_MS = 2500;
    const TIMEOUT_MS = 5 * 60 * 1000;

    const poll = async () => {
      while (!stopped) {
        await new Promise(r => setTimeout(r, POLL_INTERVAL_MS));
        if (stopped) break;
        if (Date.now() - startTime > TIMEOUT_MS) {
          setGradingError('הבדיקה לוקחת זמן רב מהרגיל — נסה לרענן את הדף');
          setPollingActive(false);
          setGradingStep('grading_failed');
          break;
        }
        try {
          const detail = await getGradedTest(gradedTestId);
          if (detail.status === 'draft' || detail.status === 'approved') {
            setGradedTestDetail(detail as GradedTestDraftResponse);
            setPollingActive(false);
            setGradingStep('draft_review');
          } else if (detail.status === 'failed') {
            setGradingError((detail as { error_message?: string }).error_message ?? 'שגיאה בבדיקה');
            setPollingActive(false);
            setGradingStep('grading_failed');
          }
          // pending / grading → keep polling
        } catch {
          // network blip — keep polling
        }
      }
    };
    void poll();
    return () => { stopped = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pollingActive, gradedTestId]);

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
    setExtractionMetadata(null);
    setExtractionAnnotations([]);

    if (!file) return;

    if (!isDocxFile(file)) {
      setError('סוג קובץ לא נתמך. אנא העלי קובץ DOCX.');
      return;
    }

    setIsLoading(true);
    setPendingDocxFile(file);
    setPreflightQuestions([]);
    setPreflightDetectedTitle(null);
    setRubricStep('purpose');
    setIsLoading(false);
  };

  // ---------------------------------------------------------------------------
  // DOCX extraction core (PR-1: async job — submit → poll → result)
  // ---------------------------------------------------------------------------
  const [extractionJobId, setExtractionJobId] = useState<string | null>(null);
  const [extractionRetrying, setExtractionRetrying] = useState(false);

  /** Shared post-processing: identical for the live flow and the resume flow. */
  const applyExtractionResult = useCallback((response: ExtractRubricResponse) => {
    setExtractedQuestions(hydrateAnyQuestions(response.questions));
    // Anchor INV-R3 against the document-declared total. Without this,
    // the validator has nothing to compare against. response.total_points
    // is top-level on ExtractRubricResponse (defaults to 100 per backend INV-4
    // when the source document has no explicit total).
    setRubricDeclaredTotal(response.total_points);
    setSelectionGroups(response.selection_groups ?? []);
    setExtractionMetadata(response.metadata || null);
    setExtractionAnnotations(response.annotations || []);
    if (response.name) setRubricName(response.name);
    setRubricStep('review');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // PR-2 (C10): stash the teacher's in-progress REVIEW EDITS before any forced
  // logout. The extraction RESULT is already durable server-side (PR-1's job row);
  // what is irreplaceable is the editing the teacher did on top of it.
  const stashReviewWork = useCallback(() => {
    if (rubricStep !== 'review' || extractedQuestions.length === 0) return;
    stashUnsavedWork({
      kind: 'rubric_review',
      rubricName,
      questions: extractedQuestions,
      annotations: extractionAnnotations,
      declaredTotal: rubricDeclaredTotal ?? null,
      selectionGroups,
      extractionJobId,
    });
  }, [rubricStep, extractedQuestions, rubricName, extractionAnnotations,
      rubricDeclaredTotal, extractionJobId]);

  const handleAuthFailure = useCallback(() => {
    stashReviewWork();
    toast.error(authErrorMessage());
  }, [stashReviewWork]);

  const extractionJob = useExtractionJob(extractionJobId, {
    onComplete: async () => {
      if (!extractionJobId) return;
      try {
        const jobResult = await getExtractionJobResult(extractionJobId);
        applyExtractionResult(jobResult.result);
      } catch (err) {
        setErrorModal(translateExtractionError(toMessage(err)));
        setRubricStep('upload');
      }
    },
    // failed / stale: stay on the extracting step — it renders the error state
    // with a wired retry (the job + source doc are durable server-side).
    onAuthError: () => {
      handleAuthFailure();
      setError('פג תוקף ההתחברות — יש להתחבר מחדש ואז לחזור לעמוד זה. החילוץ ממשיך ברקע.');
    },
  });

  // Restore offer: if a previous session was cut short mid-review, the edits are
  // in the stash. Offer them back exactly once, on mount.
  const [restorable, setRestorable] = useState<UnsavedWork | null>(null);
  useEffect(() => {
    const stashed = peekUnsavedWork();
    if (stashed) setRestorable(stashed);
  }, []);

  const restoreStashedWork = useCallback(() => {
    if (!restorable) return;
    setExtractedQuestions(hydrateAnyQuestions(restorable.questions as never));
    if (restorable.rubricName) setRubricName(restorable.rubricName);
    if (restorable.declaredTotal != null) setRubricDeclaredTotal(restorable.declaredTotal);
    setSelectionGroups((restorable.selectionGroups as SelectionGroup[]) ?? []);
    if (restorable.extractionJobId) setExtractionJobId(restorable.extractionJobId);
    setExtractionAnnotations((restorable.annotations as Annotation[]) || []);
    clearUnsavedWork();
    setRestorable(null);
    setMainMode('rubric');
    setRubricStep('review');
    toast.success('העבודה שלא נשמרה שוחזרה');
  }, [restorable]);

  const discardStashedWork = useCallback(() => {
    clearUnsavedWork();
    setRestorable(null);
  }, []);

  const _runDocxExtraction = async (
    file: File,
    purposes: RubricPurposeValues,
  ) => {
    setRubricStep('extracting');
    setIsLoading(true);
    setError(null);
    try {
      const submitted = await submitExtractionJob(file, {
        name: rubricName || file.name.replace(/\.docx$/i, ''),
        subject: 'computer_science',
        locale: 'he-IL',
        questionPurposes: Object.keys(purposes.questionPurposes).length > 0
          ? purposes.questionPurposes
          : undefined,
        testTopic: purposes.testTopic || undefined,
      });
      // Double-click / re-upload of the same doc converges on the same job
      // (reused=true) — the hook picks it up either way.
      setExtractionJobId(submitted.job_id);
    } catch (err) {
      const raw = err instanceof Error ? err.message : 'שגיאה בחילוץ המחוון מ-DOCX';
      setErrorModal(translateExtractionError(raw));
      setRubricStep('upload');
    } finally {
      setIsLoading(false);
    }
  };

  /** Retry a failed/stale job — the source DOCX is stored server-side, no re-upload. */
  const handleExtractionRetry = async () => {
    if (!extractionJobId) return;
    setExtractionRetrying(true);
    setError(null);
    try {
      await retryExtractionJob(extractionJobId);
      extractionJob.start();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'שגיאה בניסיון חוזר');
    } finally {
      setExtractionRetrying(false);
    }
  };

  /** Abandon the extracting view (the job keeps running server-side; the
   * resume effect below re-attaches to it on the next visit). */
  const handleExtractionBack = () => {
    extractionJob.stop();
    setExtractionJobId(null);
    setRubricStep('upload');
  };

  // Resume: an in-flight extraction survives leaving the page — on mount,
  // re-attach to the most recent active job and re-enter the extracting step.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const active = await listExtractionJobs({ active: true, limit: 1 });
        if (!cancelled && active.length > 0) {
          const job = active[0];
          setExtractionJobId(job.job_id);
          setMainMode('rubric');
          setRubricStep('extracting');
        }
      } catch {
        // Resume is best-effort — never block the page on it.
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handlePurposeConfirm = async (values: RubricPurposeValues) => {
    if (!pendingDocxFile) return;
    await _runDocxExtraction(pendingDocxFile, values);
  };

  const handlePurposeSkip = async () => {
    if (!pendingDocxFile) return;
    await _runDocxExtraction(pendingDocxFile, { testTopic: '', questionPurposes: {} });
  };

  // Combined annotations: backend extraction annotations + live validation
  // errors converted to Annotation shape. The unified source of truth for
  // save-blocking — `hasBlockingErrors` (below) reads from this.
  //
  // Live validators wired here:
  //   - validateAllQuestions → INV-R1, INV-R1b, INV-R2 (per question / per criterion)
  //   - validateRubricTotalPoints → INV-R3 (rubric-level, target_id: 'rubric' → global banner)
  const combinedAnnotations: Annotation[] = useMemo(() => {
    const liveAnnotations: Annotation[] = [];

    // INV-R1, INV-R1b, INV-R2 — per question / per criterion
    const liveIssues = validateAllQuestions(extractedQuestions);
    liveIssues.forEach((issues) => {
      issues.forEach((issue) => {
        liveAnnotations.push({
          annotation_type: 'invariant_violation',
          severity: issue.severity,
          message: issue.message,
          target_id: issue.target_id,
          id: issue.key,
        });
      });
    });

    // INV-R3 — rubric-level total. Gated on rubricDeclaredTotal being set
    // (it is, from extraction time onward — see _runDocxExtraction).
    if (rubricDeclaredTotal !== undefined) {
      const r3 = validateRubricTotalPoints(extractedQuestions, rubricDeclaredTotal);
      if (r3) {
        liveAnnotations.push({
          annotation_type: 'invariant_violation',
          severity: r3.severity,
          message: r3.message,
          target_id: r3.target_id, // 'rubric' — see validateRubricTotalPoints
          id: r3.key,
        });
      }
    }

    return [...extractionAnnotations, ...liveAnnotations];
  }, [extractedQuestions, extractionAnnotations, rubricDeclaredTotal]);

  const hasBlockingErrors = combinedAnnotations.some(a => a.severity === 'error');

  const handleSaveRubric = async () => {
    if (!rubricName.trim()) {
      setError('יש להזין שם למחוון לפני השמירה.');
      return;
    }

    setIsLoading(true);
    setError(null);
    setSaveError(null);
    try {
      // Dehydrate: convert number point fields back to strings for the backend.
      const dehydrated = dehydrateQuestions(extractedQuestions);

      // Single source of truth for the save payload — both the initial save
      // and the warning-acknowledgement retry share the same draft. Crucially,
      // total_points is the teacher-authoritative `rubricDeclaredTotal`, not
      // `Σ q.total_points`. By the time save fires, hasBlockingErrors is false
      // (the button is otherwise disabled), which means INV-R3 holds and the
      // two values are equal. If the anchor is somehow undefined we fall back
      // to 0 — the backend will reject this, surfacing the bug loudly rather
      // than silently transmitting a fabricated total.
      const draft = {
        questions: dehydrated,
        total_points: rubricDeclaredTotal ?? 0,
        selection_groups: selectionGroups,
        num_questions: extractedQuestions.length,
        num_sub_questions: extractedQuestions.reduce((sum, q) => sum + (q.sub_questions?.length || 0), 0),
        num_criteria: extractedQuestions.reduce((sum, q) =>
          sum + q.criteria.length + (q.sub_questions || []).reduce((s, sq) => s + sq.criteria.length, 0), 0
        ),
      };

      const response = await saveOntologyRubric({
        name: rubricName,
        draft,
        extraction_job_id: extractionJobId ?? undefined,
      });

      if (isWarningsResponse(response)) {
        // Auto-acknowledge only pipeline rubric_mismatch warnings (structural point mismatches
        // in the source document that the teacher has already seen in the editor).
        // Never auto-acknowledge invariant_violation warnings — those must be resolved first.
        const warningIds = response.warnings
          .filter(w => w.annotation_type !== 'invariant_violation')
          .map(w => w.id);
        const retryResponse = await saveOntologyRubric({
          name: rubricName,
          draft,
          acknowledged_warning_ids: warningIds,
          extraction_job_id: extractionJobId ?? undefined,
        });
        if (!isWarningsResponse(retryResponse)) {
          setSavedRubricId(retryResponse.rubric_id);
        }
      } else {
        setSavedRubricId(response.rubric_id);
      }
      setRubricStep('saved');
    } catch (err) {
      if (err instanceof ApiAuthError) {
        handleAuthFailure();          // stash the edits BEFORE anything redirects
      } else if (err instanceof RubricSaveError) {
        // PR-3: a compile REJECTION is the rubric gate doing its job — it is the one
        // moment the product exists for. It must never collapse to a generic sentence.
        // The payload now names the offending node (`q1.א.2`), the invariant, the
        // expected/actual points, and a real Hebrew message a teacher can act on;
        // RubricErrorDisplay already renders all of it. Flattening this to
        // toMessage(err) — as this branch used to — threw every one of those away and
        // showed only "שגיאה בהכנת המחוון".
        setSaveError(err);
      } else {
        setError(toMessage(err));     // other domain error -> inline banner (convention)
      }
    } finally {
      setIsLoading(false);
    }
  };

  // S11: load classes when the user reaches the upload step
  useEffect(() => {
    if (gradingStep === 'upload_batch') {
      listClasses()
        .then(r => setBatchClasses(r.classes.map(c => ({ id: String(c.id), name: c.name }))))
        .catch(() => {/* classes optional — ignore load failure */});
    }
  }, [gradingStep]);

  // S11: create a batch and navigate to the batch review page
  const handleGradeAsBatch = async () => {
    if (!selectedRubric || testFiles.length === 0) return;
    setBatchUploading(true);
    try {
      const result = await createBatch(
        testFiles,
        selectedRubric.id,
        batchClassId || undefined,
      );
      router.push(`/batches/${result.batch_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'שגיאה ביצירת הבאץ\'');
      setBatchUploading(false);
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
  // S4: Handwritten transcription — blocking call, no streaming
  // Flow: Upload → PDF Processing (spinner) → TranscriptionReviewPanel → grading_queued
  // =============================================================================
  const handleGradeHandwritten = async () => {
    if (!selectedRubric || handwrittenConfigs.length === 0) return;

    const config = handwrittenConfigs[0];
    setCurrentTestFile(config.file);
    setError(null);
    setTranscribeResponse(null);
    setGradingStep('pdf_processing');

    try {
      const response = await transcribe(selectedRubric.id, config.file);
      setTranscribeResponse(response);
      setGradingStep('review_transcription');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'שגיאה בתמלול');
      setGradingStep('upload_batch');
    }
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
      // TODO(S4): re-wire to new gradeWithTranscription() endpoint
      // const result = await gradeWithTranscription({
      //   rubric_id: selectedRubric.id,
      //   student_name: streaming.transcriptionData.student_name,
      //   filename: streaming.transcriptionData.filename,
      //   answers: editedAnswers,
      // });

      // Store page thumbnails for results view
      const pagesMap = new Map<string, PagePreview[]>();
      pagesMap.set(streaming.transcriptionData.filename, streaming.transcriptionData.pages);
      setTestPagesMap(pagesMap);

      // TODO(S4): uncomment when gradeWithTranscription is re-wired
      // setGradingResults([result]);
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
        // TODO(S4): re-wire to new grading endpoint
        // const result = await gradeSingleTest(
        //   selectedRubric.id,
        //   testMapping.answerMappings,
        //   testMapping.file,
        //   0
        // );
        // results.push(result);
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
    setExtractedQuestions([]);
    setRubricDeclaredTotal(undefined);
    setSelectedRubric(null);
    setTestFiles([]);
    setTestMappings([]);
    setGradingResults([]);
    setTranscriptionMode(null);
    setHandwrittenConfigs([]);
    setCurrentTestFile(null);
    setError(null);
    // Reset DOCX state
    setExtractionMetadata(null);
    setExtractionAnnotations([]);
    // Reset preflight/purpose state
    setPendingDocxFile(null);
    setPreflightQuestions([]);
    setPreflightDetectedTitle(null);
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
                <p className="text-gray-500 text-sm">העלי קובץ DOCX של המחוון</p>
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
                {/* PR-2 (C10): a previous session was cut short mid-review (auth
                    expiry). The teacher's edits were stashed — offer them back. */}
                {restorable && (
                  <div className="mb-4 bg-amber-50 border border-amber-200 rounded-xl p-4">
                    <div className="flex items-start gap-3">
                      <AlertCircle className="text-amber-600 mt-0.5 shrink-0" size={20} />
                      <div className="flex-1">
                        <p className="font-medium text-amber-900">נמצאה עבודה שלא נשמרה</p>
                        <p className="text-sm text-amber-700 mt-1">
                          {restorable.rubricName
                            ? `מחוון "${restorable.rubricName}" — `
                            : ''}
                          העריכה נקטעה לפני השמירה. לשחזר?
                        </p>
                        <div className="flex gap-2 mt-3">
                          <button
                            onClick={restoreStashedWork}
                            className="px-4 py-1.5 bg-amber-600 text-white rounded-lg text-sm hover:bg-amber-700 transition-colors"
                          >
                            שחזרי
                          </button>
                          <button
                            onClick={discardStashedWork}
                            className="px-4 py-1.5 text-amber-700 rounded-lg text-sm hover:bg-amber-100 transition-colors"
                          >
                            מחקי
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
                <div className="bg-white rounded-xl shadow-lg p-8">
                  <div className="text-center mb-6">
                    <Upload className="mx-auto text-primary-500 mb-3" size={48} />
                    <h2 className="text-xl font-semibold">העלאת מחוון</h2>
                    <p className="text-gray-500 mt-1">העלי קובץ DOCX של המחוון</p>
                  </div>

                  {/* Programming language selector */}
                  <div className="mb-4">
                    <label className="block text-sm font-medium text-gray-700 mb-1">שפת תכנות</label>
                    <select
                      value={programmingLanguage}
                      onChange={(e) => setProgrammingLanguage(e.target.value)}
                      className="w-full p-2 border border-surface-300 rounded-lg text-sm"
                    >
                      <option value="Java">Java</option>
                      <option value="Python">Python</option>
                      <option value="C++">C++</option>
                      <option value="C#">C#</option>
                      <option value="JavaScript">JavaScript</option>
                      <option value="Pseudocode">פסאודו-קוד</option>
                    </select>
                  </div>

                  <FileUpload file={rubricFile} onFileChange={handleRubricFileChange} accept=".pdf,.docx" label="גרור קובץ DOCX לכאן" showFormatGuide />
                  {isLoading && <div className="mt-4 flex items-center justify-center gap-2 text-primary-600"><Loader2 className="animate-spin" size={20} /><span>מעבד את הקובץ...</span></div>}
                  {error && <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm flex items-center gap-2"><AlertCircle size={18} />{error}</div>}
                </div>
              </div>
            )}

            {rubricStep === 'purpose' && (
              <div className="max-w-2xl mx-auto animate-fade-in">
                <div className="flex items-center gap-4 mb-6">
                  <BackButton onClick={() => {
                    setPendingDocxFile(null);
                    setRubricStep('upload');
                    setRubricFile(null);
                  }} />
                  <h2 className="text-xl font-bold text-gray-900">הגדרת מטרות (אופציונלי)</h2>
                </div>
                <RubricPurpose
                  questions={preflightQuestions}
                  detectedTitle={preflightDetectedTitle}
                  onConfirm={handlePurposeConfirm}
                  onSkip={handlePurposeSkip}
                  isLoading={isLoading}
                />
                {error && (
                  <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm flex items-center gap-2">
                    <AlertCircle size={18} />{error}
                  </div>
                )}
              </div>
            )}

            {rubricStep === 'extracting' && (
              <div className="max-w-xl mx-auto animate-fade-in">
                {extractionJob.status?.status === 'failed' || extractionJob.status?.stale ? (
                  /* Terminal failure / stale (server died mid-job) — durable, retryable */
                  <div className="bg-white rounded-xl shadow-lg p-8 text-center">
                    <AlertCircle className="mx-auto text-red-500 mb-4" size={64} />
                    <h2 className="text-xl font-semibold text-gray-800">החילוץ נכשל</h2>
                    <p className="text-gray-500 mt-2">
                      {extractionJob.status?.stale
                        ? 'החיבור לשרת אבד באמצע העיבוד. הקובץ שמור אצלנו — אפשר לנסות שוב בלי להעלות מחדש.'
                        : 'אירעה שגיאה בעיבוד המסמך. הקובץ שמור אצלנו — אפשר לנסות שוב בלי להעלות מחדש.'}
                    </p>
                    {extractionJob.status?.error_message && (
                      <p className="text-xs text-gray-400 mt-2 break-all" dir="ltr">
                        {extractionJob.status.error_message}
                      </p>
                    )}
                    <div className="flex items-center justify-center gap-3 mt-6">
                      <button
                        onClick={handleExtractionBack}
                        className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                      >
                        חזרה
                      </button>
                      <button
                        onClick={handleExtractionRetry}
                        disabled={extractionRetrying}
                        className="flex items-center gap-2 px-5 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 disabled:opacity-50 transition-colors"
                      >
                        {extractionRetrying ? <Loader2 className="animate-spin" size={18} /> : null}
                        נסי שוב
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="bg-white rounded-xl shadow-lg p-8 text-center">
                    <Loader2 className="mx-auto text-primary-500 mb-4 animate-spin" size={64} />
                    <h2 className="text-xl font-semibold text-gray-800">
                      {getExtractionStageLabel(extractionJob.status?.progress_stage ?? null)}
                    </h2>
                    <p className="text-gray-500 mt-2">
                      Vivi קוראת את המחוון ומחלצת שאלות, קריטריונים וניקוד — בדרך כלל 2–4 דקות.
                      אפשר לעזוב את העמוד; החילוץ ימשיך ברקע.
                    </p>
                    {extractionJob.status?.elapsed_seconds != null && (
                      <p className="text-sm text-gray-400 mt-3">
                        {Math.floor(extractionJob.status.elapsed_seconds / 60) > 0
                          ? `${Math.floor(extractionJob.status.elapsed_seconds / 60)} דק' ${Math.round(extractionJob.status.elapsed_seconds % 60)} שנ'`
                          : `${Math.round(extractionJob.status.elapsed_seconds)} שניות`}
                      </p>
                    )}
                    {error && (
                      <p className="text-sm text-amber-600 mt-3">{error}</p>
                    )}
                  </div>
                )}
              </div>
            )}

            {rubricStep === 'review' && (
              <div className="animate-fade-in">
                {/* PR-3: the compile rejection, rendered in full — the offending node,
                    the numbers, and a real Hebrew sentence. This is the rubric gate
                    doing its job; it is the moment the product exists for, so it gets
                    the teacher's whole attention rather than a generic one-liner. */}
                {saveError && (
                  <RubricErrorDisplay
                    error={saveError}
                    onDismiss={() => setSaveError(null)}
                  />
                )}
                <div className="bg-white rounded-xl shadow-lg p-6">
                  <RubricEditor
                    questions={extractedQuestions}
                    onQuestionsChange={setExtractedQuestions}
                    pages={rubricPages}
                    sourceType="docx"
                    metadata={extractionMetadata || undefined}
                    annotations={combinedAnnotations}
                    errorBannerRef={errorBannerRef}
                    programmingLanguage={programmingLanguage}
                    rubricName={rubricName}
                    rubricTotalPoints={rubricDeclaredTotal}
                    onTotalPointsChange={setRubricDeclaredTotal}
                    onMetadataChange={(patch) => {
                      if (patch.rubric_name !== undefined) setRubricName(patch.rubric_name);
                    }}
                    hasNameError={!!error && !rubricName.trim()}
                  />
                  {error && <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{error}</div>}
                  <div className="mt-6 pt-4 border-t border-surface-200 flex items-center justify-between">
                    <BackButton onClick={() => setRubricStep('upload')} />
                    <button
                      onClick={hasBlockingErrors
                        ? () => errorBannerRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
                        : handleSaveRubric}
                      disabled={isLoading}
                      aria-disabled={hasBlockingErrors}
                      className={`flex items-center gap-2 px-6 py-2 rounded-lg transition-colors ${
                        hasBlockingErrors
                          ? 'opacity-50 cursor-not-allowed bg-gray-300 text-gray-500'
                          : 'bg-primary-500 text-white hover:bg-primary-600 disabled:opacity-50'
                      }`}
                    >
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
                    <p className="text-sm text-primary-600">{selectedRubric.total_questions ?? 0} שאלות · {selectedRubric.total_points} נקודות</p>
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

                  {/* S11: Grade as batch (shown when >1 PDF selected in handwritten mode) */}
                  {transcriptionMode === 'handwritten' && testFiles.length > 1 && (
                    <div className="mt-4 p-4 bg-indigo-50 border border-indigo-200 rounded-xl">
                      <p className="text-sm font-medium text-indigo-800 mb-3">
                        בדיקה כאצווה — {testFiles.length} מבחנים יתומללו ויוכנסו לבדיקה יחד
                      </p>

                      {/* Optional class selection */}
                      <div className="mb-3">
                        <label className="block text-xs text-indigo-700 mb-1">כיתה (אופציונלי — לצורך התאמה אוטומטית של שמות)</label>
                        <select
                          value={batchClassId || ''}
                          onChange={e => setBatchClassId(e.target.value || null)}
                          className="w-full border border-indigo-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-400"
                        >
                          <option value="">ללא כיתה / תלמיד ראשון</option>
                          {batchClasses.map(c => (
                            <option key={c.id} value={c.id}>{c.name}</option>
                          ))}
                        </select>
                      </div>

                      <button
                        onClick={handleGradeAsBatch}
                        disabled={batchUploading}
                        className="w-full flex items-center justify-center gap-2 bg-indigo-600 text-white px-4 py-2.5 rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors font-medium text-sm"
                      >
                        {batchUploading ? (
                          <><Loader2 size={16} className="animate-spin" /> מעלה אצווה...</>
                        ) : (
                          <>
                            <ClipboardCheck size={16} />
                            בדוק כאצווה ({testFiles.length} מבחנים)
                          </>
                        )}
                      </button>
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

            {/* PDF Processing step — spinner while blocking transcribe() call is in-flight */}
            {gradingStep === 'pdf_processing' && currentTestFile && (
              <PdfProcessingPage
                filename={currentTestFile.name}
                onError={(msg) => {
                  setError(msg);
                  setGradingStep('upload_batch');
                }}
              />
            )}

            {/* S4: Review transcription — teacher reviews and edits VLM output */}
            {gradingStep === 'review_transcription' && transcribeResponse && (
              <TranscriptionReviewPanel
                response={transcribeResponse}
                submitting={submittingGrade}
                onBack={() => {
                  setTranscribeResponse(null);
                  setGradingStep('upload_batch');
                }}
                onSubmit={async (answers, studentId) => {
                  setSubmittingGrade(true);
                  try {
                    const result = await submitGrade({
                      transcriptionId: transcribeResponse.transcription_id,
                      answers,
                      studentId,
                    });
                    setGradedTestId(result.graded_test_id);
                    setPollingActive(true);
                    setGradingStep('grading_queued');
                  } finally {
                    setSubmittingGrade(false);
                  }
                }}
              />
            )}

            {/* S8: Grading in progress — polling until draft is ready */}
            {gradingStep === 'grading_queued' && (
              <div dir="rtl" className="max-w-md mx-auto animate-fade-in">
                <div className="bg-white rounded-xl shadow-lg p-8 text-center space-y-4">
                  <div className="w-16 h-16 rounded-full bg-primary-50 flex items-center justify-center mx-auto">
                    <Loader2 size={32} className="text-primary-500 animate-spin" />
                  </div>
                  <h2 className="text-xl font-semibold text-gray-900">הבדיקה מתבצעת...</h2>
                  <p className="text-sm text-gray-500">
                    הבינה המלאכותית בודקת את המבחן. זה עשוי לקחת מספר שניות.
                  </p>
                </div>
              </div>
            )}

            {/* S8: Draft review — grading complete, teacher reviews AI output */}
            {gradingStep === 'draft_review' && gradedTestDetail && transcribeResponse && (
              <GradedTestReviewPanel
                response={gradedTestDetail}
                transcriptionId={transcribeResponse.transcription_id}
                onBack={() => {
                  setGradedTestDetail(null);
                  setGradedTestId(null);
                  setTranscribeResponse(null);
                  setCurrentTestFile(null);
                  setHandwrittenConfigs([]);
                  setGradingStep('upload_batch');
                }}
              />
            )}

            {/* S8: Grading failed */}
            {gradingStep === 'grading_failed' && (
              <div dir="rtl" className="max-w-md mx-auto animate-fade-in">
                <div className="bg-white rounded-xl shadow-lg p-8 text-center space-y-4">
                  <div className="w-16 h-16 rounded-full bg-red-50 flex items-center justify-center mx-auto">
                    <AlertCircle size={32} className="text-red-500" />
                  </div>
                  <h2 className="text-xl font-semibold text-gray-900">שגיאה בבדיקה</h2>
                  {gradingError && (
                    <p className="text-sm text-red-600">{gradingError}</p>
                  )}
                  <button
                    onClick={() => {
                      setGradedTestDetail(null);
                      setGradedTestId(null);
                      setGradingError(null);
                      setTranscribeResponse(null);
                      setCurrentTestFile(null);
                      setHandwrittenConfigs([]);
                      setGradingStep('upload_batch');
                    }}
                    className="w-full py-3 text-sm font-medium bg-primary-500 text-white rounded-xl hover:bg-primary-600 transition-colors"
                  >
                    בדיקת מבחן חדש
                  </button>
                </div>
              </div>
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
      {/* Extraction Error Modal */}
        {errorModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm animate-fade-in">
            <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full mx-4 p-6 relative" dir="rtl">
              {/* Close button */}
              <button
                onClick={() => setErrorModal(null)}
                className="absolute top-4 left-4 text-gray-400 hover:text-gray-600 transition-colors"
              >
                <X size={20} />
              </button>

              {/* Icon */}
              <div className="flex justify-center mb-4">
                <div className="w-14 h-14 rounded-full bg-amber-50 flex items-center justify-center">
                  <AlertCircle size={28} className="text-amber-500" />
                </div>
              </div>

              {/* Content */}
              <h3 className="text-lg font-bold text-gray-900 text-center mb-2">
                {errorModal.title}
              </h3>
              <p className="text-sm text-gray-600 text-center leading-relaxed mb-4">
                {errorModal.message}
              </p>

              {/* Technical details (collapsible) */}
              {errorModal.details && (
                <details className="mb-4 text-xs text-gray-400 bg-gray-50 rounded-lg p-3">
                  <summary className="cursor-pointer hover:text-gray-600 select-none">
                    פרטים טכניים
                  </summary>
                  <pre className="mt-2 whitespace-pre-wrap break-all font-mono" dir="ltr">
                    {errorModal.details}
                  </pre>
                </details>
              )}

              {/* Action button */}
              <button
                onClick={() => setErrorModal(null)}
                className="w-full py-2.5 bg-primary-500 text-white rounded-xl font-medium hover:bg-primary-600 transition-colors"
              >
                הבנתי
              </button>
            </div>
          </div>
        )}
    </SidebarLayout>
  );
}