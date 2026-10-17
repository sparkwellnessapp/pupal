'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import type { NumericPolicy } from '@/lib/pricing';
import { NO_HIGHLIGHT, type Highlight } from '@/utils/evidence-highlight';
import { resolveKeyAction } from '@/utils/grade-review-keymap';
import type { QueueState } from '@/utils/grade-review-cursor';
import type { V6ReviewModel, V6Scope } from '@/utils/grade-review-v6-model';
import { REVIEW_LAYOUT_STACKED } from '@/lib/flags';
import { AnswerBlock } from './AnswerBlock';
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
    onComment: (checkId: string, text: string | null) => void;
    onPin: (terminalId: string, amount: string) => void;
    onClearPin: (terminalId: string) => void;
    onFeedbackChange: (target: string, text: string) => void;
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
        onChoose, onWithdraw, onComment, onPin, onClearPin, onFeedbackChange,
    } = props;

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
                            spans: litHere.checks.flatMap((c) => (c.quote && c.quoteKind
                                ? [{ quote: c.quote, kind: c.quoteKind }] : [])),
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
                                                onComment={onComment}
                                                lit={lit === criterion.terminalId}
                                                onToggleLit={() => setLit((current) =>
                                                    (current === criterion.terminalId ? null : criterion.terminalId))}
                                            />
                                        ))}

                                        {scope.feedback ? (
                                            <FeedbackCard
                                                title={RV_FB_TITLE(scope.title)}
                                                text={scope.feedback.text}
                                                // v6 feedback carries no verdict basis, so it is never
                                                // "stale" here — and it is never rewritten from this
                                                // screen (see GradeReviewV6): no regeneration offer.
                                                state="fresh"
                                                teacherEdited={scope.feedback.teacherEdited}
                                                onChange={(text) => {
                                                    if (!readOnly) onFeedbackChange(scope.scopeId, text);
                                                }}
                                                onRegenerate={() => undefined}
                                            />
                                        ) : null}
                                    </div>
                                </div>
                            </section>
                        );
                    })}

                    {model.summary ? (
                        <div className="rounded-grade border border-grade-line bg-grade-card px-6 py-4">
                            <FeedbackCard
                                title={RV_FB_SUMMARY_TITLE}
                                text={model.summary.text}
                                state="fresh"
                                teacherEdited={model.summary.teacherEdited}
                                onChange={(text) => { if (!readOnly) onFeedbackChange('summary', text); }}
                                onRegenerate={() => undefined}
                            />
                        </div>
                    ) : null}

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
            />
        </div>
    );
}
