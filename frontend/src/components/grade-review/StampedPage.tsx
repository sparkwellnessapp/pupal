'use client';

import { useRef } from 'react';

import type { StampPosition } from '@/utils/returned-exam';
import { StampDrag } from './StampDrag';

/**
 * THE stamped page — one component, two surfaces (student-profile PR OD-8,
 * UI-2 OneStampRenderer).
 *
 * The returned exam's page view (full size, the stamp draggable) and the
 * profile's row thumbnail (~100 px, read-only) draw the SAME thing: the scan
 * page in a 1:1.41 paper box, and on page 1 the approval stamp at its resolved
 * position. Extracted from `ReturnedExamPreview` verbatim — same element, same
 * classes — and proven pixel-identical there before the profile reused it
 * (M-A7), because the returned exam is the artefact teachers send home.
 *
 * Why the geometry is size-invariant without this component doing any maths:
 * `StampDrag` measures the box it lives in and places the stamp through
 * `stampBox` — the position is normalized (fractions of the page, or a
 * corner), so 96 px and 800 px put the stamp on the same spot of the PAGE.
 * That is the one place the stamp is positioned, on both surfaces.
 *
 * No fetching inside (§6.4 step 1): the caller resolves the image through the
 * authorized seam and hands over an object URL — or null, which renders the
 * empty paper rather than a broken-image glyph (degrade by omission).
 */
export interface StampedPageProps {
    /** An object URL from `fetchPageImageObjectUrl`, or null for empty paper. */
    imageUrl: string | null;
    /** Draw the stamp at all. False for scan pages 2+ on the returned page. */
    stamped?: boolean;
    /** The effective total, as the pricer renders it. */
    score: string;
    /** The RESOLVED position (test overlay → batch default → null = auto corner). */
    stampPosition: StampPosition | null;
    /** Present → the stamp is draggable (the returned page). Absent → read-only. */
    onStampCommit?: (next: StampPosition) => void;
    alt?: string;
    /** Sizing and placement — the box's aspect and paper styling are fixed here. */
    className?: string;
    'data-page-view'?: string;
}

export function StampedPage({
    imageUrl, stamped = true, score, stampPosition, onStampCommit, alt = '',
    className, ...rest
}: StampedPageProps) {
    const pageRef = useRef<HTMLDivElement | null>(null);
    return (
        <div
            ref={pageRef}
            data-page-view={rest['data-page-view']}
            className={[
                'relative aspect-[1/1.41] overflow-hidden rounded border border-grade-line',
                'bg-grade-paper shadow-grade',
                className ?? '',
            ].filter(Boolean).join(' ')}
        >
            {imageUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                    src={imageUrl}
                    alt={alt}
                    className="absolute inset-0 h-full w-full object-contain"
                />
            ) : null}
            {stamped ? (
                <StampDrag
                    position={stampPosition}
                    score={score}
                    onCommit={onStampCommit}
                    readOnly={!onStampCommit}
                    pageRef={pageRef}
                />
            ) : null}
        </div>
    );
}
