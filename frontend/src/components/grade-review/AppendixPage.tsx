'use client';

import {
    APPX_FOOTER, APPX_FOOTER_PAGE, APPX_META, APPX_POINTS, APPX_SUMMARY,
    APPX_TEACHER, APPX_TITLE,
} from '@/copy/grade-review';
import type { Appendix, AppendixPageContent } from '@/utils/returned-exam';

/**
 * P4 — one page of the feedback appendix, as the student will receive it.
 *
 * ── WHO THIS PAGE IS WRITTEN FOR ─────────────────────────────────────────
 * Everything else in this module addresses the teacher, in the feminine. This
 * page addresses a STUDENT — any student — so the voice is neutral and the ink
 * grammar changes with it: the red total here is not "the teacher overrode
 * something", it is the grade, in the colour a teacher's pen writes it.
 *
 * ── WHAT IS EXACT AND WHAT IS NOT ────────────────────────────────────────
 * The CONTENT is exact: it comes from the frozen contract through
 * `buildAppendix`, which mirrors `scopes_for_render` — same scopes, same
 * omission of excluded-by-selection questions, same points. The page BREAK is
 * an estimate (`paginateAppendix`), because the PDF paginates by asking
 * PyMuPDF whether the text fit. Nothing she decides on this screen depends on
 * where the break lands.
 *
 * ⚠ DIVERGENCE, REPORTED TO THE OWNER, NOT SILENTLY RESOLVED HERE. Spec §4.3
 * P4 and the mockup both put a red total and per-scope points on this page and
 * title each scope «שאלה 1, סעיף א»; `returned_exam.py` today renders neither
 * the total nor the scope points, and titles scopes with the raw id «q1.א».
 * This component follows the SPEC, because a returned exam carrying no grade
 * anywhere is not a thing to reproduce faithfully. The backend renderer has to
 * come up to the spec before integration; until it does, this preview is ahead
 * of the PDF and that gap is a blocking item, not a rounding error.
 */

export interface AppendixPageProps {
    appendix: Appendix;
    page: AppendixPageContent;
    /** 1-based, for «משוב 1/2». */
    pageNumber: number;
    pageCount: number;
    /** Header line: the exam's name, the student, class, date, teacher. */
    examName: string;
    studentName: string;
    className?: string | null;
    signedDate?: string | null;
    teacherName?: string | null;
}

export function AppendixPage({
    appendix, page, pageNumber, pageCount,
    examName, studentName, className, signedDate, teacherName,
}: AppendixPageProps) {
    return (
        <div
            data-appendix-page={pageNumber}
            /**
             * `aspect` WITHOUT `overflow-hidden`, and the body without `h-full`.
             *
             * A normal page is exactly A4-shaped, because aspect-ratio decides
             * the height whenever the content fits. When the pagination
             * ESTIMATE is wrong — and it is an estimate, see `paginateAppendix`
             * — the sheet GROWS instead of clipping. Clipping was the original
             * shape and it is the worse failure by far: an over-full page still
             * renders as a finished page, so she previews and signs a document
             * whose bottom she never saw (§3.5a — the degradation that keeps
             * rendering confidently is the dangerous one). A slightly tall
             * preview sheet is visible and self-correcting; lost feedback is
             * neither.
             */
            className="relative mx-auto aspect-[1/1.41] w-full max-w-page
                rounded border border-grade-line bg-grade-card shadow-grade"
        >
            <div className="px-appx-x pb-10 pt-appx-top text-gr-rtl text-grade-ink">
                {page.withHeader ? (
                    <header className="mb-3.5 flex items-end justify-between border-b
                        border-grade-ink pb-2">
                        <div>
                            <h2 className="text-gr-appx-h">
                                {APPX_TITLE(examName)}
                            </h2>
                            <div className="text-gr-label text-grade-ink-2">
                                {APPX_META([
                                    studentName,
                                    className,
                                    signedDate,
                                    teacherName ? APPX_TEACHER(teacherName) : null,
                                ])}
                            </div>
                        </div>
                        {/* The grade, in the hand and the red of a teacher's pen.
                            LTR-isolated: a bare numeral beside Hebrew reorders. */}
                        <div
                            data-appendix-total
                            dir="ltr"
                            className="font-hand text-gr-appx-total text-grade-red"
                        >
                            {appendix.total}
                        </div>
                    </header>
                ) : null}

                {page.scopes.map((scope) => (
                    <div key={scope.scopeId} data-appendix-scope={scope.scopeId} className="mb-3">
                        <div className="flex justify-between text-gr-appx-q">
                            <span>{scope.title}</span>
                            <span
                                dir="ltr"
                                className="flex-none whitespace-nowrap text-gr-appx-q font-medium
                                    text-grade-ink-2"
                                style={{ unicodeBidi: 'isolate' }}
                            >
                                {APPX_POINTS(scope.awarded, scope.possible)}
                            </span>
                        </div>

                        {scope.criteria ? (
                            <div
                                data-appendix-breakdown
                                className="my-1.5 border-s-2 border-grade-line ps-2.5
                                    text-gr-label text-grade-ink-2"
                            >
                                {scope.criteria.map((criterion, index) => (
                                    <div
                                        key={`${scope.scopeId}:${index}`}
                                        className="flex justify-between gap-2.5"
                                    >
                                        <span>{criterion.description}</span>
                                        {/* nowrap: a tariff broken across two
                                            lines reads as two numbers, and this
                                            column is the one thing on the page a
                                            student checks digit by digit. */}
                                        <span
                                            dir="ltr"
                                            className="flex-none whitespace-nowrap font-mono text-gr-chip"
                                            style={{ unicodeBidi: 'isolate' }}
                                        >
                                            {APPX_POINTS(criterion.awarded, criterion.possible)}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        ) : null}

                        <p className="mt-px text-grade-ink-2">{scope.feedback}</p>
                    </div>
                ))}

                {page.withSummary && appendix.summary ? (
                    <div data-appendix-summary
                        className="mt-4 border-t border-dashed border-grade-line pt-2.5">
                        <div className="text-gr-appx-q">{APPX_SUMMARY}</div>
                        <p className="mt-px text-grade-ink-2">{appendix.summary}</p>
                    </div>
                ) : null}
            </div>

            <div className="absolute inset-x-appx-x bottom-appx-foot flex justify-between
                text-gr-sm text-grade-pencil">
                <span>{APPX_FOOTER}</span>
                <span dir="ltr" style={{ unicodeBidi: 'isolate' }}>
                    {APPX_FOOTER_PAGE(pageNumber, pageCount)}
                </span>
            </div>
        </div>
    );
}
