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
    changeSubQuestionPointsAtPath, setSubQuestionTextAtPath,
    setQuestionText as setQuestionTextOp,
} from '@/utils/rubric-editor-ops';
import { computeAchievablePoints } from '@/utils/rubric-achievable';
import { scopeLabel, questionLabel, subQuestionLabel, humanizeScopeIds } from '@/utils/scope-label';
import { splitRoutingPrefix } from '@/utils/routing-prefix';
import { selectionSummaryLine, findingSectionsByQuestion } from '@/utils/session-spine';
import { isOpenFinding, visibleAnnotations } from '@/utils/finding-severity';
import { changedPointNodeIds } from '@/utils/points-cascade';
import { buildRailOutline, type RailNode } from '@/utils/rail-outline';
import { formatPoints } from '@/utils/rubric-display';
import { ChevronDown, ChevronLeft } from 'lucide-react';
import { AnnotationBanner } from '@/components/AnnotationBanner';
import { EditableText } from '@/components/document/EditableText';
import { EditablePoints } from '@/components/document/EditablePoints';
import { DisclosureRow } from '@/components/document/DisclosureRow';
import { CodeBlock } from '@/components/document/CodeBlock';
import { TraceTablesDisplay, ContextTablesDisplay } from '@/components/document/DataTables';
import { DocumentText, SolutionBody } from '@/components/document/DocumentText';
import { FindingCard } from '@/components/document/FindingCard';
import { countFindingsByClass, findingsSummaryLine, type Finding } from '@/utils/findings';

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
    /** D5 — a sub-question's DECLARED points, at any depth. No redistribution. */
    changeSubQuestionPoints(qIndex: number, sqPath: number[], n: number): void;
    /** D8 — prose, edited RAW. */
    changeQuestionText(qIndex: number, text: string): void;
    changeSubQuestionText(qIndex: number, sqPath: number[], text: string): void;
}

interface DocContextValue extends DocOps {
    questions: RubricQuestion[];
    annotations: Annotation[];
    changedIds: Set<string>;
    scrollToScope(targetId: string | null): void;
    /** PR-6 — the composed findings, and the four decisions she can make on one. */
    findings: Finding[];
    findingActions: FindingActions;
}

/** PR-6 §3/§4 — every decision the card can hand back to the page. */
export interface FindingActions {
    applyFix(finding: Finding): void;
    undoFix(finding: Finding): void;
    dismiss(finding: Finding): void;
    reopen(finding: Finding): void;
}

const NO_FINDING_ACTIONS: FindingActions = {
    applyFix: () => {}, undoFix: () => {}, dismiss: () => {}, reopen: () => {},
};

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

/**
 * PR-6 — the findings anchored at ONE scope. This supersedes the raw annotation
 * banner at every node that has a composed finding: the card carries the same
 * event with its explanation, its proposal and its lifecycle, instead of three
 * separate voices saying overlapping things about one problem.
 */
function ScopeFindings({ scopeId }: { scopeId: string | undefined }) {
    const { findings, findingActions, questions, scrollToScope } = useDoc();
    if (!scopeId) return null;
    const here = findings.filter((f) => f.scopeId === scopeId);
    if (here.length === 0) return null;
    return (
        <div className="space-y-2 my-2">
            {here.map((f) => (
                <FindingCard
                    key={f.key}
                    finding={f}
                    scopeText={scopeLabel(f.scopeId, questions)}
                    onApplyFix={findingActions.applyFix}
                    onUndoFix={findingActions.undoFix}
                    onDismiss={findingActions.dismiss}
                    onReopen={findingActions.reopen}
                    onJump={(x) => scrollToScope(x.scopeId)}
                />
            ))}
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
                    <td className="py-1.5 pr-8 pl-3 text-surface-600 text-doc-meta">
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
        <table ref={tableRef} className="w-full border-collapse my-3 text-doc-table" dir="rtl">
            <thead>
                <tr className="text-surface-400 text-doc-meta">
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
                            <tr><td colSpan={3}><ScopeFindings scopeId={c.criterion_id} /></td></tr>
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
    // ONE path for every answer key — SolutionBody owns the uniform grey surface
    // and routes tables / code / prose inside it. The old split (DocumentText for
    // table-bearing solutions, CodeBlock otherwise) is exactly why some solutions
    // had a grey box and some didn't.
    return (
        <DisclosureRow label="פתרון לדוגמה" toggleLabel="פתרון לדוגמה" className="my-2">
            <SolutionBody text={solution} />
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
    const { annotations, changedIds, changeSubQuestionPoints, changeSubQuestionText } = useDoc();
    const heading = sq.title?.trim() || subQuestionLabel(sq, sqPath[sqPath.length - 1], depth);
    const hasChildren = (sq.sub_questions?.length ?? 0) > 0;
    const anns = annotationsFor(annotations, idPath, sq.sub_question_id);

    return (
        <section data-scope-id={idPath} className="scroll-mt-20 mr-3 border-r border-surface-100 pr-3 mt-3">
            <div className="flex items-baseline justify-between gap-3">
                <h4 className="text-doc-sq text-surface-800">{heading}</h4>
                {/* D5: every point-bearing node is editable. This sets the DECLARED
                    value; the E-3 cascade still re-derives it from criteria on the
                    next criterion edit in this subtree (upward recomputation stays
                    where it already was). */}
                <PointsChip
                    value={sq.points}
                    ariaLabel={`ניקוד ${heading} — לחצי לעריכה`}
                    editable
                    onCommit={(n) => changeSubQuestionPoints(qIndex, sqPath, n)}
                    changed={changedIds.has(sq.sub_question_id)}
                />
            </div>

            {/* D8: display-rich / edit-raw. */}
            {sq.text?.trim() ? (
                <EditableText
                    value={sq.text}
                    onCommit={(text) => changeSubQuestionText(qIndex, sqPath, text)}
                    ariaLabel={`טקסט ${heading} — לחצי לעריכה`}
                    dir="rtl"
                    block
                    className="mt-1"
                    renderDisplay={(v) => <DocumentText text={v} />}
                />
            ) : null}
            <TraceTablesDisplay tables={sq.trace_tables} />
            <InlineAnnotations annotations={anns} />
            <ScopeFindings scopeId={idPath} />

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
    const { annotations, changedIds, changeQuestionPoints, changeQuestionText } = useDoc();
    const heading = questionLabel(q, qIndex);
    const hasSubs = q.sub_questions.length > 0;
    const anns = annotationsFor(annotations, q.question_id);

    return (
        <section
            data-scope-id={q.question_id}
            className="scroll-mt-20 doc-enter-section"
            style={{ animationDelay: `${Math.min(qIndex, 8) * 40}ms` }}
        >
            <div className="flex items-baseline justify-between gap-3 border-b border-surface-100 pb-2">
                <h3 className="text-doc-q text-surface-900 flex items-center gap-2">
                    {heading}
                    {isSelectionMember && <span className="text-xs font-normal text-primary-600 bg-primary-50 rounded-full px-2 py-0.5">שאלת בחירה</span>}
                </h3>
                {/* D5: editable at every point-bearing node. A question's total is
                    teacher-authoritative (INV-R1 surfaces any gap). For a
                    direct-criteria question the E-3 cascade still re-derives it on
                    the next criterion edit — upward recomputation is unchanged. */}
                <PointsChip
                    value={q.total_points}
                    ariaLabel={`ניקוד ${heading} — לחצי לעריכה`}
                    editable
                    onCommit={(n) => changeQuestionPoints(qIndex, n)}
                    changed={changedIds.has(q.question_id)}
                />
            </div>

            {/* D8: display-rich / edit-raw. */}
            {q.question_text?.trim() ? (
                <EditableText
                    value={q.question_text}
                    onCommit={(text) => changeQuestionText(qIndex, text)}
                    ariaLabel={`טקסט ${heading} — לחצי לעריכה`}
                    dir="rtl"
                    block
                    className="mt-2"
                    renderDisplay={(v) => <DocumentText text={v} />}
                />
            ) : null}
            {q.code_blocks?.map((code, i) => <CodeBlock key={i} code={code} />)}
            <ContextTablesDisplay tables={q.context_tables} />
            <TraceTablesDisplay tables={q.trace_tables} />
            <InlineAnnotations annotations={anns} />
            <ScopeFindings scopeId={q.question_id} />

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

/**
 * D3 — THE HEADER BAND. One composed unit that sits ABOVE the document body and
 * reads as its own surface, not as fragments stacked on the page (audit F1). A
 * two-column grid: identity on the right-hand start (name + selection line), the
 * ONE number and the undo affordance on the far side, the reassurance line
 * spanning the band when there is nothing to fix.
 *
 * D4 — מוצהר LEAVES THE HEADER. The band shows the ACHIEVABLE total, alone,
 * live-updating as points change. The declared total stays in page state (INV-R3
 * and dehydrate depend on it, and the undo tuple is unchanged) but has NO surface
 * here — an orphaned edit affordance for a number whose only meaning is "the other
 * half of a mismatch" is exactly the scattered-fragment problem. When declared and
 * achievable disagree, INV-R3 fires and the finding carries the pair with the
 * context a teacher needs; resolving it happens by editing points.
 */
function DocumentHeader({
    name, achievable, onNameCommit, selectionLine, openFindingCount, findingsLine, canUndo, onUndo,
}: {
    name: string; achievable: number; findingsLine: string | null;
    onNameCommit: (v: string) => void;
    selectionLine: string | null; openFindingCount: number; canUndo: boolean; onUndo?: () => void;
}) {
    return (
        <header className="mb-5 doc-enter-header">
            <div className="rounded-2xl bg-white ring-1 ring-surface-200 shadow-sm px-7 py-5 grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-6 gap-y-2">
                <div className="min-w-0">
                    <h1 className="text-doc-title text-surface-900">
                        <EditableText value={name} onCommit={onNameCommit} ariaLabel="שם המחוון — לחצי לעריכה" dir="rtl" placeholder="שם המחוון" />
                    </h1>
                    {selectionLine && <p className="text-doc-meta text-surface-500 mt-1.5">{selectionLine}</p>}
                </div>

                <div className="flex items-center gap-4 flex-shrink-0">
                    {canUndo && (
                        <button
                            type="button"
                            onClick={onUndo}
                            className="text-doc-meta text-surface-500 hover:text-surface-900 hover:bg-surface-50 rounded-lg px-2.5 py-1.5 transition-colors"
                        >ביטול</button>
                    )}
                    <div className="rounded-xl bg-primary-50 px-4 py-2 text-center">
                        <div data-testid="rubric-achievable-total" className="text-doc-title text-primary-800 tabular-nums leading-none">
                            {achievable}<span className="text-doc-meta font-normal text-primary-700 mr-1">נק&apos;</span>
                        </div>
                        <div className="text-doc-meta text-primary-700 mt-1">סה&quot;כ</div>
                    </div>
                </div>

                {/* §5 — blockers and advisories are counted SEPARATELY; a blocker and
                    a suggestion are not the same news and must not share a number. */}
                {findingsLine
                    ? <p className="col-span-2 text-doc-meta text-surface-600">{findingsLine}</p>
                    : openFindingCount === 0 && (
                        <p className="col-span-2 text-doc-meta text-emerald-700">הכל תקין - ויוי לא מצאה אי-התאמות במחוון ✓</p>
                    )}
            </div>
        </header>
    );
}

/** Indent per depth. Static literals — Tailwind cannot see a computed class name. */
const RAIL_INDENT = ['', 'pr-3', 'pr-6', 'pr-9', 'pr-12'] as const;

/**
 * One rail row, recursive. TWO targets with ONE job each: the chevron opens/closes
 * the branch, the label jumps to the scope. Collapsing was added without taking
 * navigation away from parents — a row that both navigated and toggled would slam
 * the branch shut every time she re-visited the question.
 */
function RailRow({
    node, activeId, findingSections, isOpen, onToggle, onJump,
}: {
    node: RailNode; activeId: string | null; findingSections: Set<string>;
    isOpen: (n: RailNode) => boolean; onToggle: (n: RailNode) => void; onJump: (id: string) => void;
}) {
    const open = isOpen(node);
    const hasChildren = node.children.length > 0;
    const active = node.id === activeId;

    return (
        <li>
            <div className={`flex items-center gap-1 ${RAIL_INDENT[Math.min(node.depth, RAIL_INDENT.length - 1)]}`}>
                {hasChildren ? (
                    <button
                        type="button"
                        onClick={() => onToggle(node)}
                        aria-expanded={open}
                        aria-label={`${open ? 'כווצי' : 'הרחיבי'} ${node.label}`}
                        className="flex-shrink-0 text-surface-400 hover:text-surface-700 transition-colors"
                    >
                        {open ? <ChevronDown size={14} /> : <ChevronLeft size={14} />}
                    </button>
                ) : (
                    <span className="w-3.5 flex-shrink-0" aria-hidden />
                )}
                <button
                    type="button"
                    data-rail-link={node.id}
                    onClick={() => onJump(node.id)}
                    className={`flex items-center gap-1.5 min-w-0 flex-1 text-right transition-colors ${active ? 'text-primary-700 font-medium' : 'text-surface-500 hover:text-surface-800'}`}
                >
                    {findingSections.has(node.id) && <span className="w-1.5 h-1.5 rounded-full bg-amber-400 flex-shrink-0" aria-label="ממצא פתוח" />}
                    {/* The label sizes to its TEXT (no flex-1). Letting it grow pushed
                        the number to the far edge of the gutter, so a short label like
                        "שאלה 1" left a wide void between a row and its own points. The
                        number now travels with the label it belongs to; the trailing
                        space simply falls at the end of the row. */}
                    <span className="truncate min-w-0">{node.label}</span>
                    <span className="tabular-nums text-surface-400 flex-shrink-0">{formatPoints(node.points)}</span>
                </button>
            </div>
            {hasChildren && open && (
                <ul className="space-y-1 mt-1">
                    {node.children.map((child) => (
                        <RailRow
                            key={child.id} node={child} activeId={activeId} findingSections={findingSections}
                            isOpen={isOpen} onToggle={onToggle} onJump={onJump}
                        />
                    ))}
                </ul>
            )}
        </li>
    );
}

function OutlineRail({
    questions, activeId, findingSections, onJump, railStyle,
}: {
    questions: RubricQuestion[]; activeId: string | null; findingSections: Set<string>;
    onJump: (id: string) => void; railStyle: { left: number; width: number } | null;
}) {
    const outline = useMemo(() => buildRailOutline(questions), [questions]);

    // Expansion = an AUTO rule the teacher can override. Auto: the question she is
    // reading opens, the rest stay shut, so the map stays short and tracks her
    // position. A chevron click records an explicit preference for that branch, and
    // explicit ALWAYS wins — scrolling never re-closes something she opened.
    const [manual, setManual] = useState<Record<string, boolean>>({});
    const autoOpen = useCallback((n: RailNode) => n.depth === 0 && n.id === activeId, [activeId]);
    const isOpen = useCallback((n: RailNode) => manual[n.id] ?? autoOpen(n), [manual, autoOpen]);
    const onToggle = useCallback((n: RailNode) => {
        const current = manual[n.id] ?? autoOpen(n);
        setManual((m) => ({ ...m, [n.id]: !current }));
    }, [manual, autoOpen]);

    // position: FIXED, not sticky — SidebarLayout's `overflow-hidden` ancestor breaks
    // sticky (verified in headless Chromium: the rail scrolls away). The spacer in the
    // flex row reserves this gutter; we pin the rail over it (left/width measured).
    return (
        <nav
            aria-label="מפת המחוון"
            style={railStyle ? { position: 'fixed', top: 80, left: railStyle.left, width: railStyle.width } : undefined}
            className={`hidden rail:block w-rail text-doc-meta max-h-[calc(100vh-100px)] overflow-y-auto ${railStyle ? '' : 'sticky top-20 self-start flex-shrink-0'}`}
        >
            <ul className="space-y-1 border-r border-surface-100 pr-4">
                {outline.map((node) => (
                    <RailRow
                        key={node.id} node={node} activeId={activeId} findingSections={findingSections}
                        isOpen={isOpen} onToggle={onToggle} onJump={onJump}
                    />
                ))}
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
    /**
     * PR-6 — the composed findings, and the decisions she can make on them.
     * Composed by the PAGE (which also derives the save-time acknowledgment set
     * from them), so there is exactly one composition per render and the card and
     * the save gate can never disagree about a finding's status.
     */
    findings?: Finding[];
    findingActions?: FindingActions;
    /** §7 — whether the advisory scan completed; drives the honesty notice. */
    advisoryScan?: 'complete' | 'partial' | 'unknown';
}

export function RubricDocument({
    questions,
    onQuestionsChange,
    annotations = [],
    errorBannerRef,
    rubricName = '',
    // D4: `rubricTotalPoints` / `onTotalPointsChange` stay on the prop seam (parity
    // with RubricEditor; page state and the undo tuple are unchanged) but the band
    // renders NO declared-total surface — see DocumentHeader.
    onMetadataChange,
    selectionGroups = [],
    canUndo = false,
    onUndo,
    findings = [],
    findingActions = NO_FINDING_ACTIONS,
    advisoryScan = 'unknown',
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

    // D9 — RAIL LANDING. `block: 'center'` centered the whole SECTION, so for any
    // section taller than the viewport the heading landed far above the top edge
    // (off-screen) and the teacher arrived mid-body. `block: 'start'` lands the
    // section's own top edge and — unlike 'center' — honours `scroll-margin-top`,
    // which every section carries as `scroll-mt-20` (5rem) to clear the ~80px
    // sticky app header. Anchor + margin together put the TITLE just below the
    // header at both viewports.
    const scrollToScope = useCallback((targetId: string | null) => {
        if (!targetId) return;
        document.querySelector(`[data-scope-id="${targetId}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
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
        // D5: a parent edit sets that node's DECLARED value and NOTHING else — no
        // downward redistribution, no rescaling of children. If it opens a sum gap,
        // the live validator fires and the finding renders: surfacing a discrepancy
        // is the product, inventing a number to hide it is not (§2 FC).
        changeSubQuestionPoints: (qIndex, sqPath, n) =>
            onQuestionsChange(changeSubQuestionPointsAtPath(questions, qIndex, sqPath, n)),
        // D8: commit the RAW string verbatim — no trim, no normalization, so
        // dehydrate emits byte-identically what she typed.
        changeQuestionText: (qIndex, text) => onQuestionsChange(setQuestionTextOp(questions, qIndex, text)),
        changeSubQuestionText: (qIndex, sqPath, text) =>
            onQuestionsChange(setSubQuestionTextAtPath(questions, qIndex, sqPath, text)),
    }), [questions, onQuestionsChange]);

    // ── D7: the ONE annotation transform, at the root, so every consumer (inline
    // banners, the blocking summary, rail dots, the reassurance count) reads the
    // same truth. Two rules, both from the shared modules:
    //   1. visibleAnnotations — a static extraction message is suppressed when a
    //      LIVE validator entry covers the same node (the stale-assertion class:
    //      the frozen message keeps asserting extraction-time numbers).
    //   2. humanizeScopeIds — a backend message interpolates the raw scope id
    //      ("בQ1"); the naming law applies to message bodies, not just labels.
    const shownAnnotations = useMemo(
        () => visibleAnnotations(annotations).map((a) => (
            a.message ? { ...a, message: humanizeScopeIds(a.message, questions) } : a
        )),
        [annotations, questions],
    );

    // PR-6 — an annotation that a finding already carries must NOT also render as a
    // raw banner: one event, one voice. Everything a card does not cover still
    // renders through the old path, so nothing is silently dropped.
    const coveredAnnotationIds = useMemo(() => {
        const s = new Set<string>();
        for (const f of findings) for (const id of f.annotationIds) s.add(id);
        return s;
    }, [findings]);

    const uncoveredAnnotations = useMemo(
        () => shownAnnotations.filter((a) => !coveredAnnotationIds.has(a.id)),
        [shownAnnotations, coveredAnnotationIds],
    );

    const ctx: DocContextValue = useMemo(() => ({
        ...ops, questions, annotations: uncoveredAnnotations, changedIds, scrollToScope,
        findings, findingActions,
    }), [ops, questions, uncoveredAnnotations, changedIds, scrollToScope, findings, findingActions]);

    // ── Derived ──
    const achievable = useMemo(() => computeAchievablePoints(questions, selectionGroups), [questions, selectionGroups]);
    const selectionLine = useMemo(() => selectionSummaryLine(selectionGroups), [selectionGroups]);
    const findingSections = useMemo(() => findingSectionsByQuestion(shownAnnotations, questions), [shownAnnotations, questions]);
    const selectionMemberIds = useMemo(() => {
        const s = new Set<string>();
        selectionGroups.forEach((g) => g.of_question_ids.forEach((id) => s.add(id)));
        return s;
    }, [selectionGroups]);
    const errorAnnotations = useMemo(() => shownAnnotations.filter((a) => a.severity === 'error'), [shownAnnotations]);
    const globalAnnotations = useMemo(() => shownAnnotations.filter((a) => a.target_id === null || a.target_id === 'rubric'), [shownAnnotations]);
    const openFindingCount = useMemo(() => shownAnnotations.filter(isOpenFinding).length, [shownAnnotations]);

    // §2 — target-less findings render in the advisory strip, not on a node.
    const documentFindings = useMemo(() => findings.filter((f) => f.scopeId === null), [findings]);
    // §5 — the two classes are counted separately and never summed into one number.
    const findingCounts = useMemo(() => countFindingsByClass(findings), [findings]);
    const findingsLine = useMemo(() => findingsSummaryLine(findingCounts), [findingCounts]);

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
            {/* §1a: rail is a SIBLING of the content column, OUTSIDE the white card.
                In-flow spacer reserves its gutter; the rail is position:fixed over it
                (sticky is broken by SidebarLayout's overflow-hidden ancestor). */}
            <div ref={rootRef} dir="rtl" className="flex gap-8 items-start justify-center">
                <div ref={railSpacerRef} className="hidden rail:block w-rail flex-shrink-0" aria-hidden />
                <OutlineRail questions={questions} activeId={activeId} findingSections={findingSections} onJump={scrollToScope} railStyle={railBox} />

                <div className="flex-1 min-w-0 max-w-document">
                    {/* D3: the band is its OWN surface, above the document body. */}
                    <DocumentHeader
                        name={rubricName}
                        achievable={achievable}
                        onNameCommit={(v) => onMetadataChange?.({ rubric_name: v })}
                        selectionLine={selectionLine}
                        openFindingCount={openFindingCount}
                        findingsLine={findingsLine}
                        canUndo={canUndo}
                        onUndo={onUndo}
                    />

                    <div className="bg-white rounded-2xl shadow-sm ring-1 ring-surface-100 px-8 py-7">
                        {/* Relocated top summary banner — same errorBannerRef contract (§6). */}
                        {errorAnnotations.length > 0 && (
                            <div ref={errorBannerRef} className="scroll-mt-20 mb-6 rounded-lg border border-red-200 bg-red-50/60 p-4 space-y-2">
                                <p className="text-doc-table font-semibold text-red-800">יש לתקן לפני שמירה:</p>
                                <ul className="space-y-1.5 text-doc-table">
                                    {errorAnnotations.map((a) => (
                                        <li key={a.id} className="text-red-700">
                                            {a.target_id ? (
                                                <button type="button" className="underline decoration-red-300 underline-offset-2 hover:text-red-900" onClick={() => scrollToScope(a.target_id)}>
                                                    {scopeLabel(a.target_id, questions)}
                                                </button>
                                            ) : <span>המחוון</span>}
                                            {' — '}{a.message}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}
                        {globalAnnotations.length > 0 && <div className="mb-6 space-y-2">{globalAnnotations.map((a) => <AnnotationBanner key={a.id} annotation={a} />)}</div>}

                        {/* §7 — PARTIAL-SCAN HONESTY. An empty advisory list must never
                            read as a clean bill of health when we do not know the scan
                            finished. Quiet, reassuring, and never alarming: the rubric
                            IS usable; we simply will not claim more than we checked. */}
                        {advisoryScan === 'partial' && (
                            <p className="mb-6 rounded-lg border border-surface-200 bg-surface-50 px-3 py-2 text-doc-meta text-surface-600">
                                חלק מבדיקות ההמלצות לא הושלמו (תקלה זמנית) — המחוון תקין לשימוש.
                            </p>
                        )}

                        {/* §2 — document-level findings (selection normalization, and any
                            other target-less kind) live in the strip, not on a node. */}
                        {documentFindings.length > 0 && (
                            <div className="mb-6 space-y-2">
                                {documentFindings.map((f) => (
                                    <FindingCard
                                        key={f.key}
                                        finding={f}
                                        scopeText="המחוון"
                                        onApplyFix={findingActions.applyFix}
                                        onUndoFix={findingActions.undoFix}
                                        onDismiss={findingActions.dismiss}
                                        onReopen={findingActions.reopen}
                                        onJump={() => scrollToScope(null)}
                                    />
                                ))}
                            </div>
                        )}

                        <div className="space-y-12">
                            {questions.map((q, i) => (
                                <QuestionSection key={q.question_id} q={q} qIndex={i} isSelectionMember={selectionMemberIds.has(q.question_id)} />
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        </DocContext.Provider>
    );
}
