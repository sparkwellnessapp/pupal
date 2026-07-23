'use client';

import { useEffect } from 'react';
import { RubricDocument } from '@/components/RubricDocument';
import type { RubricQuestion } from '@/types/rubric';
import type { Annotation, SelectionGroup } from '@/lib/api';

/**
 * Reproduces RubricDocument's REAL production mount context so the shots show the
 * actual visual — the `min-h-screen` brand background, SidebarLayout's
 * `overflow-hidden` main wrapper (the ancestor that breaks sticky), the centered
 * content region, and the white card. `data-lab` marks the snap target.
 *
 * Interactive states (solutions-expanded, editing-a-point, undo-toast) are driven
 * by the snap script (click, then capture); this frame renders the static base.
 */
export function LabFrame({
    questions, annotations, selectionGroups, rubricName, fixture, state,
}: {
    questions: RubricQuestion[]; annotations: Annotation[]; selectionGroups: SelectionGroup[];
    rubricName: string; fixture: string; state: string;
}) {
    // "solutions-expanded" opens every disclosure so the snap captures them open.
    useEffect(() => {
        if (state !== 'solutions-expanded') return;
        const t = setTimeout(() => {
            document.querySelectorAll<HTMLButtonElement>('button[aria-expanded="false"]').forEach((b) => b.click());
        }, 150);
        return () => clearTimeout(t);
    }, [state]);

    return (
        <div className="min-h-screen bg-[#FFFaf2]" data-lab={`${fixture}_${state}`}>
            {/* Reproduce SidebarLayout's overflow-hidden main wrapper (the ancestor that
                breaks sticky) — but NO card here; RubricDocument owns its content card. */}
            <div className="overflow-hidden">
                <main className="p-6">
                    <RubricDocument
                        questions={questions}
                        onQuestionsChange={() => {}}
                        annotations={annotations}
                        rubricName={rubricName}
                        rubricTotalPoints={undefined}
                        selectionGroups={selectionGroups}
                    />
                </main>
            </div>
        </div>
    );
}
