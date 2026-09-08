'use client';

/**
 * The transcription answer editor — ported from v0.5's TranscribedTextDisplay
 * (the backdrop-overlay technique: highlighted per-line divs BEHIND a
 * transparent textarea), rebuilt on the current architecture.
 *
 * RTL/bidi mechanism (plan §7, ADJUDICATED by the named Playwright test
 * `rtl-bidi-code-comment-rendering`): the editor is a pure `dir={dir}` island
 * inside the RTL page — and NOTHING more. The plan's original proposal added
 * `unicode-bidi: plaintext` per backdrop line; the test measured it doing the
 * OPPOSITE of its intent: plaintext resolves paragraph direction from the
 * first strong character, so a Hebrew-initial comment line (`// תכונות`)
 * became RTL-base and the `//` migrated to the RIGHT of the Hebrew (x≈590 vs
 * 559). Under plain dir={dir} the paragraph stays LTR — `//` stays left,
 * punctuation stays put — which is the correct rendering for code and what
 * the v0.5 screenshot showed. The ruled test assertions are the spec; the
 * mechanism serves them.
 *
 * Subject-agnostic by design (§3.3): plain monospace text, no language-aware
 * rendering — there is no syntax highlighting to leak.
 */

import { AlertTriangle } from 'lucide-react';
import { useCallback, useRef } from 'react';

import type { ReviewLineFlag } from '@/utils/review-flags';
import { linesForReviewCount } from '@/utils/hebrew-plural';

const LINE_HEIGHT_PX = 20;

export function TranscribedTextEditor({
    value,
    onChange,
    readOnly = false,
    lineFlags = [],
    placeholder = 'תמלול ריק — אפשר להקליד כאן',
    autoFocus = false,
    dir = 'ltr',
}: {
    value: string;
    onChange: (newText: string) => void;
    readOnly?: boolean;
    lineFlags?: ReviewLineFlag[];
    /**
     * Text direction of the island (multisubject Phase 3b, 2026-09-08): decided by
     * the rubric's SUBJECT upstream — `rtl` for mathematics (Hebrew prose with
     * linear notation), `ltr` otherwise. The default keeps every CS surface and the
     * bidi guard byte-identical. Still a pure `dir` island: `unicode-bidi: plaintext`
     * stays falsified (see the header).
     */
    // ALPHA-GAP A-2 (D-1): monospace + raw linear text for mathematics; alpha adds a math renderer (KaTeX).
    dir?: 'ltr' | 'rtl';
    /** R2: marked empty-answer cards pass the §3.2 guidance placeholder. */
    placeholder?: string;
    /**
     * Focus on mount. Set ONLY when the teacher switched this answer out of the
     * rendered table view — she clicked to edit, so the caret belongs here (and
     * a focused textarea is what makes the R3 keymap treat her typing as typing
     * rather than as navigation).
     */
    autoFocus?: boolean;
}) {
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const backdropRef = useRef<HTMLDivElement>(null);

    const hasUncertain = value.includes('[?]');
    const lineCount = value.split('\n').length;
    const minHeight = Math.max(160, lineCount * LINE_HEIGHT_PX + 40);
    const flaggedLines = new Map(lineFlags.map((f) => [f.line, f.reason]));

    const handleScroll = useCallback(() => {
        if (textareaRef.current && backdropRef.current) {
            backdropRef.current.scrollTop = textareaRef.current.scrollTop;
            backdropRef.current.scrollLeft = textareaRef.current.scrollLeft;
        }
    }, []);

    // No flags → the simple textarea path.
    if (lineFlags.length === 0) {
        return (
            <div className="relative">
                <textarea
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    readOnly={readOnly}
                    className={`w-full p-3 font-mono text-sm border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 resize-y ${
                        hasUncertain
                            ? 'bg-red-50/30 border-red-200 focus:border-red-300'
                            : 'bg-surface-50 border-surface-300'
                    } ${readOnly ? 'cursor-not-allowed opacity-70' : ''}`}
                    dir={dir}
                    style={{ minHeight: `${minHeight}px`, whiteSpace: 'pre-wrap' }}
                    placeholder={placeholder}
                    data-testid="transcription-editor"
                    autoFocus={autoFocus}
                />
                {hasUncertain && (
                    <div className="absolute bottom-2 left-2 flex items-center gap-1 px-2 py-1 bg-red-100 text-red-700 rounded text-xs font-medium">
                        <AlertTriangle size={12} />
                        מכיל תווים לא ברורים [?]
                    </div>
                )}
            </div>
        );
    }

    // Flagged path: highlighted backdrop behind a transparent textarea.
    return (
        <div className="relative">
            <div className="flex items-center gap-2 text-amber-700 text-sm mb-2" dir="rtl">
                <AlertTriangle size={16} />
                <span className="font-medium">{linesForReviewCount(lineFlags.length)}</span>
                <span className="text-xs text-gray-500">(מעבר עם העכבר מציג את הסיבה)</span>
            </div>

            <div
                className="relative border border-surface-300 rounded-lg overflow-hidden bg-white"
                style={{ minHeight: `${minHeight}px` }}
            >
                {/* Backdrop: per-line highlights (behind the textarea). */}
                <div
                    ref={backdropRef}
                    className="absolute inset-0 p-3 font-mono text-sm overflow-hidden pointer-events-none"
                    style={{ whiteSpace: 'pre-wrap', wordWrap: 'break-word' }}
                    dir={dir}
                    aria-hidden="true"
                >
                    {value.split('\n').map((line, idx) => {
                        const reason = flaggedLines.get(idx + 1);
                        return (
                            <div
                                key={idx}
                                className={`relative group ${reason ? 'bg-red-200/70 -mx-3 px-3 border-l-4 border-red-500' : ''}`}
                                style={{ minHeight: `${LINE_HEIGHT_PX}px` }}
                            >
                                <span style={{ visibility: 'hidden' }}>{line || ' '}</span>
                                {reason && (
                                    <div
                                        className="absolute left-0 top-0 -translate-x-full -ml-2 bg-red-600 text-white text-xs px-2 py-1 rounded shadow-lg z-30 whitespace-nowrap max-w-xs pointer-events-auto opacity-0 group-hover:opacity-100 transition-opacity"
                                        dir="rtl"
                                    >
                                        {reason}
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>

                {/* Transparent textarea captures input (on top). */}
                <textarea
                    ref={textareaRef}
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    onScroll={handleScroll}
                    readOnly={readOnly}
                    className={`relative w-full h-full p-3 font-mono text-sm bg-transparent resize-none focus:outline-none focus:ring-2 focus:ring-primary-500 rounded-lg ${readOnly ? 'cursor-not-allowed' : ''}`}
                    dir={dir}
                    style={{
                        minHeight: `${minHeight}px`,
                        whiteSpace: 'pre-wrap',
                        lineHeight: `${LINE_HEIGHT_PX}px`,
                        caretColor: '#1a1a1a',
                    }}
                    placeholder={placeholder}
                    data-testid="transcription-editor"
                    autoFocus={autoFocus}
                />
            </div>
        </div>
    );
}
