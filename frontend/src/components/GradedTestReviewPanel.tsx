'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import { AlertTriangle, AlertCircle, Info, Loader2, ChevronRight, ChevronLeft, CheckCircle2, Edit, RotateCcw, Save, ThumbsUp } from 'lucide-react';
import { getTranscriptionPage } from '@/lib/api';
import type {
    GradedTestDraftResponse,
    GradedTestApprovedResponse,
    ScopeOutcome,
    CriterionOutcome,
    SubCriterionOutcome,
    GradingAnnotation,
    GradedTestOverrides,
    TeacherOverride,
} from '@/types/graded_test';

interface Props {
    response: GradedTestDraftResponse | GradedTestApprovedResponse;
    transcriptionId: string;
    onBack: () => void;
    /** When true, the panel shows point inputs, comment fields, and save/approve buttons. */
    editable?: boolean;
    /** Called when the teacher saves overrides without approving. */
    onSaveDraft?: (overrides: GradedTestOverrides) => Promise<void>;
    /** Called when the teacher approves. Receives the final overrides map. */
    onApprove?: (overrides: GradedTestOverrides) => Promise<void>;
    /** S10: Re-grade against the current rubric (only offered when rubric_contract_stale). */
    onRegrade?: () => Promise<void>;
    /** S10: Open the approved grade for manual editing (always offered on approved rows). */
    onManualEdit?: () => Promise<void>;
}

// ---------------------------------------------------------------------------
// Annotation banner
// ---------------------------------------------------------------------------

function GradingAnnotationBanner({ annotation }: { annotation: GradingAnnotation }) {
    const styles: Record<string, string> = {
        error: 'bg-red-50 border-red-300 text-red-800',
        warning: 'bg-amber-50 border-amber-300 text-amber-800',
        info: 'bg-blue-50 border-blue-300 text-blue-700',
    };
    const icons: Record<string, React.ReactNode> = {
        error: <AlertTriangle size={14} className="shrink-0 mt-0.5" />,
        warning: <AlertTriangle size={14} className="shrink-0 mt-0.5" />,
        info: <Info size={14} className="shrink-0 mt-0.5" />,
    };
    return (
        <div className={`flex items-start gap-2 px-3 py-2 border rounded-lg text-sm ${styles[annotation.severity] ?? ''}`}>
            {icons[annotation.severity]}
            <span>{annotation.message}</span>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Evidence quote badge
// ---------------------------------------------------------------------------

function QuoteBadge({ validation_status, quote_text }: { validation_status: string; quote_text: string }) {
    if (!quote_text) return null;
    const styles: Record<string, string> = {
        exact: 'bg-green-50 border-green-300 text-green-800',
        fuzzy: 'bg-amber-50 border-amber-300 text-amber-800',
        not_found: 'bg-red-50 border-red-300 text-red-700',
    };
    const labels: Record<string, string> = { exact: 'ציטוט מדויק', fuzzy: 'ציטוט חלקי', not_found: 'ציטוט לא נמצא' };
    return (
        <div className={`mt-1.5 px-2.5 py-1.5 border rounded text-xs ${styles[validation_status] ?? 'bg-gray-50 border-gray-200'}`}>
            <span className="font-medium">{labels[validation_status] ?? validation_status}: </span>
            <span className="italic">&quot;{quote_text}&quot;</span>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Leaf criterion outcome row (editable or read-only)
// ---------------------------------------------------------------------------

function LeafCriterionRow({ criterion, annotations, editable, override, onOverrideChange }: {
    criterion: CriterionOutcome | SubCriterionOutcome;
    annotations: GradingAnnotation[];
    editable?: boolean;
    override?: TeacherOverride;
    onOverrideChange?: (terminalId: string, override: TeacherOverride) => void;
}) {
    const id = 'criterion_id' in criterion ? criterion.criterion_id : criterion.sub_criterion_id;
    const relevantAnnotations = annotations.filter(a => a.target_id === id);
    const displayPoints = override?.points_awarded ?? criterion.points_awarded;
    const precisionStep = 0.25;  // default; backend rounds to numeric_policy.precision

    return (
        <div className="pl-4 py-2 border-r-2 border-surface-200 mb-2">
            <div className="flex justify-between items-start gap-2">
                <span className="text-sm text-gray-700 flex-1">{criterion.description}</span>

                {editable ? (
                    <div className="flex items-center gap-1.5 shrink-0">
                        <input
                            type="number"
                            min={0}
                            max={parseFloat(criterion.points_possible)}
                            step={precisionStep}
                            value={parseFloat(displayPoints)}
                            onChange={e => {
                                const val = String(e.target.value);
                                onOverrideChange?.(id, {
                                    points_awarded: val,
                                    teacher_comment: override?.teacher_comment ?? null,
                                });
                            }}
                            className="w-16 text-right border border-gray-300 rounded px-2 py-0.5 text-sm font-semibold focus:ring-2 focus:ring-primary-400 focus:border-transparent"
                        />
                        <span className="text-sm text-gray-400">/ {criterion.points_possible}</span>
                    </div>
                ) : (
                    <span className={`text-sm font-semibold whitespace-nowrap ${
                        parseFloat(displayPoints) > 0 ? 'text-green-700' : 'text-red-600'
                    }`}>
                        {displayPoints} / {criterion.points_possible}
                    </span>
                )}
            </div>

            {/* AI reasoning — always read-only (D3) */}
            {criterion.reasoning && (
                <p className="mt-1 text-xs text-gray-500 leading-relaxed">{criterion.reasoning}</p>
            )}
            {criterion.evidence_quote && (
                <QuoteBadge
                    validation_status={criterion.evidence_quote.validation_status}
                    quote_text={criterion.evidence_quote.quote_text}
                />
            )}

            {/* Teacher comment field — only in editable mode */}
            {editable && (
                <textarea
                    value={override?.teacher_comment ?? ''}
                    onChange={e => {
                        onOverrideChange?.(id, {
                            points_awarded: displayPoints,
                            teacher_comment: e.target.value || null,
                        });
                    }}
                    placeholder="הוסף הערה (אופציונלי)"
                    rows={1}
                    className="mt-1.5 w-full text-xs border border-gray-200 rounded px-2 py-1 text-gray-700 placeholder-gray-400 resize-none focus:ring-1 focus:ring-primary-300"
                />
            )}
            {/* Teacher comment display — read-only when not editable but override exists */}
            {!editable && override?.teacher_comment && (
                <p className="mt-1 text-xs text-blue-700 italic">הערת מורה: {override.teacher_comment}</p>
            )}

            {relevantAnnotations.map(ann => (
                <div key={ann.id} className="mt-1">
                    <GradingAnnotationBanner annotation={ann} />
                </div>
            ))}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Scope outcome card
// ---------------------------------------------------------------------------

function ScopeCard({ scope, annotations, index, isLowConfidence, editable, overrides, onOverrideChange }: {
    scope: ScopeOutcome;
    annotations: GradingAnnotation[];
    index: number;
    isLowConfidence: boolean;
    editable?: boolean;
    overrides?: GradedTestOverrides;
    onOverrideChange?: (terminalId: string, override: TeacherOverride) => void;
}) {
    const [expanded, setExpanded] = useState(true);
    const scopeId = scope.sub_question_id
        ? `${scope.question_id}.${scope.sub_question_id}`
        : scope.question_id;
    const scopeAnnotations = annotations.filter(a => a.target_id === scopeId);
    const errorAnnotations = scopeAnnotations.filter(a => a.severity === 'error');

    // Live-compute scope awarded from overrides (for display when editable)
    const effectiveScopeAwarded = useMemo(() => {
        if (!editable || !overrides) return parseFloat(scope.points_awarded);
        return scope.criterion_outcomes.reduce((scopeSum, co) => {
            if (co.sub_criterion_outcomes && co.sub_criterion_outcomes.length > 0) {
                return scopeSum + co.sub_criterion_outcomes.reduce((subSum, sc) => {
                    const ov = overrides[sc.sub_criterion_id];
                    return subSum + parseFloat(ov?.points_awarded ?? sc.points_awarded);
                }, 0);
            }
            const ov = overrides[co.criterion_id];
            return scopeSum + parseFloat(ov?.points_awarded ?? co.points_awarded);
        }, 0);
    }, [scope, overrides, editable]);

    const ptsPossible = parseFloat(scope.points_possible);
    const pctStr = ptsPossible > 0
        ? `${Math.round((effectiveScopeAwarded / ptsPossible) * 100)}%`
        : '—';

    return (
        <div className={`bg-white rounded-xl border shadow-sm mb-3 ${
            errorAnnotations.length > 0 ? 'border-red-300' : 'border-surface-200'
        }`}>
            {/* Scope header */}
            <button
                className="w-full flex items-center justify-between px-4 py-3 text-right"
                onClick={() => setExpanded(e => !e)}
            >
                <div className="flex items-center gap-2 flex-1 min-w-0">
                    <span className="text-xs text-gray-400 font-mono">{scopeId}</span>
                    {isLowConfidence && (
                        <span className="text-xs bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded">
                            ביטחון נמוך
                        </span>
                    )}
                    {scope.graded_by === 'skipped_no_answer' && (
                        <span className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">אין תשובה</span>
                    )}
                    {scope.graded_by === 'failed' && (
                        <span className="text-xs bg-red-100 text-red-600 px-1.5 py-0.5 rounded">שגיאת AI</span>
                    )}
                    {/* PR-4 (census F11): a "choose k of N" member that did not make the
                        student's best-k. EXCLUDED, not zeroed — the unchosen question was
                        never owed. Backend signals this purely via graded_by (no annotation),
                        so this badge is the only place the teacher sees the state named. */}
                    {scope.graded_by === 'excluded_by_selection' && (
                        <span
                            className="text-xs bg-indigo-50 text-indigo-600 border border-indigo-200 px-1.5 py-0.5 rounded"
                            title="שאלת בחירה: נספרות רק התשובות הטובות ביותר. סעיף זה לא נכלל בציון — הוא לא נדרש."
                        >
                            לא נבחר למענה (שאלת בחירה)
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-3">
                    <span className="text-sm font-semibold text-gray-800">
                        {editable ? effectiveScopeAwarded.toFixed(2).replace(/\.?0+$/, '') : scope.points_awarded}
                        {' '}/ {scope.points_possible}
                        <span className="text-gray-400 font-normal ml-1 text-xs">({pctStr})</span>
                    </span>
                    {expanded ? <ChevronRight size={16} className="text-gray-400 rotate-90" /> : <ChevronLeft size={16} className="text-gray-400 -rotate-90" />}
                </div>
            </button>

            {expanded && (
                <div className="px-4 pb-3 border-t border-surface-100">
                    {/* Scope-level annotations */}
                    {scopeAnnotations.length > 0 && (
                        <div className="mt-2 space-y-1">
                            {scopeAnnotations.map(ann => (
                                <GradingAnnotationBanner key={ann.id} annotation={ann} />
                            ))}
                        </div>
                    )}

                    {/* Criteria */}
                    <div className="mt-3 space-y-1">
                        {scope.criterion_outcomes.map(co => (
                            co.sub_criterion_outcomes && co.sub_criterion_outcomes.length > 0
                                ? (
                                    <div key={co.criterion_id}>
                                        {/* Branch criterion header — read-only computed total */}
                                        <div className="flex justify-between items-center text-xs font-medium text-gray-500 mb-1">
                                            <span>{co.description}</span>
                                            {editable && overrides && (
                                                <span className="text-gray-400">
                                                    {co.sub_criterion_outcomes.reduce((sum, sc) => {
                                                        const ov = overrides[sc.sub_criterion_id];
                                                        return sum + parseFloat(ov?.points_awarded ?? sc.points_awarded);
                                                    }, 0).toFixed(2).replace(/\.?0+$/, '')}
                                                    {' '}/ {co.points_possible}
                                                </span>
                                            )}
                                        </div>
                                        {co.sub_criterion_outcomes.map(sc => (
                                            <LeafCriterionRow
                                                key={sc.sub_criterion_id}
                                                criterion={sc}
                                                annotations={annotations}
                                                editable={editable}
                                                override={overrides?.[sc.sub_criterion_id]}
                                                onOverrideChange={onOverrideChange}
                                            />
                                        ))}
                                    </div>
                                )
                                : (
                                    <LeafCriterionRow
                                        key={co.criterion_id}
                                        criterion={co}
                                        annotations={annotations}
                                        editable={editable}
                                        override={overrides?.[co.criterion_id]}
                                        onOverrideChange={onOverrideChange}
                                    />
                                )
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main panel
// ---------------------------------------------------------------------------

/**
 * PR-3 / B-5 — the guard for this screen's aggregate.
 *
 * TRUE when the client CANNOT faithfully reproduce the server's score, so no live
 * aggregate may be shown. On a "choose k of N" exam the server counts only the
 * student's best-k and divides by the ACHIEVABLE total; any client-side sum over all
 * scopes is therefore the wrong numerator over the right denominator.
 *
 * Exported for test: the invariant ("never display an aggregate that could disagree
 * with what approval would freeze") is worth pinning independently of the render.
 */
export function hasSelectionExclusions(
    scopes: Array<{ graded_by: string }>,
): boolean {
    return scopes.some(s => s.graded_by === 'excluded_by_selection');
}

export function GradedTestReviewPanel({ response, transcriptionId, onBack, editable, onSaveDraft, onApprove, onRegrade, onManualEdit }: Props) {
    const { draft } = response;

    // Local override state — only changed terminals appear in the map
    const [overrides, setOverrides] = useState<GradedTestOverrides>(() => {
        // Seed with existing overrides from the draft (e.g., after a PATCH save)
        return { ...draft.teacher_overrides };
    });

    const [saving, setSaving] = useState(false);
    const [approving, setApproving] = useState(false);
    const [actionError, setActionError] = useState<string | null>(null);
    const [gateViolations, setGateViolations] = useState<unknown[] | null>(null);

    const handleOverrideChange = useCallback((terminalId: string, override: TeacherOverride) => {
        setOverrides(prev => ({ ...prev, [terminalId]: override }));
        setActionError(null);
        setGateViolations(null);
    }, []);

    const handleSaveDraft = async () => {
        if (!onSaveDraft) return;
        setSaving(true);
        setActionError(null);
        try {
            await onSaveDraft(overrides);
        } catch (err: unknown) {
            setActionError(err instanceof Error ? err.message : 'שגיאה בשמירה');
        } finally {
            setSaving(false);
        }
    };

    const handleApprove = async () => {
        if (!onApprove) return;
        setApproving(true);
        setActionError(null);
        setGateViolations(null);
        try {
            await onApprove(overrides);
        } catch (err: unknown) {
            const e = err as Error & { gateViolations?: unknown[] };
            setActionError(e.message ?? 'שגיאה באישור');
            if (e.gateViolations) setGateViolations(e.gateViolations);
        } finally {
            setApproving(false);
        }
    };

    // Sort scopes by min_confidence ascending (least-confident first)
    const sortedScopes = useMemo(() =>
        [...draft.scope_outcomes].sort((a, b) => a.min_confidence - b.min_confidence),
        [draft.scope_outcomes]
    );

    // Live total from current overrides
    const runningTotal = useMemo(() => {
        return sortedScopes.reduce((total, scope) => {
            return total + scope.criterion_outcomes.reduce((scopeSum, co) => {
                if (co.sub_criterion_outcomes && co.sub_criterion_outcomes.length > 0) {
                    return scopeSum + co.sub_criterion_outcomes.reduce((subSum, sc) => {
                        const ov = overrides[sc.sub_criterion_id];
                        return subSum + parseFloat(ov?.points_awarded ?? sc.points_awarded);
                    }, 0);
                }
                const ov = overrides[co.criterion_id];
                return scopeSum + parseFloat(ov?.points_awarded ?? co.points_awarded);
            }, 0);
        }, 0);
    }, [sortedScopes, overrides]);

    const totalPossible = parseFloat(response.total_possible ?? '0');
    const hasErrorAnnotations = draft.annotations.some(a => a.severity === 'error');

    // Source pane state
    const [selectedPage, setSelectedPage] = useState(1);
    const [pageCache, setPageCache] = useState<Record<number, string>>({});
    const [loadingPage, setLoadingPage] = useState(false);
    const [pageLoadError, setPageLoadError] = useState<string | null>(null);
    const [activeMobilePane, setActiveMobilePane] = useState<'outcomes' | 'source'>('outcomes');

    const fetchPage = useCallback(async (pageNumber: number) => {
        if (pageCache[pageNumber]) { setSelectedPage(pageNumber); return; }
        setLoadingPage(true);
        setPageLoadError(null);
        try {
            const result = await getTranscriptionPage(transcriptionId, pageNumber);
            setPageCache(prev => ({ ...prev, [pageNumber]: result.thumbnail_base64 }));
            setSelectedPage(pageNumber);
        } catch (err: unknown) {
            setPageLoadError(err instanceof Error ? err.message : 'שגיאה בטעינת הדף');
        } finally {
            setLoadingPage(false);
        }
    }, [pageCache, transcriptionId]);

    // eslint-disable-next-line react-hooks/exhaustive-deps
    useEffect(() => { void fetchPage(1); }, []);

    const globalAnnotations = draft.annotations.filter(a =>
        !draft.scope_outcomes.some(so => {
            const sid = so.sub_question_id
                ? `${so.question_id}.${so.sub_question_id}`
                : so.question_id;
            return a.target_id === sid;
        })
    );
    const errorCount = draft.annotations.filter(a => a.severity === 'error').length;

    const isApproved = response.status === 'approved';

    // ── THE INVARIANT FOR THIS SCREEN (PR-3 / B-5) ──────────────────────────────
    // NEVER display an aggregate that could disagree with what approval would freeze.
    // When that number is not computable client-side, show NO live aggregate rather
    // than a wrong one.
    //
    // `runningTotal` sums EVERY scope. On a "choose k of N" exam the server counts
    // only the student's best-k and divides by the ACHIEVABLE total, so this sum is
    // simply the wrong numerator — it over-counts the excluded members against an
    // achievable denominator. Showing it would recreate, on the teacher's screen, the
    // exact "reviewed number ≠ recorded number" disagreement that PR-3 spent its whole
    // effort eliminating between the grading runner and the approval gate.
    //
    // We also cannot just print the server's number as if it were live: while the
    // teacher is editing overrides that value is STALE, and a stale number rendered as
    // current is merely a different lie. So on selection exams we show the server's
    // last-computed figure, explicitly labelled as such, and no live percentage.
    //
    // A correct LIVE preview would have to re-run best-k client-side, because an
    // override can flip which member wins the slot (bump the 15-pointer above the
    // 50-pointer and membership changes). That is real work, not a one-liner — it is
    // B-5 → PR-4, deliberately not improvised into this merge.
    const isSelectionExam = hasSelectionExclusions(sortedScopes);
    const canDeriveAggregate = !isSelectionExam;

    const displayTotal = editable && canDeriveAggregate
        ? runningTotal.toFixed(2).replace(/\.?0+$/, '')
        : (response.total_score ?? '—');
    const pctDisplay = canDeriveAggregate && totalPossible > 0
        ? `${((editable ? runningTotal : parseFloat(response.total_score ?? '0')) / totalPossible * 100).toFixed(1)}%`
        : null;

    return (
        <div dir="rtl" className="min-h-screen bg-gradient-to-br from-surface-50 via-primary-50/20 to-surface-100">
            {/* Header */}
            <div className="sticky top-0 z-10 bg-white/80 backdrop-blur border-b border-surface-200 px-6 py-4 flex items-center justify-between gap-4 flex-wrap">
                <div className="flex items-center gap-3">
                    <button
                        onClick={onBack}
                        className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 transition-colors"
                    >
                        <ChevronRight size={16} />
                        חזרה
                    </button>
                    <span className="text-gray-300">|</span>
                    <h1 className="text-lg font-semibold text-gray-900">
                        {isApproved ? 'בדיקה מאושרת' : 'עריכת בדיקה'}
                    </h1>
                    {response.student_name && (
                        <span className="text-sm text-gray-500">— {response.student_name}</span>
                    )}
                </div>

                {/* Live score + actions */}
                <div className="flex items-center gap-3 flex-wrap">
                    {response.total_possible !== null && (
                        <div className="flex items-center gap-2">
                            <CheckCircle2 size={18} className={isApproved ? 'text-green-500' : 'text-primary-500'} />
                            <span className="text-base font-bold text-gray-900">
                                {displayTotal} / {response.total_possible}
                            </span>
                            {pctDisplay && (
                                <span className="text-sm text-gray-500">({pctDisplay})</span>
                            )}
                            {/* Selection exam: the aggregate is NOT live. Say so, plainly —
                                per-scope points below still update as the teacher edits. */}
                            {isSelectionExam && editable && (
                                <span
                                    className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded px-2 py-0.5"
                                    title="במבחן בחירה נספרות רק התשובות הטובות ביותר; הסכום הסופי מחושב בשרת בעת השמירה"
                                >
                                    סה״כ סופי מחושב בשמירה (מבחן בחירה)
                                </span>
                            )}
                        </div>
                    )}

                    {/* S9 approve actions */}
                    {editable && !isApproved && (
                        <>
                            <button
                                onClick={handleSaveDraft}
                                disabled={saving || approving}
                                className="flex items-center gap-1.5 px-3 py-1.5 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors"
                            >
                                <Save size={14} />
                                {saving ? 'שומר...' : 'שמור טיוטה'}
                            </button>
                            <button
                                onClick={handleApprove}
                                disabled={approving || saving || hasErrorAnnotations}
                                title={hasErrorAnnotations ? 'יש לפתור את כל השגיאות לפני האישור' : undefined}
                                className="flex items-center gap-1.5 px-3 py-1.5 bg-primary-600 text-white rounded-lg text-sm font-medium hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                            >
                                <ThumbsUp size={14} />
                                {approving ? 'מאשר...' : 'אשר ציון'}
                            </button>
                        </>
                    )}
                </div>

                {/* Mobile tab switcher */}
                <div className="flex lg:hidden gap-1 bg-surface-100 rounded-lg p-0.5">
                    <button
                        className={`px-3 py-1 rounded-md text-sm font-medium transition-all ${
                            activeMobilePane === 'outcomes'
                                ? 'bg-white shadow-sm text-gray-900'
                                : 'text-gray-500'
                        }`}
                        onClick={() => setActiveMobilePane('outcomes')}
                    >
                        תוצאות
                    </button>
                    <button
                        className={`px-3 py-1 rounded-md text-sm font-medium transition-all ${
                            activeMobilePane === 'source'
                                ? 'bg-white shadow-sm text-gray-900'
                                : 'text-gray-500'
                        }`}
                        onClick={() => setActiveMobilePane('source')}
                    >
                        מקור
                    </button>
                </div>
            </div>

            {/* Error annotation summary — blocks approval */}
            {errorCount > 0 && (
                <div className="mx-6 mt-3 px-4 py-3 bg-red-50 border border-red-300 rounded-xl flex items-start gap-2 text-sm text-red-800">
                    <AlertTriangle size={16} className="shrink-0 mt-0.5" />
                    <span>
                        נמצאו {errorCount} בעיות בבדיקה שחייבות פתרון לפני האישור.
                        {editable && ' כפתור האישור ינעל עד לפתרונן.'}
                    </span>
                </div>
            )}

            {/* Gate violations from server (422) */}
            {gateViolations && gateViolations.length > 0 && (
                <div className="mx-6 mt-3 px-4 py-3 bg-red-50 border border-red-300 rounded-xl text-sm text-red-800">
                    <div className="flex items-center gap-2 mb-1 font-medium">
                        <AlertTriangle size={16} />
                        האישור נדחה — תקן את הבעיות הבאות:
                    </div>
                    <ul className="list-disc list-inside space-y-0.5">
                        {(gateViolations as Array<{message: string}>).map((v, i) => (
                            <li key={i}>{v.message}</li>
                        ))}
                    </ul>
                </div>
            )}

            {/* Action error (non-gate) */}
            {actionError && !gateViolations && (
                <div className="mx-6 mt-3 px-4 py-3 bg-red-50 border border-red-300 rounded-xl text-sm text-red-800 flex items-center gap-2">
                    <AlertTriangle size={16} />
                    {actionError}
                </div>
            )}

            {/* S10: Approved — confirmation + revision affordances */}
            {isApproved && (
                <div className="mx-6 mt-3 space-y-2">
                    <div className="px-4 py-3 bg-green-50 border border-green-300 rounded-xl flex items-center gap-2 text-sm text-green-800">
                        <CheckCircle2 size={16} className="shrink-0" />
                        הבדיקה אושרה ונעולה.
                    </div>

                    {/* Stale rubric badge */}
                    {'rubric_contract_stale' in response && response.rubric_contract_stale && (
                        <div className="px-4 py-3 bg-amber-50 border border-amber-300 rounded-xl flex items-center gap-2 text-sm text-amber-800">
                            <AlertCircle size={16} className="shrink-0" />
                            הציון נקבע לפי גרסה ישנה של המחוון — ניתן לבדוק מחדש לפי הגרסה הנוכחית.
                        </div>
                    )}

                    {/* Revision action buttons */}
                    {(onManualEdit || onRegrade) && (
                        <div className="flex gap-2 flex-wrap">
                            {onManualEdit && (
                                <button
                                    onClick={onManualEdit}
                                    className="flex items-center gap-1.5 px-3 py-1.5 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                                >
                                    <Edit size={14} />
                                    עריכה ידנית
                                </button>
                            )}
                            {'rubric_contract_stale' in response && response.rubric_contract_stale && onRegrade && (
                                <button
                                    onClick={onRegrade}
                                    className="flex items-center gap-1.5 px-3 py-1.5 border border-amber-400 bg-amber-50 rounded-lg text-sm text-amber-800 hover:bg-amber-100 transition-colors"
                                >
                                    <RotateCcw size={14} />
                                    בדיקה מחדש לפי מחוון עדכני
                                </button>
                            )}
                        </div>
                    )}
                </div>
            )}

            {/* S10: Minimal revision note — shown when this is a successor row */}
            {'regraded_from_id' in response && response.regraded_from_id && (
                <div className="mx-6 mt-2 px-3 py-1.5 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-700">
                    <Info size={12} className="inline ml-1 shrink-0" />
                    זהו ציון מעודכן — גרסה חדשה של בדיקה קודמת.
                </div>
            )}

            {/* Two-pane layout */}
            <div className="flex flex-col lg:flex-row gap-0 lg:gap-6 p-4 lg:p-6">
                {/* Outcomes pane */}
                <div className={`lg:w-1/2 ${activeMobilePane === 'source' ? 'hidden lg:block' : ''}`}>
                    {/* Global annotations */}
                    {globalAnnotations.length > 0 && (
                        <div className="mb-3 space-y-1">
                            {globalAnnotations.map(ann => (
                                <GradingAnnotationBanner key={ann.id} annotation={ann} />
                            ))}
                        </div>
                    )}

                    {/* Read-only note — only when not editable */}
                    {!editable && !isApproved && (
                        <div className="mb-3 px-3 py-2 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-700">
                            <Info size={12} className="inline ml-1" />
                            קריאה בלבד — עריכת ציונים ואישור יהיו זמינים בשלב האישור
                        </div>
                    )}

                    {/* Scope cards sorted by confidence */}
                    {sortedScopes.map((scope, idx) => (
                        <ScopeCard
                            key={`${scope.question_id}.${scope.sub_question_id ?? ''}`}
                            scope={scope}
                            annotations={draft.annotations}
                            index={idx}
                            isLowConfidence={scope.min_confidence < 0.6 && scope.graded_by === 'llm'}
                            editable={editable && !isApproved}
                            overrides={overrides}
                            onOverrideChange={handleOverrideChange}
                        />
                    ))}

                    {/* Unmatched answers */}
                    {draft.unmatched_transcription_answers.length > 0 && (
                        <div className="mt-2 px-3 py-2 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-700">
                            <AlertTriangle size={12} className="inline ml-1" />
                            {draft.unmatched_transcription_answers.length} תשובות לא הותאמו לשאלות במחוון
                        </div>
                    )}
                </div>

                {/* Source pane */}
                <div className={`lg:w-1/2 ${activeMobilePane === 'outcomes' ? 'hidden lg:block' : ''}`}>
                    <div className="bg-white rounded-xl border border-surface-200 shadow-sm p-4 sticky top-24">
                        {/* Page navigation */}
                        <div className="flex items-center justify-between mb-3">
                            <button
                                onClick={() => fetchPage(selectedPage - 1)}
                                disabled={selectedPage <= 1 || loadingPage}
                                className="p-1.5 rounded-lg hover:bg-surface-100 disabled:opacity-40 transition-colors"
                            >
                                <ChevronRight size={18} className="text-gray-600" />
                            </button>
                            <span className="text-sm text-gray-500">
                                עמ&apos; {selectedPage}
                            </span>
                            <button
                                onClick={() => fetchPage(selectedPage + 1)}
                                disabled={loadingPage}
                                className="p-1.5 rounded-lg hover:bg-surface-100 disabled:opacity-40 transition-colors"
                            >
                                <ChevronLeft size={18} className="text-gray-600" />
                            </button>
                        </div>

                        {/* Page image */}
                        {loadingPage && (
                            <div className="flex items-center justify-center h-64">
                                <Loader2 size={28} className="animate-spin text-primary-400" />
                            </div>
                        )}
                        {pageLoadError && !loadingPage && (
                            <div className="flex items-center justify-center h-32 text-sm text-red-600 gap-2">
                                <AlertTriangle size={16} />
                                {pageLoadError}
                            </div>
                        )}
                        {pageCache[selectedPage] && !loadingPage && (
                            <img
                                src={`data:image/png;base64,${pageCache[selectedPage]}`}
                                alt={`עמוד ${selectedPage}`}
                                className="w-full rounded border border-surface-200"
                            />
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
