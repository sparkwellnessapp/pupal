'use client';

import { useState } from 'react';
import { Info, Table, FileCode, Tag } from 'lucide-react';

interface RubricFormatGuideProps {
    className?: string;
}

/**
 * An interactive info icon that displays rubric formatting best practices.
 * Helps teachers understand how to structure their rubric PDFs for optimal extraction.
 */
export function RubricFormatGuide({ className = '' }: RubricFormatGuideProps) {
    const [isOpen, setIsOpen] = useState(false);

    return (
        <div
            className={`relative ${className}`}
            onMouseEnter={() => setIsOpen(true)}
            onMouseLeave={() => setIsOpen(false)}
        >
            {/* Info Icon Trigger */}
            <div
                className="flex items-center gap-1.5 text-gray-500 hover:text-primary-600 transition-colors text-sm group cursor-help"
                aria-label="מידע על מבנה מחוון"
            >
                <Info size={18} className="group-hover:scale-110 transition-transform" />
                <span className="text-xs opacity-75 group-hover:opacity-100">איך לבנות מחוון?</span>
            </div>

            {/* Expandable Guide Panel - using flex centering for true center */}
            {isOpen && (
                <div
                    className="fixed inset-0 z-[100] flex justify-center pt-[120px] pointer-events-none"
                    onMouseEnter={() => setIsOpen(true)}
                    onMouseLeave={() => setIsOpen(false)}
                >
                    <div
                        className="bg-white rounded-xl shadow-xl border border-surface-200 p-4 w-[380px] h-fit pointer-events-auto animate-fade-in"
                    >
                        {/* Header */}
                        <div className="mb-3">
                            <h3 className="font-semibold text-gray-800 text-sm">טיפים לבניית מחוון</h3>
                        </div>

                        {/* Tips List */}
                        <div className="space-y-3 text-sm">
                            {/* Tip 1: Table Format */}
                            <div className="flex gap-3">
                                <div className="flex-shrink-0 w-8 h-8 bg-primary-50 rounded-lg flex items-center justify-center">
                                    <Table size={16} className="text-primary-600" />
                                </div>
                                <div>
                                    <p className="font-medium text-gray-700">קריטריונים בטבלה</p>
                                    <p className="text-gray-500 text-xs mt-0.5">
                                        סדרי את הקריטריונים לבדיקה והנקודות שלהן בטבלה עם עמודות ברורות
                                    </p>
                                </div>
                            </div>

                            {/* Tip 2: Example Solution */}
                            <div className="flex gap-3">
                                <div className="flex-shrink-0 w-8 h-8 bg-emerald-50 rounded-lg flex items-center justify-center">
                                    <FileCode size={16} className="text-emerald-600" />
                                </div>
                                <div>
                                    <p className="font-medium text-gray-700">אופציונלי: הוספת פתרון לדוגמה</p>
                                    <p className="text-gray-500 text-xs mt-0.5">
                                        במידה ויש פתרון דוגמה לשאלה, הוסיפי כותרת <span className="font-semibold text-emerald-600">&quot;פתרון לדוגמה&quot;</span> לפני הפתרון
                                    </p>
                                </div>
                            </div>

                            {/* Tip 3: Clear Labels */}
                            <div className="flex gap-3">
                                <div className="flex-shrink-0 w-8 h-8 bg-amber-50 rounded-lg flex items-center justify-center">
                                    <Tag size={16} className="text-amber-600" />
                                </div>
                                <div>
                                    <p className="font-medium text-gray-700">תיוג ברור</p>
                                    <p className="text-gray-500 text-xs mt-0.5">
                                        סמני שאלות עם &quot;שאלה 1&quot;, &quot;שאלה 2&quot; וכו&apos;
                                    </p>
                                </div>
                            </div>
                        </div>

                        {/* Example Visual */}
                        <div className="mt-4 p-3 bg-surface-50 rounded-lg border border-surface-200">
                            <p className="text-xs text-gray-500 mb-2 font-medium">דוגמה למבנה טבלה:</p>
                            <div className="bg-white rounded border border-surface-200 overflow-hidden text-xs">
                                <table className="w-full">
                                    <thead className="bg-surface-100">
                                        <tr>
                                            <th className="text-right p-1.5 border-b border-surface-200 font-medium">קריטריון</th>
                                            <th className="text-center p-1.5 border-b border-surface-200 font-medium w-16">נקודות</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <tr>
                                            <td className="p-1.5 border-b border-surface-100 text-gray-600">שימוש נכון בלולאה</td>
                                            <td className="text-center p-1.5 border-b border-surface-100 font-medium text-primary-600">3</td>
                                        </tr>
                                        <tr>
                                            <td className="p-1.5 text-gray-600">חתימת הפעולה</td>
                                            <td className="text-center p-1.5 font-medium text-primary-600">2</td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
