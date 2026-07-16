'use client';

/**
 * ExampleSolutionEditor
 *
 * Collapsible per-question panel for editing the `example_solution` field.
 *
 * - Renders an "הוסף פתרון לדוגמה ＋" button when value is null/undefined.
 * - Renders a resizable textarea + "הסר" button when value exists.
 * - onChange(null) signals removal; onChange(text) signals update.
 *
 * Uses native <details>/<summary> for collapse — zero extra state needed.
 */

import { BookOpen, X } from 'lucide-react';
import { MarkdownTextRenderer } from '@/components/MarkdownTextRenderer';

interface ExampleSolutionEditorProps {
    /** Current example solution text, or null/undefined if not set */
    value: string | null | undefined;
    /** Called with new text on change, or null when the teacher removes it */
    onChange: (newValue: string | null) => void;
}

export function ExampleSolutionEditor({ value, onChange }: ExampleSolutionEditorProps) {
    const hasValue = value !== null && value !== undefined;

    if (!hasValue) {
        return (
            <button
                onClick={() => onChange('')}
                className="mt-3 flex items-center gap-1.5 text-xs text-primary-500 hover:text-primary-700 transition-colors"
                dir="rtl"
            >
                <BookOpen size={13} />
                <span>הוסף פתרון לדוגמה</span>
            </button>
        );
    }

    return (
        <details className="mt-3 group" dir="rtl" open>
            <summary className="flex items-center gap-2 cursor-pointer list-none select-none">
                <BookOpen size={14} className="text-primary-500 flex-shrink-0" />
                <span className="text-xs font-semibold text-gray-600">פתרון לדוגמה</span>
                <span className="text-xs text-gray-400 group-open:hidden">(לחץ להצגה)</span>
                <span className="text-xs text-gray-400 hidden group-open:inline">(לחץ להסתרה)</span>
                <div className="flex-1" />
                <button
                    onClick={(e) => {
                        e.preventDefault(); // don't toggle <details>
                        onChange(null);
                    }}
                    title="הסר פתרון לדוגמה"
                    className="text-gray-300 hover:text-red-400 transition-colors p-0.5 rounded"
                >
                    <X size={13} />
                </button>
            </summary>

            <MarkdownTextRenderer
                value={value ?? ''}
                onChange={(val) => onChange(val)}
                placeholder="הקלד את הפתרון לדוגמה כאן..."
                textareaClassName="font-mono"
                minHeight="6rem"
                className="mt-2"
            />
        </details>
    );
}
