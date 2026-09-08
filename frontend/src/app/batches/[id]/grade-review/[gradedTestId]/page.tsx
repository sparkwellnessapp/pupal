'use client';

/**
 * בדיקת ציונים — the per-test review route.
 *
 * /batches/[id]/grade-review/[gradedTestId]   (see the layout for why not /review)
 *
 * THE PAGE OWNS THE OVERLAY AND ITS AUTOSAVE. Everything that must survive a
 * prev/next lives in the layout's provider; this component remounts per test,
 * which is exactly the lifetime her working copy of ONE test should have.
 *
 * ── AUTOSAVE, AND WHY A FAILED SAVE BLOCKS NAVIGATION ────────────────────
 * Saves fire on a 1.5s idle debounce and again on every exit (prev, next,
 * approve, tab close). If a save FAILS the navigation is refused and the bar
 * turns red: the alternative is walking her to the next test while the
 * decisions she just made are still only in this tab, which is how a teacher
 * loses twenty minutes of judgement and never learns why. Blocking is the
 * honest failure — she can see it, retry it, and nothing is lost.
 *
 * ── N6 ───────────────────────────────────────────────────────────────────
 * Below `desk` the module yields to an honest interstitial. The answer, the
 * checklist and the evidence must be readable side by side; a phone cannot do
 * that, and pretending otherwise would produce approvals made half-blind.
 */

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';

import {
    approveGradeReview, fetchPageImageObjectUrl, getGradedTest, manualEditGradedTest,
    regenerateFeedback, regradeGradedTest, retryGradedTest, saveGradeReviewDraft,
    type GradeReviewOverlay,
} from '@/lib/api';
import { surfaceError } from '@/lib/errorSurface';
import { GradeReviewSurface } from '@/components/grade-review/GradeReviewSurface';
import { ScanViewer } from '@/components/grade-review/ScanViewer';
import { etaText } from '@/utils/grade-dashboard';
import { useGradeReview } from '@/components/grade-review/GradeReviewContext';
import type { SaveState } from '@/components/grade-review/ReviewChrome';
import {
    advanceAfterApprove, queueState, step, type GradeCursor,
} from '@/utils/grade-review-cursor';
import { buildReviewModel, type WireDraft } from '@/utils/grade-review-model';
import type { OverlayTerminals } from '@/utils/verdict-cycle';
import type { NumericPolicy } from '@/lib/pricing';
import {
    DASH_ETA_REMAINING, DASH_ETA_UNKNOWN,
    RV_APPROVED_TOAST, RV_FB_REGENERATED, RV_IDENTITY_META, RV_LANDED_AGO,
    RV_LOADING, RV_LOAD_ERROR, RV_MOBILE_BACK, RV_MOBILE_INTERSTITIAL,
    RV_APPROVED_READONLY, RV_GRADING_FAILED, RV_GRADING_IN_PROGRESS, RV_NOT_FOUND,
    RV_PRICING_MISMATCH, RV_REVISION_STARTED, RV_SAVE_FAILED, RV_TEST_POSITION,
} from '@/copy/grade-review';
import { relativeTimeHe } from '@/utils/batch-dashboard';

const AUTOSAVE_MS = 1500;

interface GradedTestPayload {
    id: string;
    status: string;
    student_name: string;
    draft?: WireDraft;
    numeric_policy?: NumericPolicy | null;
    total_possible?: string | null;
    rubric_contract_stale?: boolean;
    /** Non-null on a revision (manual_edit / regrade / retry successor). */
    regraded_from_id?: string | null;
    /** The scan this grade was made from — shared along the whole chain. */
    transcription_id?: string | null;
}

export default function GradeReviewPage() {
    const params = useParams<{ id: string; gradedTestId: string }>();
    const router = useRouter();
    const {
        batch, cursor, answersByTest, scanByTest, answersByTranscription, scanByTranscription,
        questions, rubricSubject, error: batchError, getCursor, markApproved,
    } = useGradeReview();

    const [payload, setPayload] = useState<GradedTestPayload | null>(null);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [overlay, setOverlay] = useState<OverlayTerminals>({});
    const [feedbackOverrides, setFeedbackOverrides] = useState<Record<string, string>>({});
    const [saveState, setSaveState] = useState<SaveState>('saved');
    const [approving, setApproving] = useState(false);
    const [feedbackBusy, setFeedbackBusy] = useState(false);
    const [stampPressed, setStampPressed] = useState(false);
    const [feedbackOffers, setFeedbackOffers] = useState<Record<string, string>>({});
    const [revisionBusy, setRevisionBusy] = useState(false);
    /** R4 — which scope's scan is open, and on which pages. */
    const [scan, setScan] = useState<{ title: string; pages: number[] } | null>(null);
    /** R1 — page 1 as an object URL for the mini thumb; revoked when it changes. */
    const [thumbUrl, setThumbUrl] = useState<string | null>(null);
    const closeScan = useCallback(() => setScan(null), []);

    /**
     * The joins prefer the TRANSCRIPTION id (which a revision successor shares
     * with its predecessor) and fall back to the graded-test id (the fixtures'
     * and the pre-revision shape). See `GradeReviewContext` for why.
     */
    const transcriptionId = payload?.transcription_id ?? null;
    const answersForTest = (transcriptionId ? answersByTranscription[transcriptionId] : undefined)
        ?? answersByTest[params.gradedTestId] ?? [];

    const feedThumbPath = (batch?.graded_tests ?? [])
        .find((t) => t.graded_test_id === params.gradedTestId)?.page1_image_url ?? null;
    // A successor is not in the feed; its scan's page 1 still is, by transcription.
    const page1Path = feedThumbPath
        ?? (transcriptionId ? `/api/v0/transcriptions/${transcriptionId}/pages/1/image` : null);
    useEffect(() => {
        if (!page1Path) { setThumbUrl(null); return; }
        let cancelled = false;
        let minted: string | null = null;
        fetchPageImageObjectUrl(page1Path)
            .then((url) => {
                if (cancelled) { URL.revokeObjectURL(url); return; }
                minted = url;
                setThumbUrl(url);
            })
            // A missing thumb is an empty paper frame, never an error (§3.5a).
            .catch(() => { if (!cancelled) setThumbUrl(null); });
        return () => {
            cancelled = true;
            if (minted) URL.revokeObjectURL(minted);
        };
    }, [page1Path]);

    const dirtyRef = useRef(false);
    /**
     * Bumped on every edit. `flush` captures it BEFORE awaiting and only clears
     * `dirty` if it has not moved — otherwise a verdict changed while a save
     * was in flight would be marked saved and never sent, with the bar
     * cheerfully reading «נשמר ✓» over work that exists only in this tab.
     */
    const editGenerationRef = useRef(0);
    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const latestRef = useRef<{ overlay: OverlayTerminals; feedback: Record<string, string> }>({
        overlay: {}, feedback: {},
    });
    latestRef.current = { overlay, feedback: feedbackOverrides };

    // ── load this test ────────────────────────────────────────────────────
    useEffect(() => {
        let alive = true;
        setPayload(null);
        setLoadError(null);
        setOverlay({});
        setFeedbackOverrides({});
        setFeedbackOffers({});
        setStampPressed(false);
        dirtyRef.current = false;
        editGenerationRef.current = 0;
        setSaveState('saved');

        /**
         * A revision (regrade / retry) lands as a PENDING row: the chain has
         * been extended and the agent has not run yet, so there is no draft.
         * Reporting «הבדיקה לא נמצאה» there would make every revision look
         * broken; poll instead, and say what is actually happening.
         *
         * Terminal states stop the poll: `draft` renders, `failed` says so.
         */
        let pollTimer: ReturnType<typeof setTimeout> | null = null;
        const load = () => getGradedTest(params.gradedTestId)
            .then((data) => {
                if (!alive) return;
                const status = (data as { status?: string }).status;
                if (status === 'pending' || status === 'grading') {
                    setPayload(data as unknown as GradedTestPayload);
                    pollTimer = setTimeout(load, 4000);
                    return;
                }
                const typed = data as unknown as GradedTestPayload & {
                    draft?: { teacher_overrides?: GradeReviewOverlay };
                };
                setPayload(typed);
                // Her previous working copy rides INSIDE the draft; hydrating it
                // is not dirt — only a keystroke is (the Δ14 rule, inherited).
                const stored = typed.draft?.teacher_overrides;
                if (stored?.terminals) setOverlay(stored.terminals as OverlayTerminals);
                if (stored?.feedback) setFeedbackOverrides(stored.feedback);
            })
            .catch(() => { if (alive) setLoadError(RV_LOAD_ERROR); });

        void load();
        return () => {
            alive = false;
            if (pollTimer) clearTimeout(pollTimer);
        };
    }, [params.gradedTestId]);

    const buildOverlayPayload = useCallback((): GradeReviewOverlay => ({
        terminals: latestRef.current.overlay as GradeReviewOverlay['terminals'],
        feedback: latestRef.current.feedback,
    }), []);

    /**
     * What the CLIENT priced, per terminal — the parity signal.
     *
     * The server compares these against its own and answers `pricing_mismatch`.
     * Not sending them makes that flag permanently false, so a client/server
     * pricing drift stays invisible until `/approve` refuses outright — which
     * is the worst moment to discover it, after she has reviewed the whole
     * test. Keyed by TERMINAL id, matching `effective_totals` server-side.
     */
    const clientTotalsRef = useRef<Record<string, string>>({});

    /** Returns false when the save failed — every caller treats that as a stop. */
    const flush = useCallback(async (): Promise<boolean> => {
        if (timerRef.current) { clearTimeout(timerRef.current); timerRef.current = null; }
        if (!dirtyRef.current) return true;
        setSaveState('saving');
        const generation = editGenerationRef.current;
        try {
            const saved = await saveGradeReviewDraft(
                params.gradedTestId, buildOverlayPayload(), clientTotalsRef.current);
            if (editGenerationRef.current !== generation) {
                // She kept working while this was in flight. The save that just
                // landed is already stale, so the dirty flag STAYS and the
                // debounce will send the newer state.
                return true;
            }
            dirtyRef.current = false;
            setSaveState('saved');
            // The server prices the same overlay and says whether it agrees.
            // Surfacing it here is the whole point of sending client_totals —
            // otherwise drift is only discovered when /approve refuses, after
            // she has reviewed the entire test.
            if ((saved as { pricing_mismatch?: boolean }).pricing_mismatch) {
                toast.error(RV_PRICING_MISMATCH);
            }
            return true;
        } catch (err) {
            setSaveState('failed');
            // The bar already says «השמירה נכשלה — נסי שוב» in place; the toast
            // carries the transport reason, per the error-surface convention.
            surfaceError(err);
            return false;
        }
    }, [params.gradedTestId, buildOverlayPayload]);

    const markDirty = useCallback(() => {
        dirtyRef.current = true;
        editGenerationRef.current += 1;
        setSaveState('saving');
        if (timerRef.current) clearTimeout(timerRef.current);
        timerRef.current = setTimeout(() => { void flush(); }, AUTOSAVE_MS);
    }, [flush]);

    /**
     * On unmount, FLUSH — do not merely cancel the timer.
     *
     * The prev/next path awaits `flush()` before navigating, but any other exit
     * (the WaitCard's link back to the dashboard, the mobile interstitial's
     * link, a sidebar click) unmounts this component directly. Cancelling the
     * pending timer there discards every verdict she made in the last 1.5
     * seconds, silently. The save cannot be awaited during teardown, so this is
     * fire-and-forget — but fire-and-forget beats cancel-and-lose, and
     * `beforeunload` still covers a real tab close.
     */
    useEffect(() => () => {
        if (timerRef.current) clearTimeout(timerRef.current);
        if (dirtyRef.current) {
            void saveGradeReviewDraft(
                params.gradedTestId, buildOverlayPayload(), clientTotalsRef.current,
            ).catch(() => undefined);
        }
    }, [params.gradedTestId, buildOverlayPayload]);

    // The last line of defence. Nothing can be awaited here, so this only warns
    // — the real guarantee is the flush on every in-app exit.
    useEffect(() => {
        const onBeforeUnload = (event: BeforeUnloadEvent) => {
            if (dirtyRef.current) { event.preventDefault(); event.returnValue = ''; }
        };
        window.addEventListener('beforeunload', onBeforeUnload);
        return () => window.removeEventListener('beforeunload', onBeforeUnload);
    }, []);

    // ── navigation ────────────────────────────────────────────────────────
    const goTo = useCallback(async (targetId: string | null) => {
        if (!targetId) return;
        if (!(await flush())) return;      // a failed save blocks navigation
        router.push(`/batches/${params.id}/grade-review/${targetId}`);
    }, [flush, router, params.id]);

    const liveCursor: GradeCursor | null = getCursor() ?? cursor;
    const queue = useMemo(
        () => (liveCursor
            ? queueState(liveCursor, params.gradedTestId)
            : { nextLanded: null, grading: [], skipped: 0, exhausted: false }),
        [liveCursor, params.gradedTestId],
    );
    const prevId = liveCursor ? step(liveCursor, params.gradedTestId, 'prev') : null;
    const nextId = liveCursor ? step(liveCursor, params.gradedTestId, 'next') : null;

    const policy = payload?.numeric_policy ?? null;

    const model = useMemo(() => (payload?.draft && policy
        ? buildReviewModel({
            draft: payload.draft,
            overlay,
            policy,
            answers: answersForTest,
            questions,
            feedbackOverrides,
            // The contract's achievable total, never a client re-sum (§5).
            totalPossible: payload.total_possible ?? null,
        })
        : null), [payload, policy, overlay, answersForTest, questions, feedbackOverrides]);

    // Kept in a ref so the unmount flush — which cannot read state — still
    // sends the parity numbers.
    clientTotalsRef.current = model
        ? Object.fromEntries(model.scopes.flatMap(
            (scope) => scope.criteria.map((c) => [c.terminalId, c.awarded])))
        : {};

    const onApprove = useCallback(async () => {
        if (!model || approving) return;
        if (!(await flush())) return;
        setApproving(true);
        try {
            await approveGradeReview(
                params.gradedTestId, buildOverlayPayload(), model.total);
            setPayload((p) => (p ? { ...p, status: 'approved' } : p));
            // The cursor must learn this BEFORE the advance decision, or the
            // walk can hand her back the test she just signed.
            markApproved(params.gradedTestId);
            const fresh = getCursor() ?? liveCursor;
            const target = fresh ? advanceAfterApprove(fresh, params.gradedTestId) : null;
            const nextName = target && fresh
                ? fresh.byId[target]?.student_name ?? null : null;
            // R12's order is the whole point: the stamp presses on the mini
            // thumb, and only then does she move on. Advancing first would
            // leave the signature happening on a screen she has already left,
            // which is the one moment in the flow worth showing her.
            setStampPressed(true);
            toast.success(RV_APPROVED_TOAST(model.total, nextName));
            await new Promise((resolve) => { setTimeout(resolve, 420); });
            // OD-F4: auto-advance. Nothing landed left → the dashboard, which is
            // where the batch's own state lives.
            router.push(target
                ? `/batches/${params.id}/grade-review/${target}`
                : `/batches/${params.id}`);
        } catch (err) {
            surfaceError(err);
        } finally {
            setApproving(false);
        }
    }, [model, approving, flush, params.gradedTestId, params.id,
        buildOverlayPayload, liveCursor, getCursor, markApproved, router]);

    const onFeedbackRegenerate = useCallback(async (target: string) => {
        setFeedbackBusy(true);
        try {
            const result = await regenerateFeedback(params.gradedTestId, target);
            // `offered_only` means she has edited this text and the server did
            // NOT overwrite it. Vivi proposes; the teacher decides — so a
            // regeneration that would clobber her words is OFFERED beside them,
            // as something she can read and choose. It was briefly a toast,
            // which asked her to decide from memory against text that had
            // already disappeared.
            if (result.offered_only) {
                setFeedbackOffers((o) => ({ ...o, [target]: result.text }));
            } else {
                setFeedbackOverrides((f) => ({ ...f, [target]: result.text }));
                markDirty();
                toast.success(RV_FB_REGENERATED);
            }
        } catch (err) {
            surfaceError(err);
        } finally {
            setFeedbackBusy(false);
        }
    }, [params.gradedTestId, markDirty]);

    /**
     * regrade / manual_edit / retry — each EXTENDS the chain and returns a NEW
     * graded-test id, so the only correct thing to do afterwards is navigate to
     * it. Staying put would leave her editing a row that is now read-only
     * (LCY-2: approved and failed rows are immutable except `regraded_to_id`).
     */
    const runRevision = useCallback(async (
        kind: 'regrade' | 'manual_edit' | 'retry',
    ) => {
        if (revisionBusy) return;
        if (!(await flush())) return;
        setRevisionBusy(true);
        try {
            const call = kind === 'regrade' ? regradeGradedTest
                : kind === 'manual_edit' ? manualEditGradedTest : retryGradedTest;
            const revision = await call(params.gradedTestId);
            toast.success(RV_REVISION_STARTED);
            router.push(
                `/batches/${params.id}/grade-review/${revision.graded_test_id}`);
        } catch (err) {
            surfaceError(err);
        } finally {
            setRevisionBusy(false);
        }
    }, [revisionBusy, flush, params.gradedTestId, params.id, router]);

    // ── shells ────────────────────────────────────────────────────────────
    const batchHref = `/batches/${params.id}`;

    if (loadError || batchError) {
        return <Shell><p className="text-grade-red">{loadError ?? batchError}</p></Shell>;
    }
    if (!payload) return <Shell><p className="text-grade-pencil">{RV_LOADING}</p></Shell>;
    if (payload.status === 'pending' || payload.status === 'grading') {
        return (
            <Shell>
                <p data-grading className="text-grade-ink-2">{RV_GRADING_IN_PROGRESS}</p>
                <Link
                    href={batchHref}
                    className="mt-3 inline-block text-primary-700 underline underline-offset-link"
                >
                    {RV_MOBILE_BACK}
                </Link>
            </Shell>
        );
    }
    if (payload.status === 'failed') {
        return (
            <Shell>
                <p data-grading-failed className="text-grade-red">{RV_GRADING_FAILED}</p>
                <Link
                    href={batchHref}
                    className="mt-3 inline-block text-primary-700 underline underline-offset-link"
                >
                    {RV_MOBILE_BACK}
                </Link>
            </Shell>
        );
    }
    if (!payload.draft || !policy) {
        return <Shell><p className="text-grade-pencil">{RV_NOT_FOUND}</p></Shell>;
    }

    /**
     * An approved test is READ-ONLY (LCY-2: approved rows are immutable except
     * `regraded_to_id`). Leaving the verdict buttons live meant one keystroke
     * queued an autosave the server 409s — and since a failed save blocks
     * navigation, that single keystroke stranded her on the test with no way
     * forward. `עריכה מחדש` in the overflow is the way back in.
     */
    const readOnly = payload.status === 'approved';

    /**
     * R13. The banner says «את עורכת בדיקה שכבר אושרה», so it must be true: a
     * draft with a `regraded_from_id` whose PREDECESSOR is approved (manual_edit
     * / regrade). A retry successor also carries `regraded_from_id`, but its
     * predecessor FAILED — nothing was ever signed, and the sentence would lie.
     * The predecessor is looked up in the feed; if it is not there, the banner
     * is omitted rather than guessed. The chain position comes from the feed's
     * `version` when > 1 (the feed sends 1 for every row today — reported), so
     * the number is omitted rather than showing «גרסה 1» on a second version.
     */
    const feedItem = (batch?.graded_tests ?? [])
        .find((t) => t.graded_test_id === params.gradedTestId);
    const predecessor = payload.regraded_from_id
        ? (batch?.graded_tests ?? []).find((t) => t.graded_test_id === payload.regraded_from_id)
        : undefined;
    const versionBanner = payload.regraded_from_id && !readOnly
        && predecessor?.status === 'approved'
        ? { version: (feedItem?.version ?? 1) > 1 ? (feedItem?.version as number) : null }
        : null;

    /** R2 — «(מנוקד עכשיו, עוד כ-2 דקות)»: the batch's own ETA, minutes-granular. */
    const queueEta = etaText(batch?.eta ?? null, {
        firstLanding: DASH_ETA_REMAINING,
        remaining: DASH_ETA_REMAINING,
        unknown: DASH_ETA_UNKNOWN,
    });

    /**
     * R4 — «הצגת הסריקה». The scope id is the join key (`q1.א` → question 1,
     * sub «א»): exact answer first, then the parent question's pages (the
     * transcription segments to depth 1, the same fallback the grader used),
     * else nothing — and the viewer says so instead of guessing a page.
     */
    const scanSource = (transcriptionId ? scanByTranscription[transcriptionId] : undefined)
        ?? scanByTest[params.gradedTestId] ?? null;
    const openScan = (scopeId: string) => {
        const scope = model?.scopes.find((s) => s.scopeId === scopeId);
        const [q, sub] = scopeId.split('.');
        const number = Number(q.replace(/^q/i, ''));
        const answers = scanSource?.answers ?? [];
        const exact = answers.find((a) => a.question_number === number
            && (a.sub_question_id ?? null) === (sub ?? null));
        const parent = answers.find((a) => a.question_number === number
            && (a.sub_question_id ?? null) === null);
        const pages = (exact?.page_numbers?.length ? exact : parent)?.page_numbers ?? [];
        setScan({ title: scope?.title ?? scopeId, pages: [...new Set(pages)].sort((a, b) => a - b) });
    };

    /**
     * R1's identity line: «כיתה · מבחן 3 מתוך 30 · נחת לפני 6 דקות».
     *
     * Each part is omitted when its datum is absent rather than rendered as a
     * dash — a line of placeholders reads as broken, and every one of these is
     * context she can do without. (`מס׳` — the student's class number — has no
     * field on any wire shape today; it is left out rather than faked.)
     */
    const cursorItem = liveCursor?.byId[params.gradedTestId];
    // A revision successor is not in the entry-frozen cursor, and an unguarded
    // indexOf renders «מבחן 0 מתוך 5». Omit the position rather than lie about it.
    const cursorIndex = liveCursor?.order.indexOf(params.gradedTestId) ?? -1;
    const position = liveCursor && cursorIndex >= 0
        ? RV_TEST_POSITION(cursorIndex + 1, liveCursor.order.length)
        : null;
    const className = (batch as { class_name?: string | null } | null)?.class_name ?? null;
    const landedAgo = cursorItem?.landed_at
        ? RV_LANDED_AGO(relativeTimeHe(cursorItem.landed_at, new Date()))
        : null;

    return (
        <>
            {/* N6 — below `desk` the module yields rather than pretending. */}
            <div className="px-6 py-10 text-center desk:hidden">
                <p className="mx-auto max-w-md text-gr-body text-grade-ink-2">
                    {RV_MOBILE_INTERSTITIAL}
                </p>
                <Link
                    href={batchHref}
                    className="mt-4 inline-block text-primary-700 underline underline-offset-[3px]"
                >
                    {RV_MOBILE_BACK}
                </Link>
            </div>

            <main className="mx-auto hidden max-w-[1180px] px-6 pb-24 pt-6 desk:block">
                <GradeReviewSurface
                    draft={payload.draft}
                    answers={answersForTest}
                    questions={questions}
                    subject={rubricSubject}
                    policy={policy}
                    overlay={overlay}
                    onOverlayChange={(next) => { setOverlay(next); markDirty(); }}
                    feedbackOverrides={feedbackOverrides}
                    onFeedbackChange={(target, text) => {
                        setFeedbackOverrides((f) => ({ ...f, [target]: text }));
                        markDirty();
                    }}
                    onFeedbackRegenerate={onFeedbackRegenerate}
                    feedbackBusy={feedbackBusy}
                    feedbackOffers={feedbackOffers}
                    onAcceptFeedbackOffer={(target) => {
                        const text = feedbackOffers[target];
                        if (text === undefined) return;
                        setFeedbackOverrides((f) => ({ ...f, [target]: text }));
                        setFeedbackOffers(({ [target]: _drop, ...rest }) => rest);
                        markDirty();
                    }}
                    onDismissFeedbackOffer={(target) =>
                        setFeedbackOffers(({ [target]: _drop, ...rest }) => rest)}
                    studentName={payload.student_name}
                    identityMeta={RV_IDENTITY_META([className, position, landedAgo])}
                    approved={payload.status === 'approved'}
                    readOnly={readOnly}
                    stampPressed={stampPressed}
                    thumbUrl={thumbUrl}
                    versionBanner={versionBanner}
                    revision={{
                        status: payload.status,
                        contractStale: Boolean(payload.rubric_contract_stale),
                        busy: revisionBusy,
                        onRegrade: () => { void runRevision('regrade'); },
                        onManualEdit: () => { void runRevision('manual_edit'); },
                        onRetry: () => { void runRevision('retry'); },
                    }}
                    queue={queue}
                    eta={queueEta}
                    batchHref={batchHref}
                    canPrev={Boolean(prevId)}
                    canNext={Boolean(nextId)}
                    onPrev={() => { void goTo(prevId); }}
                    onNext={() => { void goTo(nextId); }}
                    // The batch rides along so the preview keeps its two
                    // batch-wide controls (see that route's doc).
                    onOpenPreview={() => router.push(
                        `/graded-tests/${params.gradedTestId}/returned?batch=${params.id}`)}
                    onShowScan={openScan}
                    saveState={saveState}
                    approving={approving}
                    onApprove={() => { void onApprove(); }}
                    onSaveNow={() => { void flush(); }}
                    onNotice={(message) => toast(message)}
                    modalOpen={scan !== null}
                />
                {scan ? (
                    <ScanViewer
                        scopeTitle={scan.title}
                        transcriptionId={scanSource?.transcriptionId ?? null}
                        pageNumbers={scan.pages}
                        onClose={closeScan}
                    />
                ) : null}
            </main>
        </>
    );
}

function Shell({ children }: { children: React.ReactNode }) {
    return <main className="mx-auto max-w-[1180px] px-6 py-10">{children}</main>;
}
