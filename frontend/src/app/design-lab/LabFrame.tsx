'use client';

import { useEffect, useMemo } from 'react';
import { RubricDocument } from '@/components/RubricDocument';
import type { RubricQuestion } from '@/types/rubric';
import type { Annotation, SelectionGroup, PedagogicalMistakeWire } from '@/lib/api';
import { composeFindings, deriveFix } from '@/utils/findings';
import { applyEditSteps } from '@/utils/edit-steps';
import { validateAllQuestions } from '@/utils/rubric-validation';

/**
 * Reproduces RubricDocument's REAL production mount context so the shots show the
 * actual visual — the `min-h-screen` brand background, SidebarLayout's
 * `overflow-hidden` main wrapper (the ancestor that breaks sticky), the centered
 * content region, and the white card. `data-lab` marks the snap target.
 *
 * Interactive states (solutions-expanded, editing-a-point, undo-toast) are driven
 * by the snap script (click, then capture); this frame renders the static base.
 *
 * PR-6b CARD STATES (`cards-open` / `cards-resolved` / `cards-dismissed`): the
 * findings are composed EXACTLY as the production page composes them — same
 * module, the fixture's own GT pedagogical_mistakes + live validation — so the
 * shots show the real finding lifecycle, not staged copy. `cards-resolved`
 * additionally APPLIES every proposal through the real edit-steps interpreter,
 * so the resolved shots show genuinely settled sums (hobby: סעיף ג exists, all
 * three q2 findings collapsed).
 */
export function LabFrame({
    questions, annotations, selectionGroups, rubricName, fixture, state,
    pedagogicalMistakes = [],
}: {
    questions: RubricQuestion[]; annotations: Annotation[]; selectionGroups: SelectionGroup[];
    rubricName: string; fixture: string; state: string;
    pedagogicalMistakes?: PedagogicalMistakeWire[];
}) {
    // "solutions-expanded" opens every disclosure so the snap captures them open.
    useEffect(() => {
        if (state !== 'solutions-expanded') return;
        const t = setTimeout(() => {
            document.querySelectorAll<HTMLButtonElement>('button[aria-expanded="false"]').forEach((b) => b.click());
        }, 150);
        return () => clearTimeout(t);
    }, [state]);

    const isCards = state.startsWith('cards');

    const mistakes = useMemo<PedagogicalMistakeWire[]>(() => {
        if (!isCards) return [];
        if (state === 'cards-dismissed') {
            return pedagogicalMistakes.map((m) => ({ ...m, dismissed: true, dismissed_at: '2026-07-31T12:00:00Z' }));
        }
        if (state === 'cards-resolved') {
            return pedagogicalMistakes.map((m) => (m.suggested_fix
                ? { ...m, fix_applied: true, fix_applied_at: '2026-07-31T12:00:00Z' }
                : m));
        }
        return pedagogicalMistakes;
    }, [isCards, state, pedagogicalMistakes]);

    const shownQuestions = useMemo(() => {
        if (state !== 'cards-resolved') return questions;
        // Apply every proposal through the REAL interpreter — the resolved shots
        // must show what one click actually produces, not a hand-arranged tree.
        let qs = questions;
        for (const m of pedagogicalMistakes) {
            if (m.explained_by) continue;                 // shadows have no fix of their own
            const fix = deriveFix(m);
            if (!fix) continue;
            const applied = applyEditSteps(qs, fix.steps);
            if (applied && applied.declaredTotal === undefined) qs = applied.questions;
        }
        return qs;
    }, [state, questions, pedagogicalMistakes]);

    const findings = useMemo(() => {
        if (!isCards) return [];
        const live = Array.from(validateAllQuestions(shownQuestions).values()).flat();
        return composeFindings(annotations, live, mistakes, shownQuestions);
    }, [isCards, annotations, mistakes, shownQuestions]);

    const noop = () => {};

    return (
        <div className="min-h-screen bg-[#FFFaf2]" data-lab={`${fixture}_${state}`}>
            {/* Reproduce SidebarLayout's overflow-hidden main wrapper (the ancestor that
                breaks sticky) — but NO card here; RubricDocument owns its content card. */}
            <div className="overflow-hidden">
                <main className="p-6">
                    <RubricDocument
                        questions={shownQuestions}
                        onQuestionsChange={() => {}}
                        annotations={annotations}
                        rubricName={rubricName}
                        rubricTotalPoints={undefined}
                        selectionGroups={selectionGroups}
                        findings={findings}
                        findingActions={{ applyFix: noop, undoFix: noop, dismiss: noop, reopen: noop }}
                        advisoryScan={isCards ? 'complete' : 'unknown'}
                    />
                </main>
            </div>
        </div>
    );
}
