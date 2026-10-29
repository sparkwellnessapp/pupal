'use client';

/**
 * A drawing of the teacher's rubric, shown as HER drawing (2026-10-29): the crop of the box
 * the math rubric reader located, fetched from the server (which cuts it from the stored
 * source document), with the reader's description beneath it — the description is what the
 * grader reads, so she sees both and can tell when the reading is wrong.
 *
 * WHERE THE DOCUMENT IS comes from one provider, set by the page that knows: an extraction
 * still under review (its job), or a saved rubric. Outside a provider, or when the crop cannot
 * be had (a rubric typed by hand, an old draft), the description renders alone — never a
 * broken image, never a redraw.
 */
import { createContext, useContext, useEffect, useState } from 'react';
import { ImageIcon } from 'lucide-react';

import { MathInline } from '@/components/math/MathNotationContext';
import { getExtractionJobFigure, getRubricFigure } from '@/lib/api';
import { boxParam, parseFigureLine, type RubricFigureRef } from '@/utils/rubric-figures';

export type RubricFigureSource = { kind: 'job'; id: string } | { kind: 'rubric'; id: string } | null;

export const RubricFigureSourceContext = createContext<RubricFigureSource>(null);

const cache = new Map<string, Promise<string | null>>();

function loadFigure(source: Exclude<RubricFigureSource, null>, ref: RubricFigureRef): Promise<string | null> {
    const key = `${source.kind}:${source.id}:${ref.page}:${boxParam(ref.box)}`;
    let hit = cache.get(key);
    if (!hit) {
        const call = source.kind === 'job'
            ? getExtractionJobFigure(source.id, ref.page, boxParam(ref.box))
            : getRubricFigure(source.id, ref.page, boxParam(ref.box));
        hit = call.then((r) => `data:${r.content_type};base64,${r.image_base64}`).catch(() => null);
        cache.set(key, hit);
    }
    return hit;
}

function FigureImage({ refd }: { refd: RubricFigureRef }) {
    const source = useContext(RubricFigureSourceContext);
    const [src, setSrc] = useState<string | null | undefined>(source ? undefined : null);
    useEffect(() => {
        if (!source) return;
        let alive = true;
        loadFigure(source, refd).then((s) => { if (alive) setSrc(s); });
        return () => { alive = false; };
    }, [source, refd]);
    if (src === null) return null;
    if (src === undefined) {
        return <div className="h-40 w-full animate-pulse rounded-md bg-surface-100" data-figure-loading />;
    }
    return (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt={refd.description} data-figure-image
            className="max-h-80 max-w-full rounded-md border border-surface-200 bg-white object-contain" />
    );
}

/** One `[איור …]` line: the drawing (when located) and its description. */
export function RubricFigureLine({ line }: { line: string }) {
    const parsed = parseFigureLine(line);
    if (!parsed) return null;
    return (
        <figure data-rubric-figure={parsed.page ?? 'described'} dir="rtl"
            className="my-3 flex flex-col items-start gap-1.5">
            {parsed.page !== null ? <FigureImage refd={parsed as RubricFigureRef} /> : null}
            <figcaption className="flex items-start gap-1.5 text-doc-meta text-surface-500">
                <ImageIcon size={14} className="mt-0.5 flex-shrink-0" aria-hidden />
                <span><MathInline text={parsed.description} /></span>
            </figcaption>
        </figure>
    );
}

export function isFigureLine(line: string): boolean {
    return parseFigureLine(line) !== null;
}

/** Rubric text that may hold drawing lines (a question's text on the grade-review surface). */
export function RubricText({ text }: { text: string }) {
    const lines = text.split('\n');
    return (
        <>
            {lines.map((line, i) => isFigureLine(line)
                ? <RubricFigureLine key={i} line={line} />
                : <span key={i}>{i > 0 && !isFigureLine(lines[i - 1]) ? <br /> : null}<MathInline text={line} /></span>)}
        </>
    );
}
