/**
 * A drawing in a teacher's rubric — the marker the math rubric reader writes, mirrored from
 * `backend/app/services/docx_v3/rubric_figures.py` (one grammar, two languages):
 *
 *     [איור p<page> <ymin>,<xmin>,<ymax>,<xmax>: <description>]   located: her drawing is shown
 *     [איור: <description>]                                        not located: described only
 *
 * The box is 0–1000 of the source image `page` (1-based). The surface asks the server for the
 * crop and never redraws a figure from the description.
 */
export interface RubricFigureRef {
    page: number;
    box: [number, number, number, number];
    description: string;
}

const LOCATED = /^\s*\[איור p(\d+) (\d+),(\d+),(\d+),(\d+): (.*)\]\s*$/;
const DESCRIBED = /^\s*\[איור:\s*(.*)\]\s*$/;

/** The figure a whole line is, or null. A line with prose around the marker is not a figure line. */
export function parseFigureLine(line: string): RubricFigureRef | { description: string; page: null } | null {
    const m = LOCATED.exec(line);
    if (m) {
        const [y0, x0, y1, x1] = [m[2], m[3], m[4], m[5]].map(Number);
        return { page: Number(m[1]), box: [y0, x0, y1, x1], description: m[6] };
    }
    const d = DESCRIBED.exec(line);
    return d ? { description: d[1], page: null } : null;
}

export function boxParam(box: [number, number, number, number]): string {
    return box.join(',');
}
