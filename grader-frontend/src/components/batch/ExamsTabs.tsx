'use client';

/**
 * §5.7 — «המבחנים שלי», one place, two views.
 *
 * ── THE FOLD (OD-1 ruled; R12's mechanics) ────────────────────────────────
 * `המבחנים שלי` did not exist. The sidebar carried `המקבצים שלי` (`/batches`)
 * and `מבחנים בדוקים` (`/my-graded-tests`), which are not two sections — they
 * are the same objects at two zoom levels: the exam events she uploaded, and
 * the individual signed tests inside them. Two sidebar entries for one thing is
 * how a teacher ends up asking which of them her work is in.
 *
 * So the section is ONE (`המבחנים שלי`), and the zoom level is a TAB. The
 * batch list is the default view, because that is where work happens; the
 * cross-batch list of individual graded tests stays reachable and stays at its
 * own route — moving the route would break every link that already points at
 * it for nothing. Nothing here redirects; nothing is deleted.
 */

import Link from 'next/link';

import { TAB_BY_EXAM, TAB_GRADED_TESTS, TABS_LABEL } from '@/copy/batch';

export type ExamsTab = 'batches' | 'graded';

const TABS: ReadonlyArray<{ key: ExamsTab; href: string; label: string }> = [
    { key: 'batches', href: '/batches', label: TAB_BY_EXAM },
    { key: 'graded', href: '/my-graded-tests', label: TAB_GRADED_TESTS },
];

export function ExamsTabs({ active }: { active: ExamsTab }) {
    return (
        <nav
            data-testid="exams-tabs"
            // NOT the section title: the sidebar is also a <nav>, and two of
            // them sharing a name makes every role query over either one
            // ambiguous — for a screen reader as much as for a test.
            aria-label={TABS_LABEL}
            className="mb-5 flex items-center gap-1 border-b border-batch-line"
        >
            {TABS.map((tab) => (
                <Link
                    key={tab.key}
                    href={tab.href}
                    data-tab={tab.key}
                    aria-current={active === tab.key ? 'page' : undefined}
                    className={[
                        '-mb-px border-b-2 px-3 py-2 text-sm transition-colors',
                        active === tab.key
                            ? 'border-primary-500 font-semibold text-batch-ink'
                            : 'border-transparent text-batch-muted hover:text-batch-ink',
                    ].join(' ')}
                >
                    {tab.label}
                </Link>
            ))}
        </nav>
    );
}
