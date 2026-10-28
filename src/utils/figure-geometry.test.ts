import { describe, expect, it } from 'vitest';

import { chipPosition, cropAspect, cropOf, imageStyle } from './figure-geometry';

describe('figure geometry — chips stay on their marks at any width', () => {
    const crop = cropOf([200, 100, 600, 900], 0)!;

    it('cuts the box as fractions of the page', () => {
        expect(crop.x0).toBeCloseTo(0.1);
        expect(crop.y0).toBeCloseTo(0.2);
        expect(crop.w).toBeCloseTo(0.8);
        expect(crop.h).toBeCloseTo(0.4);
    });

    it('adds a margin, clamped to the page', () => {
        const c = cropOf([0, 0, 500, 1000])!;
        expect(c.x0).toBe(0);
        expect(c.y0).toBe(0);
        expect(c.w).toBe(1);
        expect(c.h).toBeCloseTo(0.54);
    });

    it('refuses a box that is not a box', () => {
        expect(cropOf(null)).toBeNull();
        expect(cropOf([1, 2, 3])).toBeNull();
        expect(cropOf([500, 500, 400, 600])).toBeNull();
    });

    it('a point at the box corner is the crop corner', () => {
        const near = (p: { left: number; top: number } | null, left: number, top: number) => {
            expect(p!.left).toBeCloseTo(left);
            expect(p!.top).toBeCloseTo(top);
        };
        near(chipPosition([200, 100], crop), 0, 0);
        near(chipPosition([600, 900], crop), 100, 100);
        near(chipPosition([400, 500], crop), 50, 50);
    });

    it('a point outside the crop has no chip (it is never pinned to the edge)', () => {
        expect(chipPosition([900, 500], crop)).toBeNull();
        expect(chipPosition(null, crop)).toBeNull();
    });

    it('the image is scaled and shifted so the crop fills the container', () => {
        const st = imageStyle(crop);
        expect(parseFloat(st.width)).toBeCloseTo(125);
        expect(parseFloat(st.left)).toBeCloseTo(-12.5);
        expect(parseFloat(st.top)).toBeCloseTo(-50);
        expect(cropAspect(crop, 1203 / 1691)).toBeCloseTo((0.8 / 0.4) * (1203 / 1691));
    });
});
