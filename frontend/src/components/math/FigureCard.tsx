'use client';

/**
 * One drawing at the transcription gate: the STUDENT'S OWN INK, with Vivi's reading pinned
 * onto it (MATH_RENDERING_PLAN §3, §5; owner ruling OD-M2 — "nothing he drew is lost or
 * changed").
 *
 * Nothing here is drawn that he did not draw. The picture is a crop of the scan; each
 * reading is a small chip on the mark it came from, and the same readings are listed
 * beside it, each editable. A misread sits ON the mark it misreads, so she sees it without
 * comparing two pictures. Hovering a row lights its chip, and the reverse.
 *
 * Editing (when `onChange` is given): change a value (MathLive, never LaTeX), delete a
 * reading, flip «בצבע אחר», or add one Vivi missed — the measured failure is an
 * UNLABELLED drawn line the reader skipped while calling the figure complete. Every edit
 * hands up a whole new Figure; the parent persists it with the answer.
 */
import { useState } from 'react';

import { MathSpanEditor } from '@/components/math/MathSpanEditor';
import { MathText } from '@/components/math/MathText';
import {
    FIG_ADD, FIG_DELETE, FIG_EDIT, FIG_INK_OTHER, FIG_KIND_HE, FIG_NO_CROP, FIG_NO_FEATURES,
    FIG_SOURCE_TEACHER, FIG_TITLE, FIG_UNCERTAIN,
} from '@/copy/math';
import type { Figure, FigureFeature, FigureFeatureKind } from '@/types/transcription';
import { chipPosition, cropAspect, cropOf, imageStyle } from '@/utils/figure-geometry';

const ADDABLE: FigureFeatureKind[] = [
    'vertical_asymptote', 'horizontal_asymptote', 'minimum', 'maximum', 'x_intercept',
    'y_intercept', 'point', 'side_label', 'angle_label', 'other_label',
];

export function FigureCard({ figure, pageImage, onChange }: {
    figure: Figure;
    /** The page's image (a data/blob URL or base64 PNG/JPEG data URL); null while loading. */
    pageImage: string | null;
    onChange?: (next: Figure) => void;
}) {
    const [lit, setLit] = useState<number | null>(null);
    const [editing, setEditing] = useState<number | 'new' | null>(null);
    const [newKind, setNewKind] = useState<FigureFeatureKind>('vertical_asymptote');
    const [aspect, setAspect] = useState<number | null>(null);
    const crop = cropOf(figure.box_2d);
    const editable = !!onChange;

    const setFeatures = (features: FigureFeature[]) => onChange?.({ ...figure, features });
    const replaceAt = (i: number, f: FigureFeature) =>
        setFeatures(figure.features.map((g, j) => (j === i ? f : g)));

    return (
        <div data-testid="figure-card" data-figure-no={figure.figure_no} data-page={figure.page_number}
            className="mt-3 rounded-lg border border-surface-300 bg-white p-3">
            <div dir="rtl" className="mb-2 text-xs font-medium text-gray-600">{FIG_TITLE(figure.figure_no, figure.page_number)}</div>
            <div className="flex flex-col gap-3 md:flex-row">
                <div className="md:w-1/2">
                    {crop && pageImage ? (
                        <div
                            className="relative w-full overflow-hidden rounded border border-surface-200 bg-surface-50"
                            style={{ aspectRatio: aspect ? `${cropAspect(crop, aspect)}` : '4 / 3' }}
                        >
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img
                                src={pageImage}
                                alt=""
                                onLoad={(e) => {
                                    const im = e.currentTarget;
                                    if (im.naturalHeight) setAspect(im.naturalWidth / im.naturalHeight);
                                }}
                                className="absolute max-w-none select-none"
                                style={imageStyle(crop)}
                            />
                            {figure.features.map((f, i) => {
                                const at = chipPosition(f.point, crop);
                                if (!at) return null;
                                return (
                                    <span
                                        key={i}
                                        data-figure-chip={i}
                                        onMouseEnter={() => setLit(i)}
                                        onMouseLeave={() => setLit(null)}
                                        className={[
                                            'absolute -translate-x-1/2 -translate-y-1/2 rounded-full border-2',
                                            lit === i ? 'h-5 w-5 border-primary-600 bg-primary-200/60'
                                                : 'h-3.5 w-3.5 border-primary-600 bg-white/60',
                                        ].join(' ')}
                                        style={{ left: `${at.left}%`, top: `${at.top}%` }}
                                        title={FIG_KIND_HE[f.kind] ?? f.kind}
                                    />
                                );
                            })}
                        </div>
                    ) : (
                        <div dir="rtl" className="rounded border border-dashed border-surface-300 p-3 text-xs text-gray-500">
                            {FIG_NO_CROP}
                        </div>
                    )}
                </div>
                <ul dir="rtl" className="space-y-1 md:w-1/2" data-testid="figure-features">
                    {figure.features.length === 0 && <li className="text-xs text-gray-500">{FIG_NO_FEATURES}</li>}
                    {figure.features.map((f, i) => (
                        <li
                            key={i}
                            data-figure-feature={i}
                            onMouseEnter={() => setLit(i)}
                            onMouseLeave={() => setLit(null)}
                            className={`flex flex-wrap items-center gap-1.5 rounded px-1.5 py-1 text-sm ${lit === i ? 'bg-primary-50' : ''}`}
                        >
                            <span className="text-gray-600">{FIG_KIND_HE[f.kind] ?? f.kind}:</span>
                            {editing === i ? (
                                <MathSpanEditor
                                    body={f.as_written}
                                    onSave={(latex) => { replaceAt(i, { ...f, as_written: latex, source: 'teacher' }); setEditing(null); }}
                                    onCancel={() => setEditing(null)}
                                />
                            ) : f.as_written ? (
                                <MathText text={`\\(${f.as_written}\\)`} />
                            ) : <span className="text-xs text-gray-400">—</span>}
                            {f.uncertain && <span className="rounded bg-amber-100 px-1 text-[11px] text-amber-800">{FIG_UNCERTAIN}</span>}
                            {f.ink === 'other' && <span className="rounded bg-pink-100 px-1 text-[11px] text-pink-800">{FIG_INK_OTHER}</span>}
                            {f.source === 'teacher' && <span className="rounded bg-primary-100 px-1 text-[11px] text-primary-800">{FIG_SOURCE_TEACHER}</span>}
                            {editable && editing !== i && (
                                <span className="ms-auto flex gap-1.5 text-xs">
                                    <button type="button" className="text-primary-700 underline" onClick={() => setEditing(i)}>{FIG_EDIT}</button>
                                    <button type="button" className="text-gray-600 underline"
                                        onClick={() => replaceAt(i, { ...f, ink: f.ink === 'other' ? 'primary' : 'other', source: 'teacher' })}>
                                        {FIG_INK_OTHER}
                                    </button>
                                    <button type="button" data-figure-delete={i} className="text-red-700 underline"
                                        onClick={() => setFeatures(figure.features.filter((_, j) => j !== i))}>{FIG_DELETE}</button>
                                </span>
                            )}
                        </li>
                    ))}
                    {editable && (editing === 'new' ? (
                        <li className="flex flex-wrap items-center gap-1.5 px-1.5 py-1 text-sm">
                            <select value={newKind} onChange={(e) => setNewKind(e.target.value as FigureFeatureKind)}
                                className="rounded border border-surface-300 px-1 py-0.5 text-xs">
                                {ADDABLE.map((k) => <option key={k} value={k}>{FIG_KIND_HE[k]}</option>)}
                            </select>
                            <MathSpanEditor
                                body=""
                                saveUnchanged
                                onSave={(latex) => {
                                    setFeatures([...figure.features, {
                                        kind: newKind, as_written: latex, point: null, ink: 'primary',
                                        uncertain: false, source: 'teacher',
                                    }]);
                                    setEditing(null);
                                }}
                                onCancel={() => setEditing(null)}
                            />
                        </li>
                    ) : (
                        <li>
                            <button type="button" data-testid="figure-add" className="text-xs text-primary-700 underline"
                                onClick={() => setEditing('new')}>{FIG_ADD}</button>
                        </li>
                    ))}
                </ul>
            </div>
        </div>
    );
}
