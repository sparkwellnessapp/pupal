'use client';

import {
    createContext, useContext, useCallback, useEffect, useMemo, useRef, useState, Fragment,
    type RefObject,
} from 'react';
import type { RubricQuestion, RubricSubQuestion, RubricCriterion, RubricSubCriterion } from '@/types/rubric';
import type { Annotation, SelectionGroup } from '@/lib/api';
import { recalculateParentsFromCriteria } from '@/utils/rubric-transform';
import {
    updateCriterionAtPath, addCriterionAtPath, removeCriterionAtPath,
    changeQuestionPoints as changeQuestionPointsOp,
} from '@/utils/rubric-editor-ops';
import { computeAchievablePoints } from '@/utils/rubric-achievable';
import { scopeLabel, questionLabel, subQuestionLabel } from '@/utils/scope-label';
import { splitRoutingPrefix } from '@/utils/routing-prefix';
import { selectionSummaryLine, findingSectionsByQuestion } from '@/utils/session-spine';
import { isOpenFinding } from '@/utils/finding-severity';
import { changedPointNodeIds } from '@/utils/points-cascade';
import { AnnotationBanner } from '@/components/AnnotationBanner';
import { EditableText } from '@/components/document/EditableText';
import { EditablePoints } from '@/components/document/EditablePoints';
import { DisclosureRow } from '@/components/document/DisclosureRow';
import { CodeBlock } from '@/components/document/CodeBlock';
import { RichBody, TraceTablesDisplay, ContextTablesDisplay } from '@/components/document/DataTables';

/**
 * RubricDocument (PR-5 Sprint 2) — THE MIRROR. A sibling view to RubricEditor that
 * reads as her DOCX annotated by Vivi (Dream Law 4), not as form furniture.
 *
 * Prop seam = RubricEditor's PLUS `selectionGroups` (needed for §5). It consumes
 * questions + annotations + errorBannerRef and emits through onQuestionsChange /
 * onTotalPointsChange / onMetadataChange — it NEVER touches rubric-transform's
 * golden suite. Every edit routes through the pure `*AtPath` ops (imported, never
 * forked); this is a CORRECTNESS INVARIANT, not a style choice — the page-level
 * undo stack pushes snapshots by reference and relies on structural sharing, so an
 * in-place mutation would retroactively corrupt earlier snapshots.
 *
 * Editability this sprint (the "living sums" model, E-3): the teacher edits LEAVES
 * — criterion points/descriptions, sub-criteria — and watches parents cascade.
 * Sub-question points and direct-criteria question totals are READ-ONLY cascaded
 * sums. A parent question's declared total (with sub-questions) stays editable
 * (INV-R1 surfaces any mismatch). Question/sub-question PROSE and solutions are
 * read-only display this sprint (deferred, like D-2) — the Dream DoD is
 * criteria-points-centric.
 */

// ─────────────────────────────────────────────────────────────────────────────
// Context — the edit ops + read data, so the recursive tree stays prop-light.
// ─────────────────────────────────────────────────────────────────────────────

interface DocOps {
    updateCriterion(qIndex: number, sqPath: number[], cIndex: number, updates: Partial<RubricCriterion>): void;
    addCriterion(qIndex: number, sqPath: number[]): void;
    removeCriterion(qIndex: number, sqPath: number[], cIndex: number, label: string): void;
    setSubCriteria(qIndex: number, sqPath: number[], cIndex: number, subs: RubricSubCriterion[] | null): void;
    changeQuestionPoints(qIndex: number, n: number): void;
}

interface DocContextValue extends DocOps {
    questions: RubricQuestion[];
    annotations: Annotation[];
    changedIds: Set<string>;
    scrollToScope(targetId: string | null): void;
}

const DocContext = createContext<DocContextValue | null>(null);
function useDoc(): DocContextValue {
    const ctx = useContext(DocContext);
    if (!ctx) throw new Error('RubricDocument subcomponents must render inside <RubricDocument>');
    return ctx;
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

/** Annotations anchored to any of the given ids (bare id or full dotted path). */
function annotationsFor(annotations: Annotation[], ...ids: (string | undefined)[]): Annotation[] {
    const set = new Set(ids.filter((x): x is string => !!x));
    return annotations.filter((a) => a.target_id !== null && set.has(a.target_id));
}

/** D-4: mute a leading routing prefix that just repeats the scope heading. Render-
 *  only; the underlying state stays verbatim. */
function mutedPrefixRenderer(headingLabel: string) {
    return (value: string) => {
        const { prefix, rest } = splitRoutingPrefix(value, headingLabel);
        return prefix ? <><span className="text-surface-400">{prefix}</span>{rest}</> : value;
    };
}

function InlineAnnotations({ annotations }: { annotations: Annotation[] }) {
    if (annotations.length === 0) return null;
    return (
        <div className="space-y-1.5 my-2">
            {annotations.map((a) => <AnnotationBanner key={a.id} annotation={a} />)}
        </div>
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// CriteriaTable — the centerpiece (§3). Real <table>; description wraps, never
// h-scrolls; points via EditablePoints (the one cascade site); breakdown rows.
// ─────────────────────────────────────────────────────────────────────────────

function SubCriteriaRows({
    qIndex, sqPath, cIndex, criterion,
}: { qIndex: number; sqPath: number[]; cIndex: number; criterion: RubricCriterion }) {
    const { setSubCriteria, changedIds } = useDoc();
    const subs = criterion.sub_criteria ?? [];

    const editSub = (scIndex: number, updates: Partial<RubricSubCriterion>) => {
        const next = subs.map((sc, i) => (i === scIndex ? { ...sc, ...updates } : sc));
        setSubCriteria(qIndex, sqPath, cIndex, next);
    };

    return (
        <>
            {subs.map((sc, scIndex) => (
                <tr key={sc.sub_criterion_id} data-scope-id={sc.sub_criterion_id} className="scroll-mt-20 bg-surface-50/40">
                    <td className="py-1.5 pr-8 pl-3 text-surface-600 text-[13px]">
                        <span className="text-surface-300 ml-1">↳</span>
                        <EditableText
                            value={sc.description}
                            onCommit={(description) => editSub(scIndex, { description })}
                            ariaLabel={`תיאור תת-קריטריון ${scIndex + 1} — לחצי לעריכה`}
                            dir="rtl"
                        />
                    </td>
                    <td className="py-1.5 px-2 text-center align-top">
                        <EditablePoints
                            value={sc.points}
                            onCommit={(points) => editSub(scIndex, { points })}
                            ariaLabel={`ניקוד תת-קריטריון ${scIndex + 1} — לחצי לעריכה`}
                            changed={changedIds.has(sc.sub_criterion_id)}
                        />
                    </td>
                    <td aria-hidden />
                </tr>
            ))}
        </>
    );
}

function CriteriaTable({
    qIndex, sqPath, criteria, scopeHeading,
}: { qIndex: number; sqPath: number[]; criteria: RubricCriterion[]; scopeHeading: string }) {
    const { updateCriterion, addCriterion, removeCriterion, annotations, changedIds } = useDoc();
    const tableRef = useRef<HTMLTableElement>(null);
    const muteView = mutedPrefixRenderer(scopeHeading); // D-4

    // E-5: Enter in a points cell advances to the next row's points.
    const focusNextPoints = useCallback((cIndex: number) => {
        const cells = tableRef.current?.querySelectorAll<HTMLElement>('[data-points-cell]');
        const next = cells?.[cIndex + 1];
        (next?.querySelector('button, input') as HTMLElement | undefined)?.focus();
    }, []);

    if (criteria.length === 0) return null;

    return (
        <table ref={tableRef} className="w-full border-collapse my-2 text-sm" dir="rtl">
            <thead>
                <tr className="text-surface-400 text-xs">
                    <th className="text-right font-normal pb-1 pr-3">קריטריון</th>
                    <th className="text-center font-normal pb-1 px-2 w-16">נק'</th>
                    <th className="w-8" aria-hidden />
                </tr>
            </thead>
            <tbody>
                {criteria.map((c, cIndex) => {
                    const anns = annotationsFor(annotations, c.criterion_id);
                    const hasSubs = (c.sub_criteria?.length ?? 0) > 0;
                    return (
                        <Fragment key={c.criterion_id}>
                            <tr data-scope-id={c.criterion_id} className="scroll-mt-20 border-t border-surface-100 align-top group">
                                <td className="py-2 pr-3">
                                    {hasSubs ? (
                                        <DisclosureRow
                                            label={<EditableText value={c.description} onCommit={(description) => updateCriterion(qIndex, sqPath, cIndex, { description })} ariaLabel={`תיאור קריטריון ${cIndex + 1} — לחצי לעריכה`} dir="rtl" renderDisplay={muteView} />}
                                            toggleLabel={`פירוט קריטריון ${cIndex + 1}`}
                                        >
                                            <table className="w-full border-collapse"><tbody>
                                                <SubCriteriaRows qIndex={qIndex} sqPath={sqPath} cIndex={cIndex} criterion={c} />
                                            </tbody></table>
                                        </DisclosureRow>
                                    ) : (
                                        <EditableText value={c.description} onCommit={(description) => updateCriterion(qIndex, sqPath, cIndex, { description })} ariaLabel={`תיאור קריטריון ${cIndex + 1} — לחצי לעריכה`} dir="rtl" renderDisplay={muteView} />
                                    )}
                                </td>
                                <td className="py-2 px-2 text-center" data-points-cell>
                                    <EditablePoints
                                        value={c.points}
                                        onCommit={(points) => updateCriterion(qIndex, sqPath, cIndex, { points })}
                                        onEnterCommit={() => focusNextPoints(cIndex)}
                                        ariaLabel={`ניקוד קריטריון ${cIndex + 1} — לחצי לעריכה`}
                                        changed={changedIds.has(c.criterion_id)}
                                    />
                                </td>
                                <td className="py-2 w-8 text-center">
                                    <button
                                        type="button"
                                        onClick={() => removeCriterion(qIndex, sqPath, cIndex, `קריטריון ${cIndex + 1}`)}
                                        aria-label={`מחקי קריטריון ${cIndex + 1}`}
                                        className="opacity-0 group-hover:opacity-100 focus:opacity-100 text-surface-300 hover:text-red-500 transition-opacity text-lg leading-none"
                                    >×</button>
                                </td>
                            </tr>
                            {anns.length > 0 && (
                                <tr><td colSpan={3} className="pb-2"><InlineAnnotations annotations={anns} /></td></tr>
                            )}
                        </Fragment>
                    );
                })}
                <tr>
                    <td colSpan={3} className="pt-1">
                        <button
                            type="button"
                            onClick={() => addCriterion(qIndex, sqPath)}
                            className="text-sm text-surface-400 hover:text-primary-600 transition-colors"
                        >+ הוסיפי קריטריון</button>
                    </td>
                </tr>
            </tbody>
        </table>
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// SolutionBlock — read-only disclosure (D-2).
// ─────────────────────────────────────────────────────────────────────────────

function SolutionBlock({ solution }: { solution?: string | null }) {
    if (!solution || !solution.trim()) return null;
    return (
        <DisclosureRow label="פתרון לדוגמה" toggleLabel="פתרון לדוגמה" className="my-2">
            <CodeBlock code={solution} />
        </DisclosureRow>
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// SectionHeading + PointsChip
// ─────────────────────────────────────────────────────────────────────────────

function PointsChip({ value, ariaLabel, editable, onCommit, changed }: {
    value: number; ariaLabel: string; editable: boolean; onCommit?: (n: number) => void; changed?: boolean;
}) {
    return (
        <span className="text-sm text-surface-500 tabular-nums">
            <EditablePoints value={value} onCommit={onCommit ?? (() => {})} ariaLabel={ariaLabel} readOnly={!editable} changed={changed} />
            <span className="mr-0.5">נק'</span>
        </span>
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// SubQuestionSection — recursive (§2). Leaf → CriteriaTable; parent → children.
// ─────────────────────────────────────────────────────────────────────────────

function SubQuestionSection({
    qIndex, sq, sqPath, idPath, depth,
}: { qIndex: number; sq: RubricSubQuestion; sqPath: number[]; idPath: string; depth: number }) {
    const { annotations, changedIds } = useDoc();
    const heading = sq.title?.trim() || subQuestionLabel(sq, sqPath[sqPath.length - 1], depth);
    const hasChildren = (sq.sub_questions?.length ?? 0) > 0;
    const anns = annotationsFor(annotations, idPath, sq.sub_question_id);

    return (
        <section data-scope-id={idPath} className="scroll-mt-20 mr-3 border-r border-surface-100 pr-3 mt-3">
            <div className="flex items-baseline justify-between gap-3">
                <h4 className="font-medium text-surface-700">{heading}</h4>
                {/* Sub-question points are a cascaded sum — read-only (E-3 living sums). */}
                <PointsChip value={sq.points} ariaLabel={`ניקוד ${heading}`} editable={false} changed={changedIds.has(sq.sub_question_id)} />
            </div>

            {sq.text?.trim() ? <RichBody text={sq.text} dir="rtl" className="mt-1 text-[15px]" /> : null}
            <TraceTablesDisplay tables={sq.trace_tables} />
            <InlineAnnotations annotations={anns} />

            {hasChildren
                ? <div className="space-y-1">{sq.sub_questions!.map((child, i) => (
                    <SubQuestionSection key={child.sub_question_id} qIndex={qIndex} sq={child} sqPath={[...sqPath, i]} idPath={`${idPath}.${child.sub_question_id}`} depth={depth + 1} />
                ))}</div>
                : <CriteriaTable qIndex={qIndex} sqPath={sqPath} criteria={sq.criteria} scopeHeading={heading} />}

            <SolutionBlock solution={sq.example_solution} />
        </section>
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// QuestionSection
// ─────────────────────────────────────────────────────────────────────────────

function QuestionSection({
    q, qIndex, isSelectionMember,
}: { q: RubricQuestion; qIndex: number; isSelectionMember: boolean }) {
    const { annotations, changedIds, changeQuestionPoints } = useDoc();
    const heading = questionLabel(q, qIndex);
    const hasSubs = q.sub_questions.length > 0;
    const anns = annotationsFor(annotations, q.question_id);

    return (
        <section
            data-scope-id={q.question_id}
            className="scroll-mt-20 pt-5 first:pt-0 doc-enter-section"
            style={{ animationDelay: `${Math.min(qIndex, 8) * 40}ms` }}
        >
            <div className="flex items-baseline justify-between gap-3 border-b border-surface-100 pb-1.5">
                <h3 className="text-lg font-semibold text-surface-900 flex items-center gap-2">
                    {heading}
                    {isSelectionMember && <span className="text-xs font-normal text-primary-600 bg-primary-50 rounded-full px-2 py-0.5">שאלת בחירה</span>}
                </h3>
                {/* A parent question's total is teacher-authoritative (INV-R1). A direct-
                    criteria question's total is a cascaded sum → read-only. */}
                <PointsChip
                    value={q.total_points}
                    ariaLabel={`ניקוד ${heading}${hasSubs ? ' — לחצי לעריכה' : ''}`}
                    editable={hasSubs}
                    onCommit={(n) => changeQuestionPoints(qIndex, n)}
                    changed={changedIds.has(q.question_id)}
                />
            </div>

            {q.question_text?.trim() ? <RichBody text={q.question_text} dir="rtl" className="mt-2" /> : null}
            {q.code_blocks?.map((code, i) => <CodeBlock key={i} code={code} />)}
            <ContextTablesDisplay tables={q.context_tables} />
            <TraceTablesDisplay tables={q.trace_tables} />
            <InlineAnnotations annotations={anns} />

            {hasSubs
                ? q.sub_questions.map((sq, i) => (
                    <SubQuestionSection key={sq.sub_question_id} qIndex={qIndex} sq={sq} sqPath={[i]} idPath={`${q.question_id}.${sq.sub_question_id}`} depth={1} />
                ))
                : <CriteriaTable qIndex={qIndex} sqPath={[]} criteria={q.criteria} scopeHeading={heading} />}

            <SolutionBlock solution={q.example_solution} />
        </section>
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// DocumentHeader (§5) + OutlineRail (E-2)
// ─────────────────────────────────────────────────────────────────────────────

function DocumentHeader({
    name, achievable, declared, onNameCommit, onDeclaredCommit, selectionLine, openFindingCount, canUndo, onUndo,
}: {
    name: string; achievable: number; declared: number | undefined;
    onNameCommit: (v: string) => void; onDeclaredCommit: (n: number) => void;
    selectionLine: string | null; openFindingCount: number; canUndo: boolean; onUndo?: () => void;
}) {
    return (
        <header className="mb-4 doc-enter-header">
            <div className="flex items-start justify-between gap-4">
                <h1 className="text-2xl font-bold text-surface-900">
                    <EditableText value={name} onCommit={onNameCommit} ariaLabel="שם המחוון — לחצי לעריכה" dir="rtl" placeholder="שם המחוון" />
                </h1>
                <div className="flex items-center gap-3 flex-shrink-0">
                    {canUndo && (
                        <button type="button" onClick={onUndo} className="text-sm text-surface-500 hover:text-surface-800 transition-colors">ביטול</button>
                    )}
                    <div className="text-left">
                        <div data-testid="rubric-achievable-total" className="text-2xl font-bold text-surface-900 tabular-nums">{achievable}<span className="text-sm font-normal text-surface-500 mr-1">נק'</span></div>
                        <div className="text-xs text-surface-400 flex items-center gap-1 justify-end">
                            <span>מוצהר</span>
                            <EditablePoints value={declared ?? achievable} onCommit={onDeclaredCommit} ariaLabel="ניקוד מוצהר — לחצי לעריכה" />
                        </div>
                    </div>
                </div>
            </div>
            {selectionLine && <p className="text-sm text-surface-600 mt-1">{selectionLine}</p>}
            {openFindingCount === 0 && (
                <p className="text-sm text-emerald-700 mt-1">ויוי לא מצאה אי-התאמות במחוון ✓</p>
            )}
        </header>
    );
}

function OutlineRail({
    questions, activeId, findingSections, onJump, railStyle,
}: {
    questions: RubricQuestion[]; activeId: string | null; findingSections: Set<string>;
    onJump: (id: string) => void; railStyle: { left: number; width: number } | null;
}) {
    // position: FIXED, not sticky — SidebarLayout's `overflow-hidden` ancestor breaks
    // sticky (verified in headless Chromium: the rail scrolls away). The spacer in the
    // flex row reserves this gutter; we pin the rail over it (left/width measured).
    return (
        <nav
            aria-label="מפת המחוון"
            style={railStyle ? { position: 'fixed', top: 80, left: railStyle.left, width: railStyle.width } : undefined}
            className={`hidden min-[1100px]:block w-44 text-sm max-h-[calc(100vh-100px)] overflow-y-auto ${railStyle ? '' : 'sticky top-20 self-start flex-shrink-0'}`}
        >
            <ul className="space-y-1 border-r border-surface-100 pr-3">
                {questions.map((q, i) => {
                    const active = q.question_id === activeId;
                    return (
                        <li key={q.question_id}>
                            <button
                                type="button"
                                onClick={() => onJump(q.question_id)}
                                className={`flex items-center gap-1.5 w-full text-right transition-colors ${active ? 'text-primary-700 font-medium' : 'text-surface-500 hover:text-surface-800'}`}
                            >
                                {findingSections.has(q.question_id) && <span className="w-1.5 h-1.5 rounded-full bg-amber-400 flex-shrink-0" aria-label="ממצא פתוח" />}
                                <span className="truncate">{questionLabel(q, i)}</span>
                            </button>
                        </li>
                    );
                })}
            </ul>
        </nav>
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// RubricDocument — root
// ─────────────────────────────────────────────────────────────────────────────

interface RubricDocumentProps {
    questions: RubricQuestion[];
    onQuestionsChange: (questions: RubricQuestion[]) => void;
    annotations?: Annotation[];
    errorBannerRef?: RefObject<HTMLDivElement>;
    rubricName?: string;
    rubricTotalPoints?: number;
    onTotalPointsChange?: (newTotal: number) => void;
    onMetadataChange?: (patch: { rubric_name?: string; subject?: string; programming_language?: string }) => void;
    selectionGroups?: SelectionGroup[];
    /** E-1 (page-level undo) — the mirror renders «ביטול» and installs Ctrl+Z. */
    canUndo?: boolean;
    onUndo?: () => void;
}

export function RubricDocument({
    questions,
    onQuestionsChange,
    annotations = [],
    errorBannerRef,
    rubricName = '',
    rubricTotalPoints,
    onTotalPointsChange,
    onMetadataChange,
    selectionGroups = [],
    canUndo = false,
    onUndo,
}: RubricDocumentProps) {
    // E-3: which point chips just moved (glow). Diff against the previous questions.
    const prevRef = useRef<RubricQuestion[]>(questions);
    const [changedIds, setChangedIds] = useState<Set<string>>(() => new Set());
    useEffect(() => {
        const changed = changedPointNodeIds(prevRef.current, questions);
        prevRef.current = questions;
        if (changed.size === 0) return;
        setChangedIds(changed);
        const t = setTimeout(() => setChangedIds(new Set()), 650);
        return () => clearTimeout(t);
    }, [questions]);

    const scrollToScope = useCallback((targetId: string | null) => {
        if (!targetId) return;
        document.querySelector(`[data-scope-id="${targetId}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, []);

    // ── Edit ops — ALL through the pure *AtPath ops (correctness invariant). ──
    const ops: DocOps = useMemo(() => ({
        updateCriterion: (qIndex, sqPath, cIndex, updates) => {
            const next = updateCriterionAtPath(questions, qIndex, sqPath, cIndex, updates);
            // Recalc ONLY on a points change (the one cascade site). A description
            // edit must not silently move any sum.
            onQuestionsChange('points' in updates ? recalculateParentsFromCriteria(next) : next);
        },
        addCriterion: (qIndex, sqPath) => onQuestionsChange(addCriterionAtPath(questions, qIndex, sqPath)),
        removeCriterion: (qIndex, sqPath, cIndex, label) => {
            onQuestionsChange(removeCriterionAtPath(questions, qIndex, sqPath, cIndex));
            if (typeof window !== 'undefined') {
                // D-3: delete is undo-over-confirm — execute now, offer reversal. The
                // page listens and shows a 6s toast whose «ביטול» pops the undo stack
                // (which already holds the pre-delete snapshot from onQuestionsChange).
                window.dispatchEvent(new CustomEvent('vivi:undo-toast', { detail: { message: `${label} נמחק` } }));
            }
        },
        setSubCriteria: (qIndex, sqPath, cIndex, subs) =>
            onQuestionsChange(updateCriterionAtPath(questions, qIndex, sqPath, cIndex, { sub_criteria: subs })),
        changeQuestionPoints: (qIndex, n) => onQuestionsChange(changeQuestionPointsOp(questions, qIndex, n)),
    }), [questions, onQuestionsChange]);

    const ctx: DocContextValue = useMemo(() => ({
        ...ops, questions, annotations, changedIds, scrollToScope,
    }), [ops, questions, annotations, changedIds, scrollToScope]);

    // ── Derived ──
    const achievable = useMemo(() => computeAchievablePoints(questions, selectionGroups), [questions, selectionGroups]);
    const selectionLine = useMemo(() => selectionSummaryLine(selectionGroups, questions.length), [selectionGroups, questions.length]);
    const findingSections = useMemo(() => findingSectionsByQuestion(annotations, questions), [annotations, questions]);
    const selectionMemberIds = useMemo(() => {
        const s = new Set<string>();
        selectionGroups.forEach((g) => g.of_question_ids.forEach((id) => s.add(id)));
        return s;
    }, [selectionGroups]);
    const errorAnnotations = useMemo(() => annotations.filter((a) => a.severity === 'error'), [annotations]);
    const globalAnnotations = useMemo(() => annotations.filter((a) => a.target_id === null || a.target_id === 'rubric'), [annotations]);
    const openFindingCount = useMemo(() => annotations.filter(isOpenFinding).length, [annotations]);

    // ── E-2 rail active-tracking (window scroller; offset the 64px sticky header) ──
    const [activeId, setActiveId] = useState<string | null>(null);
    const rootRef = useRef<HTMLDivElement>(null);

    // ── E-2 rail positioning: FIXED (sticky is broken by the overflow-hidden
    // ancestor — verified). Measure the in-flow spacer's gutter and pin the rail
    // over it; a ResizeObserver on the root catches window resize AND the sidebar
    // collapse (which changes layout without a window resize event). ──
    const railSpacerRef = useRef<HTMLDivElement>(null);
    const [railBox, setRailBox] = useState<{ left: number; width: number } | null>(null);
    useEffect(() => {
        const measure = () => {
            const el = railSpacerRef.current;
            if (!el) return;
            const r = el.getBoundingClientRect();
            setRailBox(r.width > 0 ? { left: r.left, width: r.width } : null); // width 0 ⇒ collapsed (<1100px)
        };
        measure();
        const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(measure) : null;
        if (ro && rootRef.current) ro.observe(rootRef.current);
        window.addEventListener('resize', measure);
        return () => { ro?.disconnect(); window.removeEventListener('resize', measure); };
    }, []);
    useEffect(() => {
        const sections = rootRef.current?.querySelectorAll<HTMLElement>('section[data-scope-id]');
        if (!sections || sections.length === 0) return;
        const topLevel = Array.from(sections).filter((el) => questions.some((q) => q.question_id === el.getAttribute('data-scope-id')));
        const io = new IntersectionObserver(
            (entries) => {
                const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
                if (visible[0]) setActiveId(visible[0].target.getAttribute('data-scope-id'));
            },
            // REQUIRED (S2): top offset ~= sticky app header, else tracking runs a
            // section ahead and rail-clicks land under the header.
            { rootMargin: '-80px 0px -70% 0px', threshold: 0 },
        );
        topLevel.forEach((el) => io.observe(el));
        return () => io.disconnect();
    }, [questions]);

    // ── E-1 Ctrl+Z (undo owned by the page; the mirror is the review surface) ──
    useEffect(() => {
        if (!onUndo) return;
        const onKey = (e: KeyboardEvent) => {
            if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key.toLowerCase() === 'z') {
                const t = e.target as HTMLElement | null;
                // Don't hijack undo inside an active text/number field.
                if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA')) return;
                e.preventDefault();
                onUndo();
            }
        };
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [onUndo]);

    return (
        <DocContext.Provider value={ctx}>
            <div ref={rootRef} dir="rtl" className="flex gap-6 items-start">
                {/* In-flow spacer reserves the rail's gutter; the rail is position:fixed
                    over it (sticky is broken by the overflow-hidden ancestor). */}
                <div ref={railSpacerRef} className="hidden min-[1100px]:block w-44 flex-shrink-0" aria-hidden />
                <OutlineRail questions={questions} activeId={activeId} findingSections={findingSections} onJump={scrollToScope} railStyle={railBox} />

                <div className="flex-1 min-w-0">
                    {/* Relocated top summary banner — same errorBannerRef contract (§6). */}
                    {errorAnnotations.length > 0 && (
                        <div ref={errorBannerRef} className="scroll-mt-20 mb-4 rounded-lg border border-red-200 bg-red-50/60 p-3 space-y-1.5">
                            <p className="text-sm font-medium text-red-800">יש לתקן לפני שמירה:</p>
                            <ul className="space-y-1 text-sm">
                                {errorAnnotations.map((a) => (
                                    <li key={a.id} className="text-red-700">
                                        {a.target_id ? (
                                            <button type="button" className="underline hover:text-red-900" onClick={() => scrollToScope(a.target_id)}>
                                                {scopeLabel(a.target_id, questions)}
                                            </button>
                                        ) : <span>המחוון</span>}
                                        {' — '}{a.message}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}
                    {globalAnnotations.length > 0 && <div className="mb-4 space-y-1.5">{globalAnnotations.map((a) => <AnnotationBanner key={a.id} annotation={a} />)}</div>}

                    <DocumentHeader
                        name={rubricName}
                        achievable={achievable}
                        declared={rubricTotalPoints}
                        onNameCommit={(v) => onMetadataChange?.({ rubric_name: v })}
                        onDeclaredCommit={(n) => onTotalPointsChange?.(n)}
                        selectionLine={selectionLine}
                        openFindingCount={openFindingCount}
                        canUndo={canUndo}
                        onUndo={onUndo}
                    />

                    <div className="space-y-2">
                        {questions.map((q, i) => (
                            <QuestionSection key={q.question_id} q={q} qIndex={i} isSelectionMember={selectionMemberIds.has(q.question_id)} />
                        ))}
                    </div>
                </div>
            </div>
        </DocContext.Provider>
    );
}
