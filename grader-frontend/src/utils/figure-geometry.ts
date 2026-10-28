/**
 * Where a drawing's crop is cut, and where each reading's chip sits on it
 * (MATH_RENDERING_PLAN §5). Pure — every number is a percentage of the CROP, so the card
 * can be any width and the chips stay on their marks.
 *
 * Coordinates arrive on the figure pass's grid: [y, x] and [ymin, xmin, ymax, xmax], each
 * 0–1000 over the WHOLE page. The crop is the box plus a margin (labels often sit just
 * outside the drawn axes), clamped to the page.
 */

export interface CropBox {
    /** Fractions of the page, 0–1. */
    x0: number; y0: number; w: number; h: number;
}

export const CROP_MARGIN = 0.04;

export function cropOf(box: number[] | null | undefined, margin = CROP_MARGIN): CropBox | null {
    if (!box || box.length !== 4) return null;
    const [ymin, xmin, ymax, xmax] = box.map((v) => Math.max(0, Math.min(1000, v)) / 1000);
    if (!(ymax > ymin && xmax > xmin)) return null;
    const x0 = Math.max(0, xmin - margin);
    const y0 = Math.max(0, ymin - margin);
    const x1 = Math.min(1, xmax + margin);
    const y1 = Math.min(1, ymax + margin);
    return { x0, y0, w: x1 - x0, h: y1 - y0 };
}

/** CSS for the page image inside a crop container whose aspect ratio is `cropAspect`. */
export function imageStyle(crop: CropBox): { width: string; left: string; top: string } {
    return {
        width: `${100 / crop.w}%`,
        left: `${(-crop.x0 / crop.w) * 100}%`,
        top: `${(-crop.y0 / crop.h) * 100}%`,
    };
}

/** width / height of the crop, given the page's own pixel aspect (naturalWidth/naturalHeight). */
export function cropAspect(crop: CropBox, pageAspect: number): number {
    return (crop.w / crop.h) * pageAspect;
}

/** A chip's position inside the crop, in percent; null when its point falls outside it. */
export function chipPosition(point: number[] | null | undefined, crop: CropBox): { left: number; top: number } | null {
    if (!point || point.length !== 2) return null;
    const left = ((point[1] / 1000 - crop.x0) / crop.w) * 100;
    const top = ((point[0] / 1000 - crop.y0) / crop.h) * 100;
    if (left < 0 || left > 100 || top < 0 || top > 100) return null;
    return { left, top };
}
