// Mirrors backend app/schemas/transcription.py

export type AnnotationSeverity = 'error' | 'warning' | 'info';

export type TranscriptionAnnotationType =
    | 'vlm_uncertainty'
    | 'vlm_unparseable'
    | 'student_name_missing'
    | 'vlm_low_logprob'          // S11: logprob span-min below threshold
    | 'reader_disagreement'      // trust layer: independent readers read this span differently
    | 'code_lint'                // trust layer: deterministic code check (brace balance)
    | 'segmentation_mismatch'    // student's leading marker contradicts the P2-assigned key
    | 'math_notation';           // a LaTeX span that may not render (MATH_RENDERING_PLAN §4) — INFO

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

/** Vivi's READING of a drawing (MATH_RENDERING_PLAN §5) — backend `Figure`. */
export type FigureFeatureKind =
    | 'vertical_asymptote' | 'horizontal_asymptote' | 'minimum' | 'maximum'
    | 'x_intercept' | 'y_intercept' | 'point' | 'shaded_region'
    | 'vertex' | 'side_label' | 'angle_label' | 'segment_label' | 'right_angle_mark'
    | 'axis_label' | 'other_label';

export interface FigureFeature {
    kind: FigureFeatureKind;
    /** LaTeX body, no delimiters — copied from the drawing. */
    as_written: string;
    /** [y, x] on the page's 0–1000 grid; null when she added it by hand. */
    point: number[] | null;
    ink: 'primary' | 'other';
    uncertain: boolean;
    source: 'vivi' | 'teacher';
}

export interface Figure {
    /** N of its `[איור N: …]` line, numbered per page. */
    figure_no: number;
    page_number: number;
    kind: 'function_sketch' | 'geometry' | 'other';
    /** [ymin, xmin, ymax, xmax] on the page's 0–1000 grid. */
    box_2d: number[] | null;
    features: FigureFeature[];
}

export interface TranscriptionDraftAnswer {
    question_number: number;
    sub_question_id: string | null;
    answer_text: string;
    confidence: number;
    page_numbers: number[];
    /** Absent on every draft written before figures existed. */
    figures?: Figure[];
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
    /** The teacher's OWN wording for the choice («ענו על 4 מתוך 6 שאלות»),
     *  carried verbatim from the contract. Display-only, in no rule. Absent or
     *  null when the rubric carried none — the completeness sentence then omits
     *  the prefix instead of inventing a name for her choice. */
    label?: string | null;
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
    /** Her reviewed readings; omitted/null = the draft's stand. */
    figures?: Figure[] | null;
}

export interface GradeQueuedResponse {
    graded_test_id: string;
    status: 'pending';
}

export interface TranscriptionPageResponse {
    page_number: number;
    thumbnail_base64: string;
}
