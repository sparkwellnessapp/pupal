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
    V6_ADD_ANSWER, V6_CORRECTED_CHIP, V6_EDIT_TRANSCRIPTION, V6_FB_BLANK, V6_FB_FAILED,
    V6_FB_MISSING, V6_FB_NOT_WRITTEN, V6_FB_SUMMARY_BLANK, V6_FB_SUMMARY_FAILED,
    V6_FB_SUMMARY_NOT_WRITTEN, V6_HIDE_ORIGINAL, V6_ORIGINAL_EMPTY, V6_ORIGINAL_LABEL,
    V6_REGRADE_RETRY, V6_REGRADING, V6_SHOW_ORIGINAL,
} from '@/copy/grade-review-v6';
import { revealScrollTop } from '@/utils/grade-review-highlight-machine';
import { REVIEW_LAYOUT_STACKED } from '@/lib/flags';
import { hasMathNotation } from '@/lib/subjects';
import { MathInline, MathNotationContext } from '@/components/math/MathNotationContext';
import { RubricText } from '@/components/document/RubricFigure';
import { AnswerBlock } from './AnswerBlock';
import { AnswerEditor } from './AnswerEditor';
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
 * CORRECTING THE TRANSCRIPTION (SRG, owner rulings 2026-11-01): «עריכת התמלול» opens
 * the answer's raw text in place (`AnswerEditor`); «שמירה ובדיקה מחדש» hands it to the
 * route, which regrades exactly what it changed and moves to the new version. While
 * that runs the surface is read-only — the decisions she makes belong to the version
 * that comes back. The affordance exists only when the route passes `onRegradeAnswer`.
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

    /** [SRG] The row being reviewed — what the answer editor reads its source from. */
    gradedTestId?: string;
    /** [SRG] Save a corrected answer (or, `null`, retry a failed question as it stands)
     * and regrade. Absent ⇒ no correction affordance at all. */
    onRegradeAnswer?: (scope: V6Scope, answerText: string | null) => void;
    /** [SRG] The question being regraded right now; the surface is read-only meanwhile. */
    regradingScopeId?: string | null;
}

function AnswerPane({
    scope, highlight, subject, onShowScan, editAction = null, editor = null,
}: {
    scope: V6Scope;
    highlight: Highlight;
    subject: string | null;
    onShowScan: (scopeId: string, title: string) => void;
    /** [SRG] «עריכת התמלול» / «+ הוספת תשובה», when she may correct it. */
    editAction?: React.ReactNode;
    /** [SRG] the open editor, shown in place of the answer. */
    editor?: React.ReactNode;
}) {
    const [showOriginal, setShowOriginal] = useState(false);
    const original = scope.answer.kind === 'own' || scope.answer.kind === 'inherited'
        ? scope.answer.original : undefined;
    return (
        <div className="gr-card__pane" data-answer-pane={scope.scopeId}>
            <div className="mb-1 flex flex-none items-center justify-between gap-3 text-gr-label
                text-grade-pencil">
                <span>{RV_ANSWER_LABEL}</span>
                <span className="flex-1" />
                {editor ? null : editAction}
                <button
                    type="button"
                    onClick={() => onShowScan(scope.scopeId, scope.title)}
                    className="text-primary-700 underline underline-offset-link"
                >
                    {RV_SHOW_SCAN}
                </button>
            </div>
            {/* [EVD-1] the answer the grader consumed, as the server resolved it. */}
            {editor ? editor : scope.answer.kind === 'own' || scope.answer.kind === 'inherited' ? (
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
                    {/* [SRG] she corrected this answer: say so, and keep the transcription's
                        own text one click away (FC — a correction is never silent). */}
                    {original !== undefined ? (
                        <p data-answer-corrected className="mb-1.5 flex flex-none items-center gap-2
                            text-gr-meta text-primary-700">
                            <span className="rounded-grade-sm border border-primary-200 px-1.5">
                                {V6_CORRECTED_CHIP}
                            </span>
                            <button type="button" onClick={() => setShowOriginal((v) => !v)}
                                className="underline underline-offset-link">
                                {showOriginal ? V6_HIDE_ORIGINAL : V6_SHOW_ORIGINAL}
                            </button>
                        </p>
                    ) : null}
                    {original !== undefined && showOriginal ? (
                        <div data-answer-original className="mb-2 flex-none rounded-grade-sm bg-grade-bar
                            px-3 py-2 text-gr-meta text-grade-ink-2">
                            <p className="mb-1 text-grade-pencil">{V6_ORIGINAL_LABEL}</p>
                            {original === '' ? V6_ORIGINAL_EMPTY : (
                                <AnswerBlock scopeId={`${scope.scopeId}·original`} answer={original}
                                    highlight={NO_HIGHLIGHT} subject={subject} />
                            )}
                        </div>
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
        gradedTestId, onRegradeAnswer, regradingScopeId = null,
    } = props;
    /** [SRG] a regrade is running: every write goes inert until the new version lands. */
    const locked = readOnly || regradingScopeId !== null;
    const canCorrect = Boolean(onRegradeAnswer && gradedTestId) && !readOnly && !approved;
    const [editingScope, setEditingScope] = useState<string | null>(null);
    const titleOf = useCallback((sid: string) =>
        model.scopes.find((s) => s.scopeId === sid)?.title ?? sid, [model.scopes]);
    const decidedIn = useCallback((ids: readonly string[]) => model.scopes
        .filter((s) => ids.includes(s.scopeId))
        .reduce((n, s) => n + s.criteria.filter((c) => c.decided).length, 0), [model.scopes]);

    /** The box she just opened with «כתבי משוב» — it takes the caret, once. */
    const [writing, setWriting] = useState<string | null>(null);
    const feedbackCard = (target: string, title: string, fb: V6Feedback, summary = false) => (
        <FeedbackCard
            key={target}
            title={title}
            text={fb.text}
            state={fb.state}
            teacherEdited={fb.teacherEdited}
            readOnly={locked}
            busy={fb.state === 'updating'}
            canAskVivi={fb.canWrite}
            absentLabel={summary
                ? (fb.absentReason === 'failed' ? V6_FB_SUMMARY_FAILED : V6_FB_SUMMARY_NOT_WRITTEN)
                : (fb.absentReason === 'failed' ? V6_FB_FAILED : V6_FB_NOT_WRITTEN)}
            blankLabel={summary ? V6_FB_SUMMARY_BLANK : V6_FB_BLANK}
            focusOnMount={writing === target}
            onWrite={() => { setWriting(target); onFeedbackChange(target, ''); }}
            onChange={(text) => { if (!locked) onFeedbackChange(target, text); }}
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
                    if (approved || locked) return;
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
    }, [approved, locked, blocked, showBlockers, onApprove, onSaveNow,
        canNext, canPrev, onNext, onPrev, modalOpen]);

    return (
        // Every rubric text on this surface (criteria, checks, options, the question) is drawn
        // through MathInline, which typesets `\( … \)` spans under a math subject only.
        <MathNotationContext.Provider value={hasMathNotation(subject)}>
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
                                        editAction={canCorrect && scope.answer.kind !== 'unavailable' ? (
                                            <button
                                                type="button"
                                                data-edit-transcription={scope.scopeId}
                                                disabled={regradingScopeId !== null}
                                                onClick={() => setEditingScope(scope.scopeId)}
                                                className="text-primary-700 underline underline-offset-link
                                                    disabled:opacity-50"
                                            >
                                                {scope.answer.kind === 'missing' ? V6_ADD_ANSWER : V6_EDIT_TRANSCRIPTION}
                                            </button>
                                        ) : null}
                                        editor={canCorrect && editingScope === scope.scopeId && gradedTestId ? (
                                            <AnswerEditor
                                                gradedTestId={gradedTestId}
                                                questionId={scope.questionId}
                                                subQuestionId={scope.subQuestionId}
                                                subject={subject}
                                                failed={scope.gradedBy === 'failed'}
                                                busy={regradingScopeId === scope.scopeId}
                                                titleOf={titleOf}
                                                decidedIn={decidedIn}
                                                onSubmit={(text) => onRegradeAnswer?.(scope, text)}
                                                onCancel={() => setEditingScope(null)}
                                            />
                                        ) : null}
                                    />
                                    <div className="gr-card__criteria">
                                        {regradingScopeId === scope.scopeId ? (
                                            <p data-regrading className="mb-3 text-gr-body text-primary-700">
                                                {V6_REGRADING}
                                            </p>
                                        ) : null}
                                        {scope.gradedBy === 'failed' ? (
                                            <p className="mb-3 flex items-center gap-3 text-gr-body text-grade-red">
                                                <span>{RV_SCOPE_FAILED}</span>
                                                {/* D10: the same action, with nothing to edit */}
                                                {canCorrect && editingScope !== scope.scopeId ? (
                                                    <button
                                                        type="button"
                                                        data-retry-scope={scope.scopeId}
                                                        disabled={regradingScopeId !== null}
                                                        onClick={() => onRegradeAnswer?.(scope, null)}
                                                        className="text-primary-700 underline underline-offset-link
                                                            disabled:opacity-50"
                                                    >
                                                        {regradingScopeId === scope.scopeId ? V6_REGRADING : V6_REGRADE_RETRY}
                                                    </button>
                                                ) : null}
                                            </p>
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
                                                <div className="mt-1.5 rounded-grade-sm bg-grade-bar px-3 py-2.5
                                                    leading-relaxed">
                                                    <RubricText text={scope.questionText} />
                                                </div>
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
                                                readOnly={locked}
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
                canApprove={!approved && !locked}
                blocked={blocked}
                onBlocked={showBlockers}
                onApprove={onApprove}
                onShowKeys={() => undefined}
                keyboardHints={false}
                notice={!approved && !readOnly && model.feedbackMissing > 0
                    ? V6_FB_MISSING(model.feedbackMissing) : null}
            />
        </div>
        </MathNotationContext.Provider>
    );
}
