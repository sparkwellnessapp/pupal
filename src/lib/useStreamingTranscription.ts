/**
 * useStreamingTranscription Hook
 * 
 * A custom React hook that manages the streaming transcription state
 * and provides a clean interface for starting transcription and accessing state.
 * 
 * NEW: Supports two-phase UX:
 * 1. PDF Processing phase (isPdfProcessing=true, pagesReady=false)
 *    - Show loading screen with "מתמלל כתב יד..."
 * 2. Transcription phase (isPdfProcessing=false, pagesReady=true)
 *    - Navigate to TranscriptionReviewPage
 *    - VLM streaming happens here
 * 
 * Usage:
 * ```tsx
 * const streaming = useStreamingTranscription({
 *   onPagesReady: () => {
 *     // Navigate to review page when PDF processing is done
 *     setStep('review_transcription');
 *   },
 *   onComplete: (data) => console.log('Done!'),
 *   onError: (err) => console.error(err),
 * });
 * 
 * // Start streaming when file is uploaded
 * streaming.startTranscription(rubricId, file);
 * 
 * // Show loading screen while PDF is processing
 * if (streaming.isPdfProcessing) {
 *   return <PdfProcessingPage filename={file.name} />;
 * }
 * 
 * // Show review page once pages are ready
 * if (streaming.pagesReady) {
 *   return <TranscriptionReviewPage ... />;
 * }
 * ```
 */

import { useReducer, useCallback, useRef, useMemo, useEffect } from 'react';
import {
    streamTranscriptionV2,
    streamReducer,
    createInitialStreamState,
    streamStateToReviewResponse,
    type TranscriptionStreamState,
    type StreamAction,
    type TranscriptionReviewResponse,
    type TranscriptionPhase,
} from '@/lib/api';

interface UseStreamingTranscriptionOptions {
    // NEW: Callback when PDF processing is complete and pages are ready
    // Use this to trigger navigation to the review page
    onPagesReady?: (data: { pages: number; studentName: string; filename: string }) => void;
    // Callback when streaming completes successfully
    onComplete?: (data: TranscriptionReviewResponse) => void;
    // Callback when an error occurs
    onError?: (error: string) => void;
}

interface UseStreamingTranscriptionReturn {
    // The full streaming state
    state: TranscriptionStreamState;

    // Start streaming transcription
    startTranscription: (
        rubricId: string,
        testFile: File,
        options?: {
            firstPageIndex?: number;
            answeredQuestions?: number[];
        }
    ) => void;

    // Abort the current stream
    abort: () => void;

    // Reset state to initial
    reset: () => void;

    // NEW: PDF processing phase flags
    isPdfProcessing: boolean;  // True while waiting for pages (before review page)
    pagesReady: boolean;       // True once all page thumbnails received

    // Transcription phase flags
    isTranscribing: boolean;   // True while VLM is streaming text
    isVerifying: boolean;      // True during verification phase
    isComplete: boolean;       // True when all done
    hasError: boolean;

    // Current phase
    currentPhase: TranscriptionPhase;
    phaseMessage: string;

    // Progress info
    currentPage: number;
    totalPages: number;
    progressPercent: number;
    pagesReceived: number;     // NEW: Count of pages received so far

    // Converted data for TranscriptionReviewPage
    transcriptionData: TranscriptionReviewResponse | null;

    // Get display text for a specific page (verified if available, else raw)
    getPageDisplayText: (pageNumber: number) => string;

    // Check if a page is currently streaming
    isPageStreaming: (pageNumber: number) => boolean;
}

export function useStreamingTranscription(
    options?: UseStreamingTranscriptionOptions
): UseStreamingTranscriptionReturn {
    const [state, dispatch] = useReducer(streamReducer, createInitialStreamState());
    const abortRef = useRef<{ abort: () => void } | null>(null);

    // Track if onPagesReady has been called (to avoid duplicate calls)
    const pagesReadyCalledRef = useRef(false);

    // Track total pages expected (from metadata)
    const expectedPagesRef = useRef(0);

    // Start streaming
    const startTranscription = useCallback((
        rubricId: string,
        testFile: File,
        streamOptions?: {
            firstPageIndex?: number;
            answeredQuestions?: number[];
        }
    ) => {
        // Reset state first
        dispatch({ type: 'RESET' });
        pagesReadyCalledRef.current = false;
        expectedPagesRef.current = 0;

        // Abort any existing stream
        abortRef.current?.abort();

        // Start new stream
        const handle = streamTranscriptionV2(
            rubricId,
            testFile,
            {
                onMetadata: (data) => {
                    expectedPagesRef.current = data.totalPages;
                    dispatch({ type: 'METADATA', payload: data });
                },
                onPage: (page) => {
                    dispatch({ type: 'PAGE', payload: page });
                },
                onPhase: (phase, currentPage, totalPages, message) =>
                    dispatch({ type: 'PHASE', payload: { phase, currentPage, totalPages, message } }),
                onRawChunk: (pageNumber, delta) =>
                    dispatch({ type: 'RAW_CHUNK', payload: { pageNumber, delta } }),
                onRawComplete: (pageNumber, fullText) =>
                    dispatch({ type: 'RAW_COMPLETE', payload: { pageNumber, fullText } }),
                onVerifiedChunk: (pageNumber, delta) =>
                    dispatch({ type: 'VERIFIED_CHUNK', payload: { pageNumber, delta } }),
                onPageComplete: (pageNumber, pageIndex, markedText, detectedQuestions, confidenceScores) =>
                    dispatch({ type: 'PAGE_COMPLETE', payload: { pageNumber, pageIndex, markedText, detectedQuestions, confidenceScores } }),
                onAnswer: (answer) => dispatch({ type: 'ANSWER', payload: answer }),
                onDone: (totalAnswers) => {
                    dispatch({ type: 'DONE', payload: { totalAnswers } });
                },
                onError: (message) => {
                    dispatch({ type: 'ERROR', payload: { message } });
                    options?.onError?.(message);
                },
            },
            {
                ...streamOptions,
            }
        );

        abortRef.current = handle;
    }, [options]);

    // Abort streaming
    const abort = useCallback(() => {
        abortRef.current?.abort();
        abortRef.current = null;
    }, []);

    // Reset state
    const reset = useCallback(() => {
        abort();
        pagesReadyCalledRef.current = false;
        expectedPagesRef.current = 0;
        dispatch({ type: 'RESET' });
    }, [abort]);

    // Computed values
    const pagesReceived = state.pages.length;
    const totalPages = state.totalPages || expectedPagesRef.current;

    // PDF processing is done when we have all pages OR when transcription phase starts
    const pagesReady = pagesReceived > 0 && (
        pagesReceived >= totalPages ||
        state.currentPhase === 'transcribing' ||
        state.currentPhase === 'verifying' ||
        state.currentPhase === 'done'
    );

    // PDF is still processing if we've started but pages aren't ready yet
    const isPdfProcessing = state.transcriptionId !== '' && !pagesReady && !state.error;

    // Transcription states
    const isTranscribing = state.currentPhase === 'transcribing';
    const isVerifying = state.currentPhase === 'verifying';
    const isComplete = state.isComplete;
    const hasError = !!state.error;

    // Progress
    const progressPercent = useMemo(() => {
        if (totalPages === 0) return 0;
        const completedPages = Array.from(state.pageStates.values())
            .filter(p => p.phase === 'complete').length;
        return Math.round((completedPages / totalPages) * 100);
    }, [state.pageStates, totalPages]);

    // Converted data
    const transcriptionData = useMemo(() => {
        if (!state.transcriptionId) return null;
        return streamStateToReviewResponse(state);
    }, [state]);

    // Get page display text
    const getPageDisplayText = useCallback((pageNumber: number): string => {
        const pageState = state.pageStates.get(pageNumber);
        if (!pageState) return '';
        return pageState.verifiedText || pageState.rawText;
    }, [state.pageStates]);

    // Check if page is streaming
    const isPageStreaming = useCallback((pageNumber: number): boolean => {
        return state.pageStates.get(pageNumber)?.isStreaming ?? false;
    }, [state.pageStates]);

    // Effect: Call onPagesReady when pages become ready
    useEffect(() => {
        if (pagesReady && !pagesReadyCalledRef.current && options?.onPagesReady) {
            pagesReadyCalledRef.current = true;
            options.onPagesReady({
                pages: pagesReceived,
                studentName: state.studentName,
                filename: state.filename,
            });
        }
    }, [pagesReady, pagesReceived, state.studentName, state.filename, options]);

    // Effect: Call onComplete when done
    useEffect(() => {
        if (isComplete && transcriptionData && options?.onComplete) {
            options.onComplete(transcriptionData);
        }
    }, [isComplete, transcriptionData, options]);

    return {
        state,
        startTranscription,
        abort,
        reset,
        isPdfProcessing,
        pagesReady,
        isTranscribing,
        isVerifying,
        isComplete,
        hasError,
        currentPhase: state.currentPhase,
        phaseMessage: state.phaseMessage,
        currentPage: state.currentPage,
        totalPages,
        progressPercent,
        pagesReceived,
        transcriptionData,
        getPageDisplayText,
        isPageStreaming,
    };
}


/**
 * Example usage in a page component:
 * 
 * ```tsx
 * function GradingPage() {
 *   const [step, setStep] = useState<'upload' | 'transcribing' | 'review' | 'grading'>('upload');
 *   const [rubricId, setRubricId] = useState<string | null>(null);
 *   const [testFile, setTestFile] = useState<File | null>(null);
 * 
 *   const streaming = useStreamingTranscription({
 *     onComplete: (data) => {
 *       console.log('Transcription complete:', data);
 *     },
 *     onError: (error) => {
 *       console.error('Transcription error:', error);
 *       setStep('upload');
 *     },
 *   });
 * 
 *   const handleFileUpload = async (file: File) => {
 *     setTestFile(file);
 *     setStep('transcribing');
 *     
 *     // Immediately navigate to review page and start streaming
 *     streaming.startTranscription(rubricId!, file, {
 *       answeredQuestions: [1, 2, 3],
 *     });
 *   };
 * 
 *   if (step === 'transcribing' || step === 'review') {
 *     return (
 *       <TranscriptionReviewPage
 *         rubricId={rubricId!}
 *         testFile={testFile!}
 *         onContinueToGrading={(editedAnswers) => {
 *           // Handle grading with edited answers
 *           setStep('grading');
 *         }}
 *         onBack={() => {
 *           streaming.abort();
 *           setStep('upload');
 *         }}
 *       />
 *     );
 *   }
 * 
 *   // ... rest of component
 * }
 * ```
 */