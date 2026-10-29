'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import type { NumericPolicy } from '@/lib/pricing';
import { NO_HIGHLIGHT, type Highlight } from '@/utils/evidence-highlight';
import { resolveKeyAction } from '@/utils/grade-review-keymap';
import type { QueueState } from '@/utils/grade-review-cursor';
import {
    criterionQuoteSpans, type V6Feedback, type V6ReviewModel, type V6Scope,
} from '@/utils/grade-review-v6-model';
import {
    V6_FB_BLANK, V6_FB_FAILED, V6_FB_MISSING, V6_FB_NOT_WRITTEN, V6_FB_SUMMARY_BLANK,
    V6_FB_SUMMARY_FAILED, V6_FB_SUMMARY_NOT_WRITTEN,
} from '@/copy/grade-review-v6';
import { revealScrollTop } from '@/utils/grade-review-highlight-machine';
import { REVIEW_LAYOUT_STACKED } from '@/lib/flags';
import { AnswerBlock } from './AnswerBlock';
import { FIG_DEDUCTION_HINT } from '@/copy/math';
import { FIGURE_LINE } from '@/utils/figure-lines';
import { CriterionRowV6 } from './CriterionRowV6';
import { FeedbackCard } from './FeedbackCard';
import {
    QueueLine, ReviewBottomBar, ReviewTopBar, ScopeNav, VersionBanner, WaitCard,
    type SaveState,
} from './ReviewChrome';
import {
    RV_ANSWER_INHERITED, RV_ANSWER_INHERITED_ANON, RV_ANSWER_LABEL, RV_ANSWER_NONE,
    RV_ANSWER_UNAVAILABLE, RV_APPROVE_BLOCKED, RV_FB_SUMMARY_TITLE, RV_FB_TITLE,
    RV_QUESTION_TOGGLE, RV_SCOPE_EXCLUDED, RV_SCOPE_FAILED, RV_SHOW_SCAN,
} from '@/copy/grade-review';
import { formatPoints } from '@/utils/points-display';

/**
 * בדיקת ציונים for a grader-v6 grade (owner rulings 2026-10-17 §7, the MVC).
 *
 * The frame is v5's — the same top bar, queue line, question rail, answer pane
 * pinned beside its criteria, and bottom bar — so the two surfaces read as one
 * product. What changes is the unit she judges: a v6 grade is priced from the
 * CHOICES made on each check (what the answer shows, from a short list), so the
 * checklist is a list of criterion rows (`CriterionRowV6`) rather than v5's
 * ✓/½/✗ verdict rows.
 *
 * The surface owns EPHEMERAL state only — which criteria are open, which grade
 * field is open, which criterion's quotations are lit. Her decisions, the save
 * and the approval live in the route (`GradeReviewV6`), so this renders the
 * same from a fixture in a test and from the route in production.
 *
 * KEYBOARD: Ctrl/⌘+↵ approves (or names the blockers), Ctrl/⌘+S saves now,
 * ←/→ move between tests, Esc releases a lit quotation — the v5 keymap's
 * resolver, acting only on the keys this surface has. The bottom bar's hints
 * for v5's checklist keys are turned off rather than left lying.
 */

export interface GradeReviewSurfaceV6Props {
    model: V6ReviewModel;
    policy: NumericPolicy;
    subject?: string | null;
    studentName: string;
    identityMeta: string;
    approved?: boolean;
    readOnly?: boolean;
    stampPressed?: boolean;
    revision?: React.ComponentProps<typeof ReviewTopBar>['revision'];
    thumbUrl?: string | null;
    versionBanner?: { version: number | null } | null;

    queue: QueueState;
    eta: string | null;
    batchHref: string;
    canPrev: boolean;
    canNext: boolean;
    onPrev: () => void;
    onNext: () => void;
    onOpenPreview: () => void;
    onShowScan: (scopeId: string, title: string) => void;

    saveState: SaveState;
    approving?: boolean;
    onApprove: () => void;
    onSaveNow: () => void;
    onNotice: (message: string) => void;
    modalOpen?: boolean;

    onChoose: (checkId: string, optionId: string) => void;
    onWithdraw: (checkId: string) => void;
    onNote: (terminalId: string, text: string | null) => void;
    onPin: (terminalId: string, amount: string) => void;
    onClearPin: (terminalId: string) => void;
    onFeedbackChange: (target: string, text: string) => void;
    /** Ask Vivi to (re)write one feedback target — a scope id or «summary». */
    onRewriteFeedback: (target: string) => void;
    onAcceptFeedbackOffer: (target: string) => void;
    onDismissFeedbackOffer: (target: string) => void;
}

function AnswerPane({
    scope, highlight, subject, onShowScan,
}: {
    scope: V6Scope;
    highlight: Highlight;
    subject: string | null;
    onShowScan: (scopeId: string, title: string) => void;
}) {
    return (
        <div className="gr-card__pane" data-answer-pane={scope.scopeId}>
            <div className="mb-1 flex flex-none items-center justify-between text-gr-label
                text-grade-pencil">
                <span>{RV_ANSWER_LABEL}</span>
                <button
                    type="button"
                    onClick={() => onShowScan(scope.scopeId, scope.title)}
                    className="text-primary-700 underline underline-offset-link"
                >
                    {RV_SHOW_SCAN}
                </button>
            </div>
            {/* [EVD-1] the answer the grader consumed, as the server resolved it. */}
            {scope.answer.kind === 'own' || scope.answer.kind === 'inherited' ? (
                <>
                    {scope.answer.kind === 'inherited' ? (
                        <p data-answer-inherited className="mb-1.5 flex-none text-gr-meta text-grade-ink-2">
                            {scope.answer.from
                                ? RV_ANSWER_INHERITED(scope.answer.from)
                                : RV_ANSWER_INHERITED_ANON}
                        </p>
                    ) : null}
                    {/* §5 (OD-M5): a drawing's reading can miss what is drawn while calling
                        itself complete, so a point taken here is checked against the ink. */}
                    {FIGURE_LINE.test(scope.answer.text) && Number(scope.awarded) < Number(scope.possible) ? (
                        <p data-figure-deduction className="mb-1.5 flex-none rounded-grade-ctl border
                            border-grade-amber-200 bg-grade-amber-50 px-3 py-1.5 text-gr-meta text-grade-amber-ink">
                            {FIG_DEDUCTION_HINT}{' '}
                            <button type="button" onClick={() => onShowScan(scope.scopeId, scope.title)}
                                className="underline underline-offset-link">{RV_SHOW_SCAN}</button>
                        </p>
                    ) : null}
                    <AnswerBlock
                        scopeId={scope.scopeId}
                        answer={scope.answer.text}
                        highlight={highlight}
                        subject={subject}
                    />
                </>
            ) : (
                <p
                    data-answer-missing
                    data-answer-state={scope.answer.kind}
                    className="flex-none rounded-grade-ctl border border-grade-amber-200
                        bg-grade-amber-50 px-4 py-3 text-gr-body text-grade-amber-ink"
                >
                    {/* «missing» accuses; «unavailable» admits. Never swap them. */}
                    {scope.answer.kind === 'missing' ? RV_ANSWER_NONE : RV_ANSWER_UNAVAILABLE}
                </p>
            )}
        </div>
    );
}

export function GradeReviewSurfaceV6(props: GradeReviewSurfaceV6Props) {
    const {
        model, policy, subject = null, studentName, identityMeta, approved = false,
        readOnly = false, stampPressed = false, revision, thumbUrl = null, versionBanner = null,
        queue, eta, batchHref, canPrev, canNext, onPrev, onNext, onOpenPreview, onShowScan,
        saveState, approving = false, onApprove, onSaveNow, onNotice, modalOpen = false,
        onChoose, onWithdraw, onNote, onPin, onClearPin, onFeedbackChange,
        onRewriteFeedback, onAcceptFeedbackOffer, onDismissFeedbackOffer,
    } = props;

    /** The box she just opened with «כתבי משוב» — it takes the caret, once. */
    const [writing, setWriting] = useState<string | null>(null);
    const feedbackCard = (target: string, title: string, fb: V6Feedback, summary = false) => (
        <FeedbackCard
            key={target}
            title={title}
            text={fb.text}
            state={fb.state}
            teacherEdited={fb.teacherEdited}
            readOnly={readOnly}
            busy={fb.state === 'updating'}
            canAskVivi={fb.canWrite}
            absentLabel={summary
                ? (fb.absentReason === 'failed' ? V6_FB_SUMMARY_FAILED : V6_FB_SUMMARY_NOT_WRITTEN)
                : (fb.absentReason === 'failed' ? V6_FB_FAILED : V6_FB_NOT_WRITTEN)}
            blankLabel={summary ? V6_FB_SUMMARY_BLANK : V6_FB_BLANK}
            focusOnMount={writing === target}
            onWrite={() => { setWriting(target); onFeedbackChange(target, ''); }}
            onChange={(text) => { if (!readOnly) onFeedbackChange(target, text); }}
            onRegenerate={() => onRewriteFeedback(target)}
            offered={fb.offered}
            onAcceptOffer={() => onAcceptFeedbackOffer(target)}
            onDismissOffer={() => onDismissFeedbackOffer(target)}
        />
    );

    /**
     * Which criteria are open: once per test, the ones that need her (a check
     * waiting for her choice) or carry her earlier work; after that, hers.
     * Kept in a ref for the same reason v5 keeps its opening state in one — a
     * criterion she just closed must not spring open because she decided
     * something inside it.
     */
    const openingRef = useRef<ReadonlySet<string> | null>(null);
    if (openingRef.current === null) {
        openingRef.current = new Set(model.scopes.flatMap((s) => s.criteria
            .filter((c) => c.undecidedCount > 0 || c.decided)
            .map((c) => c.terminalId)));
    }
    const [toggled, setToggled] = useState<ReadonlyMap<string, boolean>>(() => new Map());
    const isOpen = useCallback((tid: string) =>
        toggled.get(tid) ?? (openingRef.current?.has(tid) ?? false), [toggled]);
    const toggle = useCallback((tid: string) => {
        setToggled((prev) => new Map(prev).set(tid, !(prev.get(tid)
            ?? (openingRef.current?.has(tid) ?? false))));
    }, []);
    const [editingPoints, setEditingPoints] = useState<string | null>(null);
    const [lit, setLit] = useState<string | null>(null);

    // [owner 2026-10-21] After «ציטוט מהתשובה» lights a criterion's quotes, scroll THAT
    // scope's answer body to the first mark. One element's scrollTop, never
    // `scrollIntoView` (it would move the page too — HL-3). Post-commit, because the
    // marks exist only once the lit state has painted. Nothing to reveal → nothing moves.
    useEffect(() => {
        if (!lit || typeof document === 'undefined') return;
        const scopeId = model.scopes.find((s) =>
            s.criteria.some((c) => c.terminalId === lit))?.scopeId;
        if (!scopeId) return;
        const body = document.querySelector<HTMLElement>(
            `[data-answer-for="${CSS.escape(scopeId)}"]`);
        const first = body?.querySelector<HTMLElement>('mark');
        if (!body || !first) return;
        const bodyTop = body.getBoundingClientRect().top + body.clientTop;
        const box = first.getBoundingClientRect();
        const top = revealScrollTop({
            spanTop: box.top - bodyTop + body.scrollTop,
            spanBottom: box.bottom - bodyTop + body.scrollTop,
            scrollTop: body.scrollTop,
            clientHeight: body.clientHeight,
            scrollHeight: body.scrollHeight,
        });
        if (top === null) return;                      // already in view
        const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
        body.scrollTo({ top, behavior: reduce ? 'auto' : 'smooth' });
        // eslint-disable-next-line react-hooks/exhaustive-deps -- reveal on the CLICK only
    }, [lit]);

    const markersByScope = useMemo(() => Object.fromEntries(
        model.scopes.map((s) => [s.scopeId, s.undecidedCount])), [model.scopes]);

    const showBlockers = useCallback(() => {
        if (model.blockers.length === 0) return;
        onNotice(RV_APPROVE_BLOCKED(model.blockers.map((b) => b.message)));
        const anchor = model.blockers.find((b) => b.scopeId)?.scopeId;
        if (anchor && typeof document !== 'undefined') {
            document.getElementById(`scope-${anchor}`)
                ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }, [model.blockers, onNotice]);

    const blocked = model.blockers.length > 0;

    useEffect(() => {
        if (typeof window === 'undefined') return undefined;
        const onKeyDown = (event: KeyboardEvent) => {
            const target = event.target as HTMLElement | null;
            const inEditable = Boolean(target && (target.tagName === 'INPUT'
                || target.tagName === 'TEXTAREA' || target.isContentEditable));
            const resolution = resolveKeyAction({
                key: event.key, code: event.code, ctrlOrMeta: event.ctrlKey || event.metaKey,
                isComposing: event.isComposing, repeat: event.repeat, inEditable, modalOpen,
            });
            if (!resolution) return;
            switch (resolution.action) {
                case 'approve':
                    event.preventDefault();
                    if (approved || readOnly) return;
                    if (blocked) showBlockers(); else onApprove();
                    break;
                case 'save':
                    event.preventDefault();
                    onSaveNow();
                    break;
                case 'nextTest': if (canNext) onNext(); break;
                case 'prevTest': if (canPrev) onPrev(); break;
                case 'release': setLit(null); break;
                default: break;            // v5's checklist keys have no meaning here
            }
        };
        window.addEventListener('keydown', onKeyDown);
        return () => window.removeEventListener('keydown', onKeyDown);
    }, [approved, readOnly, blocked, showBlockers, onApprove, onSaveNow,
        canNext, canPrev, onNext, onPrev, modalOpen]);

    return (
        <div
            className="gr-review pb-24"
            data-review-surface="v6"
            data-review-layout={REVIEW_LAYOUT_STACKED ? 'stacked' : undefined}
        >
            <ReviewTopBar
                studentName={studentName}
                meta={identityMeta}
                total={model.total}
                possible={model.possible}
                anyOverride={model.anyOverride}
                approved={approved}
                canPrev={canPrev}
                canNext={canNext}
                onPrev={onPrev}
                onNext={onNext}
                onOpenPreview={onOpenPreview}
                batchHref={batchHref}
                stampPressed={stampPressed}
                revision={revision}
                thumbUrl={thumbUrl}
            />
            <QueueLine queue={queue} eta={eta} />
            {versionBanner ? <VersionBanner version={versionBanner.version} /> : null}

            <div className="mt-4 grid items-start gap-6 rail:grid-cols-[190px_1fr]">
                <ScopeNav
                    scopes={model.scopes}
                    markersByScope={markersByScope}
                    activeScopeId={null}
                    onJump={(scopeId) => {
                        document.getElementById(`scope-${scopeId}`)
                            ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }}
                />

                <div>
                    {model.scopes.map((scope) => {
                        const litHere = scope.criteria.find((c) => c.terminalId === lit);
                        const highlight: Highlight = litHere ? {
                            pinned: true,
                            spans: criterionQuoteSpans(litHere),
                        } : NO_HIGHLIGHT;
                        return (
                            <section
                                key={scope.scopeId}
                                id={`scope-${scope.scopeId}`}
                                data-scope-id={scope.scopeId}
                                data-graded-by={scope.gradedBy}
                                className={[
                                    'mb-4 scroll-mt-scope rounded-grade border bg-grade-card px-6 pb-5 pt-5',
                                    scope.gradedBy === 'failed' ? 'border-grade-red' : 'border-grade-line',
                                ].join(' ')}
                            >
                                <header className="gr-card__strip flex items-center justify-between gap-3
                                    bg-grade-card">
                                    <h2 className="min-w-0 truncate text-gr-h2">{scope.title}</h2>
                                    <div
                                        dir="ltr"
                                        data-scope-points
                                        className={[
                                            'text-gr-pts [font-variant-numeric:tabular-nums] [unicode-bidi:isolate]',
                                            scope.overridden ? 'font-normal text-primary-700' : 'text-grade-pencil',
                                        ].join(' ')}
                                    >
                                        {formatPoints(scope.awarded)} / {formatPoints(scope.possible)}
                                    </div>
                                </header>

                                <div className="gr-card__cols">
                                    <AnswerPane
                                        scope={scope}
                                        highlight={highlight}
                                        subject={subject}
                                        onShowScan={onShowScan}
                                    />
                                    <div className="gr-card__criteria">
                                        {scope.gradedBy === 'failed' ? (
                                            <p className="mb-3 text-gr-body text-grade-red">{RV_SCOPE_FAILED}</p>
                                        ) : null}
                                        {!scope.counted || scope.gradedBy === 'excluded_by_selection' ? (
                                            <p className="mb-3 text-gr-body text-grade-pencil">{RV_SCOPE_EXCLUDED}</p>
                                        ) : null}
                                        {scope.questionText ? (
                                            <details className="mb-2.5 mt-1 text-gr-meta text-grade-ink-2">
                                                <summary className="inline-flex cursor-pointer list-none items-center
                                                    gap-1.5 text-grade-pencil marker:content-['']">
                                                    <span aria-hidden="true">▸</span>
                                                    {RV_QUESTION_TOGGLE}
                                                </summary>
                                                <p className="mt-1.5 rounded-grade-sm bg-grade-bar px-3 py-2.5
                                                    leading-relaxed">
                                                    {scope.questionText}
                                                </p>
                                            </details>
                                        ) : null}

                                        {scope.criteria.map((criterion) => (
                                            <CriterionRowV6
                                                key={criterion.terminalId}
                                                criterion={criterion}
                                                policy={policy}
                                                subject={subject}
                                                open={isOpen(criterion.terminalId)}
                                                onToggle={() => toggle(criterion.terminalId)}
                                                readOnly={readOnly}
                                                editingPoints={editingPoints === criterion.terminalId}
                                                onEditingPoints={(editing) =>
                                                    setEditingPoints(editing ? criterion.terminalId : null)}
                                                onPin={(amount) => onPin(criterion.terminalId, amount)}
                                                onClearPin={() => onClearPin(criterion.terminalId)}
                                                onChoose={onChoose}
                                                onWithdraw={onWithdraw}
                                                onNote={(text) => onNote(criterion.terminalId, text)}
                                                lit={lit === criterion.terminalId}
                                                onToggleLit={() => setLit((current) =>
                                                    (current === criterion.terminalId ? null : criterion.terminalId))}
                                            />
                                        ))}

                                        {/* Every question the student gets has a feedback box,
                                            whatever its text — so a failed write still leaves
                                            her somewhere to write. */}
                                        {scope.feedback
                                            ? feedbackCard(scope.scopeId, RV_FB_TITLE(scope.title), scope.feedback)
                                            : null}
                                    </div>
                                </div>
                            </section>
                        );
                    })}

                    <div className="rounded-grade border border-grade-line bg-grade-card px-6 py-4">
                        {feedbackCard('summary', RV_FB_SUMMARY_TITLE, model.summary, true)}
                    </div>

                    {queue.exhausted ? (
                        <div className="mt-4">
                            <WaitCard gradingCount={queue.grading.length} eta={eta} batchHref={batchHref} />
                        </div>
                    ) : null}
                </div>
            </div>

            <ReviewBottomBar
                saveState={saveState}
                approving={approving}
                canApprove={!approved && !readOnly}
                blocked={blocked}
                onBlocked={showBlockers}
                onApprove={onApprove}
                onShowKeys={() => undefined}
                keyboardHints={false}
                notice={!approved && !readOnly && model.feedbackMissing > 0
                    ? V6_FB_MISSING(model.feedbackMissing) : null}
            />
        </div>
    );
}
