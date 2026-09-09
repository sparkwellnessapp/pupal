import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import config from '../../tailwind.config';

/**
 * The F0 token gate's *structural* half (`npm run check:tokens` is the lint
 * half). Two claims are made in the config's comments, and a comment cannot
 * defend itself:
 *
 *   1. The grade-review palette does NOT re-declare teal, because the mockup's
 *      teal ramp is byte-identical to `primary` (§0.4 — one palette, one
 *      place). If someone later pastes `teal: '#0D9488'` under `grade`, the
 *      two copies drift the first time the brand is re-themed and half the
 *      surface follows the old one.
 *   2. `grade.canvas` is the SAME cream as globals.css `--background`, which
 *      is what makes the module read as part of the app rather than a page
 *      pasted onto it. That is the "tokens reviewed against the home screen"
 *      gate, as an assertion instead of a memory.
 */

const colors = (config.theme?.extend?.colors ?? {}) as Record<string, Record<string, string>>;
const grade = colors.grade ?? {};
const primary = colors.primary ?? {};

const HERE = path.dirname(fileURLToPath(import.meta.url));
const GLOBALS = readFileSync(path.resolve(HERE, '../app/globals.css'), 'utf-8');

const norm = (hex: string) => hex.toLowerCase();

describe('grade-review tokens', () => {
    it('exists as its own scope, like `batch` before it', () => {
        expect(Object.keys(grade).length).toBeGreaterThan(10);
    });

    it('re-declares NOTHING that the primary ramp already carries', () => {
        const primaryValues = new Set(Object.values(primary).map(norm));
        const duplicated = Object.entries(grade)
            .filter(([, value]) => primaryValues.has(norm(value)))
            .map(([name, value]) => `grade.${name} = ${value}`);
        expect(duplicated).toEqual([]);
    });

    it('leaves teal to `primary` — the mockup ramp IS the app ramp', () => {
        expect(norm(primary['600'])).toBe('#0d9488');   // mockup --teal
        expect(norm(primary['700'])).toBe('#0f766e');   // mockup --teal-700
        expect(norm(primary['100'])).toBe('#ccfbf1');   // mockup --teal-100
        expect(norm(primary['50'])).toBe('#f0fdfa');    // mockup --teal-50
        expect(Object.keys(grade).filter((k) => k.startsWith('teal')))
            .toEqual(['teal-line']);                    // the one value the ramp lacks
    });

    it('shares the home screen canvas', () => {
        const background = /--background:\s*(#[0-9A-Fa-f]{6})/.exec(GLOBALS)?.[1];
        expect(background).toBeDefined();
        expect(norm(grade.canvas)).toBe(norm(background as string));
    });

    it('applies Assistant app-wide from ONE decision, in both homes (OD-F1)', () => {
        // Ruled 2026-08-31. `body` and tailwind's `sans` must agree: most of
        // the app renders through `font-sans`, so setting only one leaves half
        // the product on the old face and nobody notices until a screenshot.
        expect(GLOBALS).toContain('family=Assistant');
        expect(/body\s*\{[^}]*font-family:\s*'Assistant'/.test(GLOBALS)).toBe(true);
        const fonts = (config.theme?.extend?.fontFamily ?? {}) as Record<string, string[]>;
        expect(fonts.sans[0]).toBe('Assistant');
        expect(fonts.assistant[0]).toBe('Assistant');
    });

    it('keeps Caveat loaded and used by the stamp alone', () => {
        expect(GLOBALS).toContain('family=Caveat');
        const fonts = (config.theme?.extend?.fontFamily ?? {}) as Record<string, string[]>;
        expect(fonts.hand[0]).toBe('Caveat');
    });

    it('keeps the teacher red for the teacher, and only her', () => {
        // §0.3's ink grammar: grey proposes, red decided. `batch.red` is a
        // failure colour and a different thing; they must not converge.
        expect(norm(grade.red)).toBe('#c8102e');
        expect(norm(colors.batch.red)).not.toBe(norm(grade.red));
    });
});
