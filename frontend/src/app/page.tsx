'use client';

import { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { FileUpload } from '@/components/FileUpload';
import { MultiFileUpload } from '@/components/MultiFileUpload';
import { PageGrid } from '@/components/PageThumbnail';
import { RubricEditor } from '@/components/RubricEditor';
import { RubricDocument } from '@/components/RubricDocument';
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
  type SaveOntologyRubricWarnings,
  type OntologyRubricDraft,
} from '@/lib/api';
import { useExtractionJob, getExtractionStageLabel } from '@/hooks/useExtractionJob';
import { toast } from 'sonner';
import { ApiAuthError } from '@/lib/api';
import { authErrorMessage, toMessage, surfaceError } from '@/lib/errorSurface';
import {
  clearUnsavedWork,
  peekUnsavedWork,
  stashUnsavedWork,
  type UnsavedWork,
} from '@/lib/session';
import type { TranscribeResponse } from '@/types/transcription';
import type { GradedTestDraftResponse } from '@/types/graded_test';
import { patchExtractionJobMetadata, getRubric } from '@/lib/api';
import { RubricErrorDisplay, RubricWarningsModal } from '@/components/RubricSaveFlow';
import type { RubricQuestion } from '@/types/rubric';
import { hydrateAnyQuestions, dehydrateQuestions, safeParseFloat } from '@/utils/rubric-transform';
import { validateAllQuestions, validateRubricTotalPoints } from '@/utils/rubric-validation';
import { computeAchievablePoints } from '@/utils/rubric-achievable';
import { getExtractionStageOrder } from '@/hooks/useExtractionJob';
import {
  countFindings, countCriteria, resolveRubricName, selectionSummaryLine,
  findingsWaitingLabel, classifyExtractionError,
} from '@/utils/session-spine';
import { playCompletionChime, flipTabTitleToReady, restoreTabTitle } from '@/utils/completion-signal';
import { pushSnapshot, popSnapshot, type RubricSnapshot } from '@/utils/rubric-history';
import { USE_DOCUMENT_MIRROR } from '@/lib/flags';
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
type RubricStep = 'upload' | 'extracting' | 'arrival' | 'review' | 'saved';
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
  // Captured programming language — '' means "זיהוי אוטומטי" (infer). Set only by
  // the capture card now (the upload-step select is gone); feeds the editor display.
  const [programmingLanguage, setProgrammingLanguage] = useState<string>('');
  // PR-5 S1-2 — the capture card (movement 1 of the wait). Metadata-only.
  const [captureDone, setCaptureDone] = useState(false);        // confirmed/skipped → movement 2
  const [inferredName, setInferredName] = useState<string | null>(null); // result.rubric_name
  const [filenameStem, setFilenameStem] = useState<string>(''); // filename-derived suggestion
  // PR-5 S1-3 — stages the SERVER has actually reported, accumulated across polls
  // (the server only ever emits the CURRENT one; we never fabricate future rungs).
  const observedStagesRef = useRef<Set<string>>(new Set());
  const [observedStages, setObservedStages] = useState<string[]>([]);
  // PR-5 S1-8 — review edits since arrival; cleared on save. Drives the nav guard.
  const dirtyRef = useRef(false);

  // PR-5 S2 E-1 — page-level undo stack over the FULL editable tuple
  // {questions, declaredTotal, name}. Snapshots are pushed BY REFERENCE (structural
  // sharing → 50 is trivial); every edit already goes through the pure ops. Live
  // refs mirror the current tuple so pushHistory always snapshots the PRE-edit
  // state regardless of closure staleness. No redo at MVP (deliberate; backlogged).
  const historyRef = useRef<RubricSnapshot[]>([]);
  const [canUndoRubric, setCanUndoRubric] = useState(false);
  const questionsRef = useRef(extractedQuestions);
  const declaredRef = useRef(rubricDeclaredTotal);
  const nameRef = useRef(rubricName);
  questionsRef.current = extractedQuestions;
  declaredRef.current = rubricDeclaredTotal;
  nameRef.current = rubricName;

  const pushRubricHistory = useCallback(() => {
    historyRef.current = pushSnapshot(historyRef.current, {
      questions: questionsRef.current, declaredTotal: declaredRef.current, name: nameRef.current,
    });
    setCanUndoRubric(true);
  }, []);
  const clearRubricHistory = useCallback(() => {
    historyRef.current = [];
    setCanUndoRubric(false);
  }, []);
  const undoRubricEdit = useCallback(() => {
    const { snapshot, stack } = popSnapshot(historyRef.current);
    if (!snapshot) return;
    historyRef.current = stack;
    setExtractedQuestions(snapshot.questions);
    setRubricDeclaredTotal(snapshot.declaredTotal);
    setRubricName(snapshot.name);
    setCanUndoRubric(stack.length > 0);
    dirtyRef.current = true;
  }, []);

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
  /** PR-4 (R-D): warnings the teacher must EXPLICITLY confirm before save proceeds.
   *  Replaces the old blanket auto-ack — Vivi proposes, the teacher decides. The
   *  draft is held so the confirmed retry sends the identical payload + acked ids. */
  const [pendingWarnings, setPendingWarnings] = useState<SaveOntologyRubricWarnings | null>(null);
  const [pendingSaveDraft, setPendingSaveDraft] = useState<OntologyRubricDraft | null>(null);

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

  // Rubric Handlers — S1-1/S1-2: drop the DOCX and go. No purpose interstitial,
  // no name field, no language dropdown; the job submits on drop, file-only.
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

    await _runDocxExtraction(file);
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
    //
    // safeParseFloat is LOAD-BEARING, not cosmetic: total_points is typed `number`
    // but arrives as a Decimal-serialized STRING ("100.0") on the wire. Stored raw,
    // it reached formatPoints(n.toFixed(2)) and crashed the whole review screen
    // ("e.toFixed is not a function") the moment INV-R3 fired — which is exactly
    // when a rubric has a real discrepancy to show the teacher. This is the ONE
    // rubric point value that was bypassing the hydration boundary; every other
    // point goes through safeParseFloat in hydrateAnyQuestions.
    setRubricDeclaredTotal(safeParseFloat(response.total_points));
    setSelectionGroups(response.selection_groups ?? []);
    setExtractionMetadata(response.metadata || null);
    setExtractionAnnotations(response.annotations || []);
    // Name precedence (S1-2.4): the extraction-inferred name is the MIDDLE tier —
    // it must NOT overwrite a name the teacher captured during the wait. Store it;
    // resolveRubricName picks the winner at arrival/save time.
    setInferredName(response.name ?? null);
    dirtyRef.current = false;          // a fresh result is not "unsaved edits" yet
    clearRubricHistory();              // a new rubric starts with an empty undo stack
    setRubricStep('arrival');          // S1-5: the summary card lands before the document
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
      // S1-3.4: signal a teacher who left the tab — before the (slower) result fetch.
      if (typeof document !== 'undefined' && document.visibilityState === 'hidden') {
        flipTabTitleToReady();
        playCompletionChime();
      }
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

  const _runDocxExtraction = async (file: File) => {
    // Fresh wait — reset the capture card, stage ladder, and dirty flag.
    setFilenameStem(file.name.replace(/\.docx$/i, ''));
    setRubricName('');            // placeholder shows the suggestion; blank ⇒ inference wins
    setInferredName(null);
    setProgrammingLanguage('');   // "זיהוי אוטומטי" until she says otherwise
    setCaptureDone(false);
    observedStagesRef.current = new Set();
    setObservedStages([]);
    dirtyRef.current = false;
    clearRubricHistory();
    setRubricStep('extracting');
    setIsLoading(true);
    setError(null);
    try {
      // S1-2: ZERO-PARAM submit — file only. Name/language are captured during the
      // wait (metadata-only) or inferred; extraction never depends on them.
      const submitted = await submitExtractionJob(file);
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

  // S1-3.2: accumulate the stages the SERVER has actually reported. The server
  // only ever emits the CURRENT stage; we append each distinct one so the wait
  // checklist shows honest completed rungs and never fabricates future ones.
  useEffect(() => {
    const stage = extractionJob.status?.progress_stage;
    if (stage && !observedStagesRef.current.has(stage)) {
      observedStagesRef.current.add(stage);
      setObservedStages(Array.from(observedStagesRef.current));
    }
  }, [extractionJob.status?.progress_stage]);

  // S1-3.4: restore the tab title when she returns to the tab.
  useEffect(() => {
    const onVisible = () => { if (document.visibilityState === 'visible') restoreTabTitle(); };
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
  }, []);

  // S1-8(a): browser-native prompt on real page unload while review edits are unsaved.
  useEffect(() => {
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      if (dirtyRef.current) { e.preventDefault(); e.returnValue = ''; }
    };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, []);

  // ---------------------------------------------------------------------------
  // S1-7: enter grading with a rubric already selected (carry-through + deep-link).
  // ---------------------------------------------------------------------------
  const enterGradingWithRubric = useCallback((item: RubricListItem) => {
    setSelectedRubric(item);
    setMainMode('grading');
    setGradingStep('upload_batch');
  }, []);

  // S1-7.2: wire the previously-dead deep-link. `?rubric=<id>` (my-rubrics'
  // "בדקי מבחנים עם מחוון זה" button) → load the rubric → land on upload-tests
  // pre-selected. Read window.location.search in a mount effect, NOT
  // useSearchParams (which forces a Suspense boundary / breaks the static build).
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const rubricId = new URLSearchParams(window.location.search).get('rubric');
    if (!rubricId) return;
    (async () => {
      try {
        const detail = await getRubric(rubricId);
        enterGradingWithRubric({
          ...detail,
          total_points: detail.total_points ?? detail.stats?.total_points,
          total_questions: detail.total_questions ?? detail.stats?.total_questions,
        });
      } catch {
        toast.error('לא הצלחנו לפתוח את המחוון לבדיקה');
        // stay on home
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // S1-8(b): in-app guard for the "navigations" that are actually state flips.
  const confirmDiscardIfDirty = useCallback((): boolean => {
    if (!dirtyRef.current) return true;
    return window.confirm('יש שינויים שלא נשמרו — לצאת בכל זאת?');
  }, []);

  // Wrap the review-editor callbacks so any edit marks the work dirty (S1-8) and
  // pushes a pre-edit snapshot onto the undo stack (S2 E-1).
  const handleQuestionsEdited = useCallback((qs: RubricQuestion[]) => {
    pushRubricHistory();
    dirtyRef.current = true;
    setExtractedQuestions(qs);
  }, [pushRubricHistory]);
  const handleTotalPointsChange = useCallback((t: number) => {
    pushRubricHistory();
    dirtyRef.current = true;
    setRubricDeclaredTotal(t);
  }, [pushRubricHistory]);
  const handleRubricMetadataChange = useCallback((patch: { rubric_name?: string; subject?: string; programming_language?: string }) => {
    pushRubricHistory();
    dirtyRef.current = true;
    if (patch.rubric_name !== undefined) setRubricName(patch.rubric_name);
  }, [pushRubricHistory]);

  // S2 D-3 — delete is undo-over-confirm: the mirror executes immediately and
  // dispatches this event; we surface a 6s toast whose «ביטול» pops the undo stack.
  useEffect(() => {
    const onUndoToast = (e: Event) => {
      const detail = (e as CustomEvent<{ message?: string }>).detail;
      toast(detail?.message ?? 'נמחק', {
        action: { label: 'ביטול', onClick: () => undoRubricEdit() },
        duration: 6000,
      });
    };
    window.addEventListener('vivi:undo-toast', onUndoToast as EventListener);
    return () => window.removeEventListener('vivi:undo-toast', onUndoToast as EventListener);
  }, [undoRubricEdit]);

  // S1-2.3: the capture card — confirm PATCHes the captured metadata in ONE
  // combined request (atomic jsonb merge server-side); skip just collapses. Both
  // move to movement 2 (calm waiting). Fire-and-forget: a metadata failure toasts
  // but never blocks the wait, and the name still resolves at save time.
  const handleCaptureConfirm = async () => {
    setCaptureDone(true);
    if (!extractionJobId) return;
    try {
      await patchExtractionJobMetadata(extractionJobId, {
        name: rubricName.trim() || filenameStem || null,
        programming_language: programmingLanguage || null,
      });
    } catch (err) {
      surfaceError(err);
    }
  };

  const handleCaptureSkip = () => {
    setCaptureDone(true);
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

    // INV-R3 — rubric-level ACHIEVABLE total (PR-4, achievable-aware). Gated on
    // rubricDeclaredTotal being set (it is, from extraction time onward). The
    // pre-PR-4 abstain (skip when selection groups exist) is GONE:
    // validateRubricTotalPoints now compares computeAchievablePoints(questions,
    // selection_groups) — the client mirror of backend INV-4 — against the
    // declared total, so it is correct on selection exams too (a "choose 4 of 6"
    // bagrut declares 100 while offering 150; achievable is 100). We still do NOT
    // re-derive grading best-k here — that is genuinely server-only; rubric
    // achievable is pure arithmetic over declared totals (see rubric-achievable.ts).
    if (rubricDeclaredTotal !== undefined) {
      const r3 = validateRubricTotalPoints(extractedQuestions, rubricDeclaredTotal, selectionGroups);
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
  }, [extractedQuestions, extractionAnnotations, rubricDeclaredTotal, selectionGroups]);

  const hasBlockingErrors = combinedAnnotations.some(a => a.severity === 'error');

  const handleSaveRubric = async () => {
    // S1-2.4: the name is ALWAYS resolvable (captured > inferred > filename), so
    // save is never blocked on it — the Dream doc makes naming optional.
    const resolvedName = resolveRubricName(rubricName, inferredName, filenameStem);

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
        name: resolvedName,
        draft,
        extraction_job_id: extractionJobId ?? undefined,
      });

      if (isWarningsResponse(response)) {
        // R-D: DO NOT auto-acknowledge. The old code silently acked every
        // non-invariant warning — confirming the teacher's OWN flagged mismatch on
        // her behalf, and a latent swallow of any future warning class (census C8 /
        // B-6). Instead surface the warnings and require an explicit confirm; the
        // held draft is resent with acked ids only after the teacher clicks through
        // (see handleConfirmWarnings + the RubricWarningsModal render below).
        setPendingWarnings(response);
        setPendingSaveDraft(draft);
      } else {
        setSavedRubricId(response.rubric_id);
        dirtyRef.current = false;     // saved — review work is now clean (S1-8)
        clearRubricHistory();         // E-1: history is session-scoped, clears on save
        setRubricStep('saved');
      }
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

  /** R-D: the teacher reviewed the warnings and confirmed — resend the HELD draft
   *  with all warning ids acknowledged. This is the ONLY path that acks warnings
   *  now; there is no silent auto-ack anywhere. */
  const handleConfirmWarnings = async (warningIds: string[]) => {
    if (!pendingSaveDraft) return;
    setIsLoading(true);
    setError(null);
    try {
      const resp = await saveOntologyRubric({
        name: resolveRubricName(rubricName, inferredName, filenameStem),
        draft: pendingSaveDraft,
        acknowledged_warning_ids: warningIds,
        extraction_job_id: extractionJobId ?? undefined,
      });
      if (isWarningsResponse(resp)) {
        // Fresh warnings after an explicit ack should not happen — keep the modal
        // open on them rather than silently proceeding.
        setPendingWarnings(resp);
      } else {
        setSavedRubricId(resp.rubric_id);
        setPendingWarnings(null);
        setPendingSaveDraft(null);
        dirtyRef.current = false;     // saved — clean (S1-8)
        clearRubricHistory();         // E-1: history clears on save
        setRubricStep('saved');
      }
    } catch (err) {
      setPendingWarnings(null);
      setPendingSaveDraft(null);
      if (err instanceof ApiAuthError) {
        handleAuthFailure();
      } else if (err instanceof RubricSaveError) {
        setSaveError(err);
      } else {
        setError(toMessage(err));
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancelWarnings = () => {
    setPendingWarnings(null);
    setPendingSaveDraft(null);
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
    // S1-8(b): if there is unsaved review work, confirm before discarding it.
    if (!confirmDiscardIfDirty()) return;
    dirtyRef.current = false;
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
    // Reset capture-card state
    setCaptureDone(false);
    setInferredName(null);
    setFilenameStem('');
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

                  {/* S1-1/S1-2: one action — drop the DOCX. No language dropdown,
                      no name field, no purpose step. Everything else is inferable
                      or captured during the wait. */}
                  <FileUpload file={rubricFile} onFileChange={handleRubricFileChange} accept=".pdf,.docx" label="גררי קובץ DOCX לכאן" showFormatGuide />
                  {isLoading && <div className="mt-4 flex items-center justify-center gap-2 text-primary-600"><Loader2 className="animate-spin" size={20} /><span>מעלה את הקובץ...</span></div>}
                  {error && <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm flex items-center gap-2"><AlertCircle size={18} />{error}</div>}
                </div>
              </div>
            )}

            {rubricStep === 'extracting' && (
              <div className="max-w-xl mx-auto animate-fade-in">
                {extractionJob.status?.status === 'failed' || extractionJob.status?.stale ? (
                  /* S1-4: failure — blame-correct, two one-click actions, raw hidden. */
                  (() => {
                    const stale = !!extractionJob.status?.stale;
                    const raw = extractionJob.status?.error_message ?? null;
                    const copy = stale
                      ? { headline: 'החיבור אבד באמצע העיבוד', body: 'החיבור לשרת נקטע — לא בקובץ שלך. הקובץ שמור, אין צורך להעלות שוב.' }
                      : classifyExtractionError(raw);
                    const mailto = `mailto:support@vivi-assistant.com?subject=${encodeURIComponent('תקלה בחילוץ מחוון')}&body=${encodeURIComponent(`מזהה עבודה: ${extractionJobId ?? '—'}\nזמן: ${new Date().toLocaleString('he-IL')}\n\nמה קרה: `)}`;
                    return (
                      <div className="bg-white rounded-xl shadow-lg p-8 text-center">
                        <AlertCircle className="mx-auto text-red-500 mb-4" size={64} />
                        <h2 className="text-xl font-semibold text-gray-800">{copy.headline}</h2>
                        <p className="text-gray-500 mt-2">{copy.body}</p>
                        <div className="flex items-center justify-center gap-3 mt-6">
                          <button
                            onClick={handleExtractionRetry}
                            disabled={extractionRetrying}
                            className="flex items-center gap-2 px-5 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 disabled:opacity-50 transition-colors"
                          >
                            {extractionRetrying ? <Loader2 className="animate-spin" size={18} /> : null}
                            לנסות מחדש
                          </button>
                          <a
                            href={mailto}
                            className="px-5 py-2 text-gray-600 border border-surface-300 rounded-lg hover:bg-gray-50 transition-colors"
                          >
                            דיווח תקלה
                          </a>
                        </div>
                        {raw && (
                          <details className="mt-5">
                            <summary className="text-xs text-gray-400 cursor-pointer">פרטים טכניים</summary>
                            <p className="text-xs text-gray-400 mt-2 break-all" dir="ltr">{raw}</p>
                          </details>
                        )}
                      </div>
                    );
                  })()
                ) : (
                  <div className="bg-white rounded-xl shadow-lg p-8">
                    {/* Movement 1 — productive capture (name + language). Metadata-only. */}
                    {!captureDone && (
                      <div className="mb-6 pb-6 border-b border-surface-200">
                        <h2 className="text-lg font-semibold text-gray-800 text-center">ויוי כבר קוראת את המחוון…</h2>
                        <p className="text-sm text-gray-500 text-center mt-1">בזמן שהיא עובדת, אפשר לתת שם ולבחור שפה — או לדלג.</p>
                        <div className="mt-4 space-y-3">
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">שם המחוון</label>
                            <input
                              type="text"
                              value={rubricName}
                              onChange={e => setRubricName(e.target.value)}
                              placeholder={filenameStem || 'לדוגמה: בגרות תשפ״ו'}
                              className="w-full p-2 border border-surface-300 rounded-lg text-sm"
                              dir="rtl"
                            />
                          </div>
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">שפת תכנות</label>
                            <select
                              value={programmingLanguage}
                              onChange={e => setProgrammingLanguage(e.target.value)}
                              className="w-full p-2 border border-surface-300 rounded-lg text-sm"
                            >
                              <option value="">זיהוי אוטומטי</option>
                              <option value="Java">Java</option>
                              <option value="Python">Python</option>
                              <option value="C++">C++</option>
                              <option value="C#">C#</option>
                              <option value="JavaScript">JavaScript</option>
                              <option value="Pseudocode">פסאודו-קוד</option>
                            </select>
                          </div>
                          <div className="flex items-center justify-end gap-3 pt-1">
                            <button onClick={handleCaptureSkip} className="text-sm text-gray-500 hover:text-gray-700">דלגי</button>
                            <button onClick={handleCaptureConfirm} className="px-4 py-1.5 bg-primary-500 text-white rounded-lg text-sm hover:bg-primary-600">שמרי והמשיכי</button>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Movement 2 — calm honest waiting */}
                    <div className="text-center">
                      <Loader2 className={`mx-auto text-primary-500 mb-4 animate-spin`} size={captureDone ? 64 : 40} />
                      <h2 className="text-lg font-semibold text-gray-800">
                        {getExtractionStageLabel(extractionJob.status?.progress_stage ?? null)}
                      </h2>
                      <p className="text-gray-500 mt-2 text-sm">
                        עלול לקחת 4–5 דקות. אפשר לעזוב את העמוד — החילוץ ימשיך ברקע ונודיע לך כשהוא מוכן.
                      </p>

                      {/* Honest stage checklist — only stages the server actually reported */}
                      {observedStages.length > 0 && (
                        <ul className="mt-4 inline-flex flex-col gap-1.5 text-right">
                          {getExtractionStageOrder()
                            .filter(s => observedStages.includes(s.stage))
                            .map(s => {
                              const isCurrent = s.stage === extractionJob.status?.progress_stage;
                              return (
                                <li key={s.stage} className={`flex items-center gap-2 text-sm ${isCurrent ? 'text-primary-700 font-medium' : 'text-gray-400'}`}>
                                  {isCurrent
                                    ? <Loader2 className="animate-spin" size={14} />
                                    : <CheckCircle size={14} className="text-primary-500" />}
                                  <span>{s.label}</span>
                                </li>
                              );
                            })}
                        </ul>
                      )}

                      {extractionJob.status?.elapsed_seconds != null && (
                        <p className="text-sm text-gray-400 mt-3">
                          {(() => {
                            const s = extractionJob.status.elapsed_seconds;
                            return Math.floor(s / 60) > 0
                              ? `${Math.floor(s / 60)} דק' ${Math.round(s % 60)} שנ'`
                              : `${Math.round(s)} שניות`;
                          })()}
                        </p>
                      )}

                      {/* Threshold reassurances — read off elapsed_seconds, no new timer */}
                      {extractionJob.status?.elapsed_seconds != null && extractionJob.status.elapsed_seconds >= 360 ? (
                        <p className="text-sm text-primary-600 mt-2">כמעט שם — המחוון שלך עשיר במיוחד.</p>
                      ) : extractionJob.status?.elapsed_seconds != null && extractionJob.status.elapsed_seconds >= 180 ? (
                        <p className="text-sm text-primary-600 mt-2">עדיין עובדת — מחוונים מפורטים לוקחים יותר.</p>
                      ) : null}

                      {error && <p className="text-sm text-amber-600 mt-3">{error}</p>}
                    </div>
                  </div>
                )}
              </div>
            )}

            {rubricStep === 'arrival' && (
              <div className="max-w-xl mx-auto animate-fade-in">
                <div className="bg-white rounded-xl shadow-lg p-8">
                  <div className="flex items-center gap-2 text-primary-700">
                    <CheckCircle size={22} />
                    <h2 className="text-xl font-semibold">סיימתי לקרוא את המחוון</h2>
                  </div>
                  {(() => {
                    const selLine = selectionSummaryLine(selectionGroups, extractedQuestions.length);
                    const achievable = computeAchievablePoints(extractedQuestions, selectionGroups);
                    const criteria = countCriteria(extractedQuestions);
                    const findings = countFindings(combinedAnnotations);
                    return (
                      <>
                        {selLine && (
                          <div className="mt-4 inline-block bg-primary-50 border border-primary-200 rounded-lg px-3 py-1.5 text-sm font-semibold text-primary-800">
                            {selLine}
                          </div>
                        )}
                        <dl className="mt-4 grid grid-cols-3 gap-3 text-center">
                          <div className="bg-surface-50 rounded-lg p-3">
                            <dt className="text-xs text-gray-500">שאלות</dt>
                            <dd className="text-lg font-semibold text-gray-800">{extractedQuestions.length}</dd>
                          </div>
                          <div className="bg-surface-50 rounded-lg p-3">
                            <dt className="text-xs text-gray-500">נקודות</dt>
                            <dd className="text-lg font-semibold text-gray-800">{achievable}</dd>
                          </div>
                          <div className="bg-surface-50 rounded-lg p-3">
                            <dt className="text-xs text-gray-500">קריטריונים</dt>
                            <dd className="text-lg font-semibold text-gray-800">{criteria}</dd>
                          </div>
                        </dl>
                        <div className={`mt-4 rounded-lg px-4 py-3 text-sm font-medium ${findings > 0 ? 'bg-amber-50 border border-amber-200 text-amber-800' : 'bg-green-50 border border-green-200 text-green-800'}`}>
                          {findingsWaitingLabel(findings)}
                        </div>
                        <button
                          onClick={() => setRubricStep('review')}
                          className="mt-6 w-full flex items-center justify-center gap-2 bg-primary-500 text-white px-6 py-2.5 rounded-lg hover:bg-primary-600 transition-colors font-medium"
                        >
                          עברי על המחוון
                          <ArrowLeft size={18} />
                        </button>
                      </>
                    );
                  })()}
                </div>
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
                    questions={extractedQuestions}
                    onDismiss={() => setSaveError(null)}
                  />
                )}
                {/* R-D: explicit warning confirmation (replaces the silent auto-ack).
                    Shown when save returns warnings; only an explicit confirm resends
                    the held draft with acked ids. */}
                {pendingWarnings && (
                  <RubricWarningsModal
                    warnings={pendingWarnings.warnings}
                    messageHe={pendingWarnings.message_he}
                    questions={extractedQuestions}
                    onAcknowledge={handleConfirmWarnings}
                    onCancel={handleCancelWarnings}
                    isSubmitting={isLoading}
                  />
                )}
                {/* S1-6.1: honest save overlay — ONE static line, no fake staging
                    (the client cannot observe compile stages). */}
                {isLoading && (
                  <div className="fixed inset-0 z-50 bg-black/20 flex items-center justify-center">
                    <div className="bg-white rounded-xl shadow-xl px-8 py-6 flex items-center gap-3">
                      <Loader2 className="animate-spin text-primary-500" size={22} />
                      <span className="text-gray-700">ויוי בודקת עקביות ומרכיבה את חוזה הניקוד…</span>
                    </div>
                  </div>
                )}
                {/* D-1: the DOCUMENT MIRROR is the review surface (docx flow). It owns
                    its own content card + rail layout, so NO outer card here; the footer
                    is rail-aligned to the content column. RubricEditor (rollback) keeps
                    its card. */}
                {USE_DOCUMENT_MIRROR ? (
                  <>
                    <RubricDocument
                      questions={extractedQuestions}
                      onQuestionsChange={handleQuestionsEdited}
                      annotations={combinedAnnotations}
                      errorBannerRef={errorBannerRef}
                      rubricName={rubricName}
                      rubricTotalPoints={rubricDeclaredTotal}
                      onTotalPointsChange={handleTotalPointsChange}
                      onMetadataChange={handleRubricMetadataChange}
                      selectionGroups={selectionGroups}
                      canUndo={canUndoRubric}
                      onUndo={undoRubricEdit}
                    />
                    {error && (
                      <div className="flex gap-8 justify-center mt-4" dir="rtl">
                        <div className="hidden rail:block w-rail flex-shrink-0" aria-hidden />
                        <div className="flex-1 min-w-0 max-w-document p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-doc-table">{error}</div>
                      </div>
                    )}
                    <div className="flex gap-8 justify-center mt-6" dir="rtl">
                      <div className="hidden rail:block w-rail flex-shrink-0" aria-hidden />
                      <div className="flex-1 min-w-0 max-w-document flex items-center justify-between pt-4 border-t border-surface-200">
                        <BackButton onClick={() => { if (confirmDiscardIfDirty()) { dirtyRef.current = false; clearRubricHistory(); setRubricStep('upload'); } }} />
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
                  </>
                ) : (
                  <div className="bg-white rounded-xl shadow-lg p-6">
                    <RubricEditor
                      questions={extractedQuestions}
                      onQuestionsChange={handleQuestionsEdited}
                      pages={rubricPages}
                      sourceType="docx"
                      metadata={extractionMetadata || undefined}
                      annotations={combinedAnnotations}
                      errorBannerRef={errorBannerRef}
                      programmingLanguage={programmingLanguage}
                      rubricName={rubricName}
                      rubricTotalPoints={rubricDeclaredTotal}
                      onTotalPointsChange={handleTotalPointsChange}
                      onMetadataChange={handleRubricMetadataChange}
                      hasNameError={!!error && !rubricName.trim()}
                    />
                    {error && <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{error}</div>}
                    <div className="mt-6 pt-4 border-t border-surface-200 flex items-center justify-between">
                      <BackButton onClick={() => { if (confirmDiscardIfDirty()) { dirtyRef.current = false; clearRubricHistory(); setRubricStep('upload'); } }} />
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
                )}
              </div>
            )}

            {rubricStep === 'saved' && (
              <div className="max-w-xl mx-auto animate-fade-in">
                {(() => {
                  // S1-6.2 / S1-7.1: her rubric's NAME (the UUID is dead), the facts,
                  // the partnership beat, and a CTA that CARRIES the rubric to grading.
                  const savedName = resolveRubricName(rubricName, inferredName, filenameStem);
                  const achievable = rubricDeclaredTotal ?? computeAchievablePoints(extractedQuestions, selectionGroups);
                  const criteria = countCriteria(extractedQuestions);
                  const carryOnToGrading = () => {
                    if (!savedRubricId) { goToHome(); return; }
                    enterGradingWithRubric({
                      id: savedRubricId,
                      name: savedName,
                      created_at: new Date().toISOString(),
                      is_compiled: true,
                      total_points: achievable,
                      total_questions: extractedQuestions.length,
                    });
                  };
                  return (
                    <div className="bg-white rounded-xl shadow-lg p-8 text-center">
                      <CheckCircle className="mx-auto text-primary-500 mb-4" size={64} />
                      <h2 className="text-2xl font-semibold text-primary-700">{savedName}</h2>
                      <p className="text-gray-500 mt-2 text-sm">
                        {extractedQuestions.length} שאלות · {achievable} נקודות · {criteria} קריטריונים
                      </p>
                      <p className="text-gray-700 mt-5 leading-relaxed">
                        המחוון מוכן — עברת על הכל ואישרת. מכאן ויוי בודקת לפיו.
                      </p>
                      <div className="mt-8 flex flex-col gap-3">
                        <button onClick={carryOnToGrading} className="flex items-center justify-center gap-2 mx-auto bg-primary-500 text-white px-6 py-2.5 rounded-lg hover:bg-primary-600 transition-colors font-medium">
                          <GraduationCap size={18} />המשיכי לבדיקת מבחנים
                        </button>
                        <button onClick={goToHome} className="text-gray-500 hover:text-gray-700 text-sm">לדף הבית</button>
                      </div>
                    </div>
                  );
                })()}
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