// Mirrors backend app/schemas/transcription.py

export type AnnotationSeverity = 'error' | 'warning' | 'info';

export type TranscriptionAnnotationType =
    | 'vlm_uncertainty'
    | 'vlm_unparseable'
    | 'student_name_missing'
    | 'vlm_low_logprob'          // S11: logprob span-min below threshold
    | 'reader_disagreement'      // trust layer: independent readers read this span differently
    | 'code_lint'                // trust layer: deterministic code check (brace balance)
    | 'segmentation_mismatch';   // student's leading marker contradicts the P2-assigned key

// metadata payload of a reader_disagreement annotation (backend flagging.FlagSpan)
export interface ReaderDisagreementMetadata {
    page: number;
    line_quote: string;
    transcribed: string;
    alternatives: string[];
    n_readers: number;
    char_start: number;
    char_end: number;
    anchor_similarity: number;
}

export interface TranscriptionAnnotation {
    id: string;
    severity: AnnotationSeverity;
    target_id: string; // "transcription" | "q{n}" | "q{n}.{sub}"
    annotation_type: TranscriptionAnnotationType;
    message: string;
    metadata: Record<string, unknown>;
}

export interface TranscriptionDraftAnswer {
    question_number: number;
    sub_question_id: string | null;
    answer_text: string;
    confidence: number;
    page_numbers: number[];
}

export interface TranscriptionDraft {
    schema_version: string;
    student_name_suggestion: string | null;
    page_count: number;
    answers: TranscriptionDraftAnswer[];
    annotations: TranscriptionAnnotation[];
    model_version: string | null;
    transcription_duration_ms: number | null;
}

/** A rubric SelectionGroup translated into transcription-answer space
 *  (backend `AnswerSpaceSelectionGroup`): "choose k of these question
 *  numbers". Derived server-side; the client never maps rubric ids. */
export interface AnswerSpaceSelectionGroup {
    choose_k: number;
    question_numbers: number[];
}

export interface TranscribeResponse {
    transcription_id: string;
    draft: TranscriptionDraft;
    /** [] for selection-free rubrics — every consumer reduces to old behavior. */
    selection_groups?: AnswerSpaceSelectionGroup[];
}

export interface GradeAnswerInput {
    question_number: number;
    sub_question_id: string | null;
    answer_text: string;
}

export interface GradeQueuedResponse {
    graded_test_id: string;
    status: 'pending';
}

export interface TranscriptionPageResponse {
    page_number: number;
    thumbnail_base64: string;
}
