'use client';

import { useEffect, useRef, useState } from 'react';

import { fetchTranscriptionPageObjectUrl } from '@/lib/api';
import {
    RV_SCAN_CLOSE, RV_SCAN_FAILED, RV_SCAN_LOADING, RV_SCAN_NONE, RV_SCAN_PAGE,
    RV_SCAN_TITLE,
} from '@/copy/grade-review';

/**
 * R4 — «הצגת הסריקה»: the student's own handwriting for ONE question.
 *
 * The answer block shows the APPROVED TRANSCRIPTION, and the transcription is
 * what was graded — but «אין תשובה בתמלול המאושר · ודאי מול הסריקה» and every
 * fuzzy quote end in the same place: she needs to see the page. This opens the
 * pages the transcription attributed that answer to, in the order they were
 * scanned, and nothing else — a thirty-paper evening has no room for a six-page
 * scroll to find one answer.
 *
 * Pages arrive as authorized BYTES (the same seam the pile thumbnails and the
 * returned exam use — a bare `<img src>` would 401), so every URL minted here is
 * revoked when the viewer closes. Esc closes it and is swallowed on the way
 * down, exactly as the download modal does, so the review surface's own Esc
 * (release the pinned quote) does not fire behind it.
 *
 * When the transcription named NO pages for the answer, the viewer says so
 * rather than guessing a page (§3.5a) — the full scan is one click away on the
 * returned exam.
 */

export interface ScanViewerProps {
    scopeTitle: string;
    transcriptionId: string | null;
    /** 1-based, as the transcription attributes them. Empty = unknown. */
    pageNumbers: readonly number[];
    onClose: () => void;
}

type PageState = { number: number; url: string | null; failed: boolean };

export function ScanViewer({ scopeTitle, transcriptionId, pageNumbers, onClose }: ScanViewerProps) {
    const [pages, setPages] = useState<PageState[]>(
        () => pageNumbers.map((number) => ({ number, url: null, failed: false })));
    const closeRef = useRef<HTMLButtonElement | null>(null);

    useEffect(() => {
        closeRef.current?.focus();
        const onKey = (event: KeyboardEvent) => {
            if (event.key === 'Escape') { event.stopPropagation(); onClose(); }
        };
        document.addEventListener('keydown', onKey, true);
        return () => document.removeEventListener('keydown', onKey, true);
    }, [onClose]);

    useEffect(() => {
        if (!transcriptionId || pageNumbers.length === 0) return;
        let cancelled = false;
        const minted: string[] = [];
        for (const number of pageNumbers) {
            fetchTranscriptionPageObjectUrl(transcriptionId, number)
                .then((url) => {
                    if (cancelled) { URL.revokeObjectURL(url); return; }
                    minted.push(url);
                    setPages((prev) => prev.map(
                        (p) => (p.number === number ? { ...p, url } : p)));
                })
                .catch(() => {
                    if (cancelled) return;
                    // One page failing must not blank the others — she still
                    // sees what loaded, and the failed one says so in place.
                    setPages((prev) => prev.map(
                        (p) => (p.number === number ? { ...p, failed: true } : p)));
                });
        }
        return () => {
            cancelled = true;
            minted.forEach((url) => URL.revokeObjectURL(url));
        };
    }, [transcriptionId, pageNumbers]);

    return (
        <div
            data-scan-viewer
            role="dialog"
            aria-modal="true"
            aria-label={RV_SCAN_TITLE(scopeTitle)}
            onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
            className="fixed inset-0 z-[90] flex items-start justify-center overflow-y-auto
                bg-grade-ink/35 px-4 py-6"
        >
            <div className="w-full max-w-page rounded-modal bg-grade-card px-6 py-5 shadow-grade">
                <div className="mb-4 flex items-center justify-between gap-3">
                    <h3 className="text-gr-h2 text-grade-ink">{RV_SCAN_TITLE(scopeTitle)}</h3>
                    <button
                        ref={closeRef}
                        type="button"
                        onClick={onClose}
                        className="rounded-grade-ctl border border-grade-line bg-grade-card
                            px-3.5 py-1.5 text-gr-body text-grade-ink hover:border-grade-pencil-2"
                    >
                        {RV_SCAN_CLOSE}
                    </button>
                </div>

                {pageNumbers.length === 0 || !transcriptionId ? (
                    <p data-scan-none className="rounded-grade-ctl border border-grade-amber-200
                        bg-grade-amber-50 px-4 py-3 text-gr-body text-grade-amber-ink">
                        {RV_SCAN_NONE}
                    </p>
                ) : (
                    <div className="flex flex-col gap-4">
                        {pages.map((page) => (
                            <figure key={page.number} data-scan-page={page.number}>
                                <figcaption className="mb-1.5 text-gr-label text-grade-pencil">
                                    {RV_SCAN_PAGE(page.number)}
                                </figcaption>
                                {page.url ? (
                                    // eslint-disable-next-line @next/next/no-img-element
                                    <img
                                        src={page.url}
                                        alt={RV_SCAN_PAGE(page.number)}
                                        className="w-full rounded border border-grade-line
                                            bg-grade-paper shadow-grade"
                                    />
                                ) : (
                                    <div className="grid aspect-[1/1.41] w-full place-items-center
                                        rounded border border-dashed border-grade-line bg-grade-paper
                                        text-gr-body text-grade-pencil">
                                        {page.failed ? RV_SCAN_FAILED : RV_SCAN_LOADING}
                                    </div>
                                )}
                            </figure>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
