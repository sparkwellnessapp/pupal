'use client';

/**
 * RubricMetadataEditor
 *
 * Compact, collapsible panel at the top of RubricEditor that lets teachers
 * edit rubric-level metadata: name, subject, programming language, and total
 * points. Changing total_points triggers a full proportional cascade through
 * all questions and their criteria via the onTotalPointsChange callback.
 */

import { useState } from 'react';
import { ChevronDown, ChevronUp, Settings2 } from 'lucide-react';

export interface RubricMetadata {
    rubric_name: string;
    subject: string;
    programming_language: string;
    total_points: number;
}

interface RubricMetadataEditorProps {
    rubricName: string;
    subject: string;
    programmingLanguage: string;
    totalPoints: number;
    /** Called when any metadata field except total_points changes */
    onChange: (patch: Partial<Omit<RubricMetadata, 'total_points'>>) => void;
    /** Called on blur after the teacher changes total_points */
    onTotalPointsChange: (newTotal: number) => void;
    /** Highlights the name field with an error border */
    hasNameError?: boolean;
}

export function RubricMetadataEditor({
    rubricName,
    subject,
    programmingLanguage,
    totalPoints,
    onChange,
    onTotalPointsChange,
    hasNameError = false,
}: RubricMetadataEditorProps) {
    const [isOpen, setIsOpen] = useState(false);
    // Local draft for the total-points input — committed on blur
    const [draftTotal, setDraftTotal] = useState(String(totalPoints));

    // Sync external totalPoints into the local draft when parent updates it
    // (e.g., after cascade recalculation)
    const displayTotal = isNaN(parseFloat(draftTotal)) ? totalPoints : parseFloat(draftTotal);

    function handleTotalBlur() {
        const parsed = parseFloat(draftTotal);
        if (!isNaN(parsed) && parsed > 0) {
            onTotalPointsChange(parsed);
            setDraftTotal(String(parsed));
        } else {
            // Revert to current value if invalid
            setDraftTotal(String(totalPoints));
        }
    }

    return (
        <div className="mb-4 border border-surface-200 rounded-xl bg-white shadow-sm overflow-hidden">
            {/* Header row — always visible */}
            <button
                onClick={() => setIsOpen(prev => !prev)}
                className="w-full flex items-center justify-between px-4 py-3 text-right hover:bg-surface-50 transition-colors"
                dir="rtl"
            >
                <div className="flex items-center gap-2">
                    <Settings2 size={16} className="text-primary-500" />
                    <span className="text-sm font-semibold text-gray-700">פרטי המחוון</span>
                    <span className="text-xs text-gray-400 font-normal">
                        {rubricName || 'ללא שם'} · {totalPoints} נק׳
                    </span>
                </div>
                {isOpen ? <ChevronUp size={16} className="text-gray-400" /> : <ChevronDown size={16} className="text-gray-400" />}
            </button>

            {/* Collapsible content */}
            {isOpen && (
                <div className="px-4 pb-4 pt-1 grid grid-cols-1 gap-3 border-t border-surface-100" dir="rtl">
                    {/* Rubric name */}
                    <div>
                        <label className="block text-xs font-medium text-gray-500 mb-1">
                            שם המחוון <span className="text-red-500">*</span>
                        </label>
                        <input
                            type="text"
                            value={rubricName}
                            onChange={e => onChange({ rubric_name: e.target.value })}
                            className={`w-full text-sm border rounded-lg px-3 py-2 bg-surface-50 focus:outline-none focus:ring-2 focus:ring-primary-300 text-right ${hasNameError ? 'border-red-400 ring-1 ring-red-300' : 'border-surface-300'}`}
                            placeholder="לדוגמה: מבחן מחצית א׳"
                            dir="rtl"
                        />
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                        {/* Subject */}
                        <div>
                            <label className="block text-xs font-medium text-gray-500 mb-1">נושא</label>
                            <input
                                type="text"
                                value={subject}
                                onChange={e => onChange({ subject: e.target.value })}
                                className="w-full text-sm border border-surface-300 rounded-lg px-3 py-2 bg-surface-50 focus:outline-none focus:ring-2 focus:ring-primary-300 text-right"
                                placeholder="computer_science"
                                dir="rtl"
                            />
                        </div>

                        {/* Programming language */}
                        <div>
                            <label className="block text-xs font-medium text-gray-500 mb-1">שפת תכנות</label>
                            <input
                                type="text"
                                value={programmingLanguage}
                                onChange={e => onChange({ programming_language: e.target.value })}
                                className="w-full text-sm border border-surface-300 rounded-lg px-3 py-2 bg-surface-50 focus:outline-none focus:ring-2 focus:ring-primary-300 text-right"
                                placeholder="Java / Python / ..."
                                dir="rtl"
                            />
                        </div>
                    </div>

                    {/* Total points */}
                    <div>
                        <label className="block text-xs font-medium text-gray-500 mb-1">
                            סה״כ נקודות
                            <span className="mr-1 text-gray-400 font-normal">(שינוי יחלק מחדש לפי יחס)</span>
                        </label>
                        <input
                            type="number"
                            value={draftTotal}
                            onChange={e => setDraftTotal(e.target.value)}
                            onBlur={handleTotalBlur}
                            min={1}
                            step={0.5}
                            className="w-32 text-sm border border-surface-300 rounded-lg px-3 py-2 bg-surface-50 focus:outline-none focus:ring-2 focus:ring-primary-300 text-center font-semibold"
                        />
                    </div>
                </div>
            )}
        </div>
    );
}
