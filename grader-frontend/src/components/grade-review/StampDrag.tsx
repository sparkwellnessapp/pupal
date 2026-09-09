'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { PV_STAMP_LABEL } from '@/copy/grade-review';
import { StampSvg } from './StampSvg';
import { stampBox, stampPositionFromDrag, type StampPosition } from '@/utils/returned-exam';

/**
 * P3 — the stamp on page 1, draggable.
 *
 * ── WHY IT MEASURES THE PAGE INSTEAD OF ASSUMING IT ──────────────────────
 * The stored position is NORMALIZED (`x`,`y` ∈ 0..1 of the page box) because
 * the PDF is 595pt wide and this preview is however wide the browser made it.
 * Every conversion therefore goes through the live element's own box; a
 * hardcoded page width would place the stamp correctly on one screen and
 * wrongly on every other, and the teacher would never know which one the
 * student got.
 *
 * ── WHY POINTER EVENTS AND NOT MOUSE ─────────────────────────────────────
 * `setPointerCapture` keeps the drag alive when the pointer leaves the stamp,
 * which is most of a real drag, and it is the same code path for touch. The
 * mockup uses the same three handlers.
 *
 * ── WHY THE COMMIT IS ON POINTER-UP, NOT ON MOVE ─────────────────────────
 * Every move would be a PATCH. The position is local while she drags and is
 * persisted once when she lets go — one write per decision, which is also what
 * makes «apply to all» meaningful (it applies a position she settled on).
 *
 * ── AND WHY A BARE CLICK COMMITS NOTHING (`DRAG_THRESHOLD_PX`) ───────────
 * Tapping the stamp to see whether it is interactive must not be recorded as a
 * decision, and the first version recorded it as one. The damage was not
 * cosmetic: the write turns the picker's AUTO corner into a MANUAL point, and
 * `apply_stamp_default_to_draft` refuses to ever move a manual position again —
 * so one exploratory tap would permanently freeze a guess as her choice, offer
 * «apply to all» for a position she never picked, and shift the printed stamp,
 * because a corner and a point are measured from different places.
 */
/** Below this, a pointer gesture is a look, not a decision. */
const DRAG_THRESHOLD_PX = 3;

export interface StampDragProps {
    /** The effective position: hers if set, else the backend's auto corner. */
    position: StampPosition | null;
    /** The score the stamp bears. */
    score: string;
    /** Fired once per drag, with the position to persist. */
    onCommit: (next: StampPosition) => void;
    /** The page element this stamp lives inside; used for the geometry. */
    pageRef: React.RefObject<HTMLElement>;
}

export function StampDrag({ position, score, onCommit, pageRef }: StampDragProps) {
    const ref = useRef<HTMLDivElement | null>(null);
    /** The page's rendered box. Null until measured — see the effect. */
    const [box, setBox] = useState<{ width: number; height: number } | null>(null);
    /** Non-null only DURING a drag; it is the live px position of the box. */
    const [dragging, setDragging] = useState<{ left: number; top: number } | null>(null);
    const grabRef = useRef<
        { dx: number; dy: number; startX: number; startY: number } | null>(null);
    /** Whether this gesture has travelled far enough to be a decision. */
    const movedRef = useRef(false);

    // The page is an image inside a responsive grid, so its box changes with
    // the viewport. Observing it (rather than measuring once) is what keeps the
    // stamp on the same spot of the PAGE when the window is resized.
    useEffect(() => {
        const element = pageRef.current;
        if (!element) return;
        const measure = () => {
            const rect = element.getBoundingClientRect();
            setBox({ width: rect.width, height: rect.height });
        };
        measure();
        if (typeof ResizeObserver === 'undefined') return;
        const observer = new ResizeObserver(measure);
        observer.observe(element);
        return () => observer.disconnect();
    }, [pageRef]);

    const onPointerDown = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
        const element = ref.current;
        if (!element) return;
        const rect = element.getBoundingClientRect();
        grabRef.current = {
            dx: event.clientX - rect.left,
            dy: event.clientY - rect.top,
            startX: event.clientX,
            startY: event.clientY,
        };
        movedRef.current = false;
        setDragging({ left: element.offsetLeft, top: element.offsetTop });
        element.setPointerCapture(event.pointerId);
    }, []);

    const onPointerMove = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
        const grab = grabRef.current;
        const page = pageRef.current;
        if (!grab || !page || !box) return;
        if (Math.abs(event.clientX - grab.startX) > DRAG_THRESHOLD_PX
            || Math.abs(event.clientY - grab.startY) > DRAG_THRESHOLD_PX) {
            movedRef.current = true;
        }
        const pageRect = page.getBoundingClientRect();
        const size = box.width * 0.16;
        const clamp = (v: number, hi: number) => Math.min(hi, Math.max(0, v));
        setDragging({
            left: clamp(event.clientX - pageRect.left - grab.dx, box.width - size),
            top: clamp(event.clientY - pageRect.top - grab.dy, box.height - size),
        });
    }, [box, pageRef]);

    const onPointerUp = useCallback(() => {
        const grab = grabRef.current;
        const moved = movedRef.current;
        grabRef.current = null;
        movedRef.current = false;
        setDragging(null);
        // A gesture that went nowhere leaves the stored position exactly as it
        // was — including leaving an auto corner auto. See DRAG_THRESHOLD_PX.
        if (!grab || !moved || !dragging || !box) return;
        onCommit(stampPositionFromDrag(dragging.left, dragging.top, box.width, box.height));
    }, [box, dragging, onCommit]);

    // Before the first measurement there is no honest place to draw: the page's
    // width is what turns a normalized position into pixels. Rendering at a
    // guessed size would flash the stamp in the wrong corner on every load.
    if (!box) return <div ref={ref} data-stamp-drag data-measured="false" hidden />;

    const resting = stampBox(position, box.width, box.height);
    const left = dragging?.left ?? resting.left;
    const top = dragging?.top ?? resting.top;

    return (
        <div
            ref={ref}
            data-stamp-drag
            data-measured="true"
            role="button"
            tabIndex={0}
            aria-label={PV_STAMP_LABEL}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={onPointerUp}
            style={{ left, top, width: resting.size, height: resting.size }}
            className="absolute touch-none cursor-grab select-none active:cursor-grabbing
                focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2
                focus-visible:outline-primary-600"
        >
            {/* `size` is the box; the svg fills it, so the stamp scales with the
                page exactly as the PDF's 16%-of-width rule does. */}
            <StampSvg score={score} size={resting.size} className="h-full w-full" />
        </div>
    );
}
