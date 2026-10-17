'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';

import {
    approveGradeReview, getGradedTestV6, saveGradedTestV6Draft,
    type GradedTestV6Response,
} from '@/lib/api';
import { cmp, dec } from '@/lib/decimal';
import { surfaceError } from '@/lib/errorSurface';
import type { NumericPolicy } from '@/lib/pricing';
import { priceV6 } from '@/lib/pricing-v6';
import type { QueueState } from '@/utils/grade-review-cursor';
import type { QuestionText, WireDraft } from '@/utils/grade-review-model';
import {
    buildV6ReviewModel, chooseOption, clearPin, emptyOverlayV6, feedbackPatch,
    overlayFromWire, overlayPatch, pricingOverlayOf, setComment, setPin, touchedTerminals,
    viewOf, withdrawOption, type OverlayV6,
} from '@/utils/grade-review-v6-model';
import { formatPoints } from '@/utils/points-display';
import { GradeReviewSurfaceV6 } from './GradeReviewSurfaceV6';
import type { ReviewTopBar, SaveState } from './ReviewChrome';
import { RV_LOAD_ERROR, RV_LOADING, RV_PRICING_MISMATCH } from '@/copy/grade-review';

/**
 * The grader-v6 review route body (owner rulings 2026-10-17 §7) — mounted by
 * the review page in place of v5's surface when the draft is a v6 grade.
 *
 * IT OWNS HER WORKING COPY AND ITS AUTOSAVE, exactly as the v5 page does, and
 * for the same reasons:
 *   · saves fire on a 1.5 s idle debounce and again on every exit (prev, next,
 *     approve, a revision, unmount, tab close);
 *   · a FAILED save refuses the navigation and turns the bar red — walking her
 *     on while her decisions exist only in this tab is how judgement is lost;
 *   · an edit made while a save is in flight keeps the dirty flag, so the newer
 *     state is sent next rather than marked saved.
 *
 * WHAT A SAVE SENDS: only what she changed since the server last confirmed —
 * PATCH /v6/draft MERGES (a present key sets, null withdraws, an absent key is
 * left alone) — plus `client_total`, the live pricer's total for exactly that
 * overlay, so the server can say when it prices it differently.
 *
 * THE LINE SHE READS: after an edit, the criteria it touches read
 * «ההסבר מתעדכן…» until the PATCH returns, then show the server's line (its
 * fallback composer — no LLM call anywhere). Lines are never composed here.
 *
 * APPROVAL: flush, then POST /approve with the latest response's `overrides`
 * (her full working copy as the server holds it) and the live pricer's total for
 * that same overlay. A 422 surfaces its `message_he` the way v5's does.
 */

const AUTOSAVE_MS = 1500;

type RevisionProps = NonNullable<React.ComponentProps<typeof ReviewTopBar>['revision']>;

export interface GradeReviewV6Props {
    gradedTestId: string;
    /** The envelope (`GET /graded_test/{id}` → `draft`): her criterion text, the answers. */
    draft: WireDraft;
    /** The row is approved — immutable (LCY-2); every write affordance goes inert. */
    approved: boolean;
    questions: readonly QuestionText[];
    subject?: string | null;

    studentName: string;
    identityMeta: string;
    thumbUrl?: string | null;
    stampPressed?: boolean;
    versionBanner?: { version: number | null } | null;
    revision?: RevisionProps;

    queue: QueueState;
    eta: string | null;
    batchHref: string;
    prevId: string | null;
    nextId: string | null;
    /** The page's own navigation; called only after this route's save landed. */
    onNavigate: (targetId: string) => void;
    onOpenPreview: () => void;
    onShowScan: (scopeId: string, title: string) => void;
    modalOpen?: boolean;
    /** The page's after-approval sequence (cursor, stamp, toast, advance). */
    onApproved: (total: string) => Promise<void>;
}

export function GradeReviewV6(props: GradeReviewV6Props) {
    const {
        gradedTestId, draft, approved, questions, subject = null,
        studentName, identityMeta, thumbUrl = null, stampPressed = false, versionBanner = null,
        revision, queue, eta, batchHref, prevId, nextId, onNavigate, onOpenPreview,
        onShowScan, modalOpen = false, onApproved,
    } = props;

    const [response, setResponse] = useState<GradedTestV6Response | null>(null);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [overlay, setOverlay] = useState<OverlayV6>(emptyOverlayV6);
    const [feedback, setFeedback] = useState<Record<string, string>>({});
    const [feedbackEdited, setFeedbackEdited] = useState<ReadonlySet<string>>(new Set());
    const [saveState, setSaveState] = useState<SaveState>('saved');
    const [approving, setApproving] = useState(false);
    /** criterion → the edit generation that last touched it; cleared as saves land. */
    const [pending, setPending] = useState<ReadonlyMap<string, number>>(new Map());

    const responseRef = useRef<GradedTestV6Response | null>(null);
    /** What the server last CONFIRMED — the base every patch is diffed against. */
    const savedRef = useRef<{ overlay: OverlayV6; feedback: Record<string, string> }>({
        overlay: emptyOverlayV6(), feedback: {},
    });
    /** Her latest working copy, updated synchronously so back-to-back edits compose. */
    const latestRef = useRef<{ overlay: OverlayV6; feedback: Record<string, string> }>({
        overlay: emptyOverlayV6(), feedback: {},
    });
    const dirtyRef = useRef(false);
    const generationRef = useRef(0);
    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    // ── load ──────────────────────────────────────────────────────────────
    useEffect(() => {
        let alive = true;
        getGradedTestV6(gradedTestId)
            .then((data) => {
                if (!alive) return;
                const hers = overlayFromWire(data.overlay);
                const words = { ...(data.overrides.feedback ?? {}) };
                responseRef.current = data;
                savedRef.current = { overlay: hers, feedback: words };
                latestRef.current = { overlay: hers, feedback: words };
                setResponse(data);
                setOverlay(hers);
                setFeedback(words);
                // Hydrating her stored words is not dirt — they are simply hers.
                setFeedbackEdited(new Set(Object.keys(words)));
            })
            .catch(() => { if (alive) setLoadError(RV_LOAD_ERROR); });
        return () => { alive = false; };
    }, [gradedTestId]);

    const terminalOfCheck = useMemo(() => new Map((response?.content.checks ?? []).map(
        (c) => [c.plan.check_id, c.plan.priced_terminal_id])), [response?.content]);
    /** How each check resolves on Vivi's record alone — what «back to Vivi» means. */
    const viviResolved = useMemo(() => new Map(response
        ? priceV6(viewOf(response.content)).checks.map((c) => [c.check_id, c] as const)
        : []), [response?.content]);

    // ── save ──────────────────────────────────────────────────────────────
    /** Returns false when the save failed — every caller treats that as a stop. */
    const flush = useCallback(async (): Promise<boolean> => {
        if (timerRef.current) { clearTimeout(timerRef.current); timerRef.current = null; }
        const current = responseRef.current;
        if (!dirtyRef.current || !current) return true;
        const generation = generationRef.current;
        const sent = latestRef.current;
        const v6 = overlayPatch(savedRef.current.overlay, sent.overlay);
        const words = feedbackPatch(savedRef.current.feedback, sent.feedback);
        const settle = () => {
            setPending((prev) => new Map([...prev].filter(([, g]) => g > generation)));
            if (generationRef.current === generation) {
                dirtyRef.current = false;
                setSaveState('saved');
            }
        };
        if (v6 === null && Object.keys(words).length === 0) {
            settle();                          // she undid her own edit: nothing to send
            return true;
        }
        setSaveState('saving');
        const clientTotal = priceV6(viewOf(current.content), pricingOverlayOf(sent.overlay)).total_score;
        try {
            const saved = await saveGradedTestV6Draft(gradedTestId, {
                ...(v6 ? { v6 } : {}),
                feedback: words,
                client_total: clientTotal,
            });
            responseRef.current = saved;
            savedRef.current = {
                overlay: overlayFromWire(saved.overlay),
                feedback: { ...(saved.overrides.feedback ?? {}) },
            };
            setResponse(saved);
            settle();
            // The server priced the same overlay. Saying so NOW is the point of
            // sending the total: otherwise drift surfaces only when /approve refuses.
            if (cmp(dec(saved.priced.total_score), dec(clientTotal)) !== 0) {
                toast.error(RV_PRICING_MISMATCH);
            }
            return true;
        } catch (err) {
            setSaveState('failed');
            surfaceError(err);
            return false;
        }
    }, [gradedTestId]);

    const scheduleSave = useCallback(() => {
        dirtyRef.current = true;
        setSaveState('saving');
        if (timerRef.current) clearTimeout(timerRef.current);
        timerRef.current = setTimeout(() => { void flush(); }, AUTOSAVE_MS);
    }, [flush]);

    const editOverlay = useCallback((next: OverlayV6) => {
        if (approved) return;
        const previous = latestRef.current.overlay;
        generationRef.current += 1;
        const generation = generationRef.current;
        latestRef.current = { ...latestRef.current, overlay: next };
        setOverlay(next);
        const touched = touchedTerminals(previous, next, terminalOfCheck);
        if (touched.size > 0) {
            setPending((prev) => {
                const map = new Map(prev);
                touched.forEach((tid) => map.set(tid, generation));
                return map;
            });
        }
        scheduleSave();
    }, [approved, terminalOfCheck, scheduleSave]);

    const editFeedback = useCallback((target: string, text: string) => {
        if (approved) return;
        generationRef.current += 1;
        latestRef.current = {
            ...latestRef.current, feedback: { ...latestRef.current.feedback, [target]: text },
        };
        setFeedback(latestRef.current.feedback);
        setFeedbackEdited((s) => new Set(s).add(target));
        scheduleSave();
    }, [approved, scheduleSave]);

    // On unmount, FLUSH — fire-and-forget beats cancel-and-lose (the v5 rule).
    useEffect(() => () => {
        if (timerRef.current) clearTimeout(timerRef.current);
        const current = responseRef.current;
        if (!dirtyRef.current || !current) return;
        const v6 = overlayPatch(savedRef.current.overlay, latestRef.current.overlay);
        const words = feedbackPatch(savedRef.current.feedback, latestRef.current.feedback);
        if (v6 === null && Object.keys(words).length === 0) return;
        void saveGradedTestV6Draft(gradedTestId, {
            ...(v6 ? { v6 } : {}),
            feedback: words,
            client_total: priceV6(viewOf(current.content),
                pricingOverlayOf(latestRef.current.overlay)).total_score,
        }).catch(() => undefined);
    }, [gradedTestId]);

    useEffect(() => {
        const onBeforeUnload = (event: BeforeUnloadEvent) => {
            if (dirtyRef.current) { event.preventDefault(); event.returnValue = ''; }
        };
        window.addEventListener('beforeunload', onBeforeUnload);
        return () => window.removeEventListener('beforeunload', onBeforeUnload);
    }, []);

    // ── navigation and revisions: a failed save blocks every exit ─────────
    const leaveTo = useCallback(async (targetId: string | null) => {
        if (!targetId) return;
        if (!(await flush())) return;
        onNavigate(targetId);
    }, [flush, onNavigate]);

    const guardedRevision = useMemo<RevisionProps | undefined>(() => (revision ? {
        ...revision,
        onRegrade: () => { void flush().then((ok) => { if (ok) revision.onRegrade(); }); },
        onManualEdit: () => { void flush().then((ok) => { if (ok) revision.onManualEdit(); }); },
        onRetry: () => { void flush().then((ok) => { if (ok) revision.onRetry(); }); },
    } : undefined), [revision, flush]);

    // ── the model ─────────────────────────────────────────────────────────
    const policy: NumericPolicy | null = response
        ? { precision: response.content.precision, rounding_mode: 'half_up' } : null;
    const model = useMemo(() => (response ? buildV6ReviewModel({
        review: response,
        draft,
        overlay,
        questions,
        pendingLines: new Set(pending.keys()),
        saving: saveState !== 'saved',
        feedbackOverrides: feedback,
        feedbackEdited,
    }) : null), [response, draft, overlay, questions, pending, saveState, feedback, feedbackEdited]);

    // ── approve ───────────────────────────────────────────────────────────
    const onApprove = useCallback(async () => {
        if (!model || approving || approved) return;
        // Every decision she made must be on the server before it is signed: a
        // save may land while she is still typing, so flush until clean.
        for (let i = 0; i < 3 && dirtyRef.current; i += 1) {
            if (!(await flush())) return;
        }
        const latest = responseRef.current;
        if (!latest || dirtyRef.current) return;
        setApproving(true);
        try {
            // The number she approves is the pricer's, over EXACTLY the overlay
            // being frozen — the parity check, not a suggestion.
            const total = priceV6(viewOf(latest.content),
                pricingOverlayOf(overlayFromWire(latest.overlay))).total_score;
            await approveGradeReview(
                gradedTestId, latest.overrides, total);
            await onApproved(formatPoints(total));
        } catch (err) {
            surfaceError(err);
        } finally {
            setApproving(false);
        }
    }, [model, approving, approved, flush, gradedTestId, onApproved]);

    if (loadError) return <p className="py-10 text-grade-red">{loadError}</p>;
    if (!model || !policy) return <p className="py-10 text-grade-pencil">{RV_LOADING}</p>;

    return (
        <GradeReviewSurfaceV6
            model={model}
            policy={policy}
            subject={subject}
            studentName={studentName}
            identityMeta={identityMeta}
            approved={approved}
            readOnly={approved}
            stampPressed={stampPressed}
            revision={guardedRevision}
            thumbUrl={thumbUrl}
            versionBanner={versionBanner}
            queue={queue}
            eta={eta}
            batchHref={batchHref}
            canPrev={Boolean(prevId)}
            canNext={Boolean(nextId)}
            onPrev={() => { void leaveTo(prevId); }}
            onNext={() => { void leaveTo(nextId); }}
            onOpenPreview={onOpenPreview}
            onShowScan={onShowScan}
            saveState={saveState}
            approving={approving}
            onApprove={() => { void onApprove(); }}
            onSaveNow={() => { void flush(); }}
            onNotice={(message) => toast(message)}
            modalOpen={modalOpen}
            onChoose={(checkId, optionId) => {
                const vivi = viviResolved.get(checkId);
                if (vivi) editOverlay(chooseOption(latestRef.current.overlay, checkId, optionId, vivi));
            }}
            onWithdraw={(checkId) => editOverlay(withdrawOption(latestRef.current.overlay, checkId))}
            onComment={(checkId, text) => editOverlay(setComment(latestRef.current.overlay, checkId, text))}
            onPin={(terminalId, amount) => editOverlay(setPin(latestRef.current.overlay, terminalId, amount))}
            onClearPin={(terminalId) => editOverlay(clearPin(latestRef.current.overlay, terminalId))}
            onFeedbackChange={editFeedback}
        />
    );
}
