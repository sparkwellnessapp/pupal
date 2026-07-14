'use client';

import { useEffect, useState } from 'react';

interface PdfProcessingPageProps {
    filename: string;
    // Called when PDF processing is complete and pages are ready
    onPagesReady?: () => void;
    // Called on error
    onError: (message: string) => void;
    // Progress info (optional)
    progress?: {
        currentPage?: number;
        totalPages?: number;
    };
}

// Elapsed-time-staged status messages for the two-phase + trust pipeline.
// Timings mirror the measured pipeline (render+upload → P1+readers concurrent
// → segmentation): honest narration, not fake precision. A full exam takes
// ~1–3 minutes.
const STAGES: { at: number; title: string; sub: string }[] = [
    { at: 0, title: 'מעבד את הסריקה...', sub: 'טוען את עמודי המבחן' },
    { at: 12, title: 'קורא את כתב היד...', sub: 'תמלול מדויק, עמוד אחר עמוד' },
    { at: 45, title: 'מצליב קריאות...', sub: 'מספר קוראים בלתי תלויים בודקים את התמלול ומסמנים אזורים לבדיקה' },
    { at: 90, title: 'מפריד את התשובות לשאלות...', sub: 'משייך כל קטע קוד לשאלה ולעמוד המקור שלו' },
    { at: 130, title: 'עוד רגע...', sub: 'מכין את התמלול לבדיקה שלך' },
];

/**
 * Intermediate loading page shown while PDF is being processed.
 * 
 * This page displays:
 * - Dual-color loading spinner (turquoise + purple)
 * - "מתמלל כתב יד..." header
 * - "ה-AI קורא את המבחן ומתמלל את התשובות" description
 * - Progress bar (if available)
 * - Filename
 * 
 * Once PDF processing is complete (pages received), calls onPagesReady
 * to trigger navigation to the TranscriptionReviewPage.
 */
export default function PdfProcessingPage({
    filename,
    onPagesReady,
    onError,
    progress,
}: PdfProcessingPageProps) {
    // Calculate progress percentage if available
    const progressPercent = progress?.totalPages && progress?.currentPage
        ? Math.round((progress.currentPage / progress.totalPages) * 100)
        : null;

    // Elapsed-time stage narration + a monotone progress estimate that
    // approaches (never reaches) done — the call is blocking, so this is the
    // only honest signal we can give.
    const [elapsed, setElapsed] = useState(0);
    useEffect(() => {
        const t = setInterval(() => setElapsed(e => e + 1), 1000);
        return () => clearInterval(t);
    }, []);
    const stage = [...STAGES].reverse().find(s => elapsed >= s.at) ?? STAGES[0];
    // ~120s typical: ease toward 95% cap
    const estPercent = Math.min(95, Math.round(100 * (1 - Math.exp(-elapsed / 55))));

    return (
        <div className="min-h-screen bg-gradient-to-br from-surface-50 via-primary-50/20 to-surface-100 flex flex-col">
            {/* Main content - centered */}
            <main className="flex-1 flex items-center justify-center px-6">
                <div className="max-w-md w-full text-center">
                    {/* Gradient loading spinner (turquoise → purple) */}
                    <div className="mb-8">
                        <div className="relative inline-block">
                            <svg
                                className="w-20 h-20 animate-spin"
                                viewBox="0 0 50 50"
                                style={{ animationDuration: '1.2s' }}
                            >
                                {/* Gradient definition */}
                                <defs>
                                    <linearGradient id="spinnerGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                                        <stop offset="0%" stopColor="#14b8a6" />
                                        <stop offset="50%" stopColor="#6366f1" />
                                        <stop offset="100%" stopColor="#a855f7" />
                                    </linearGradient>
                                </defs>
                                {/* Background ring */}
                                <circle
                                    cx="25"
                                    cy="25"
                                    r="20"
                                    fill="none"
                                    stroke="#e5e7eb"
                                    strokeWidth="4"
                                />
                                {/* Gradient arc */}
                                <circle
                                    cx="25"
                                    cy="25"
                                    r="20"
                                    fill="none"
                                    stroke="url(#spinnerGradient)"
                                    strokeWidth="4"
                                    strokeLinecap="round"
                                    strokeDasharray="80 126"
                                    transform="rotate(-90 25 25)"
                                />
                            </svg>
                        </div>
                    </div>

                    {/* Title — staged narration */}
                    <h1 className="text-2xl font-bold text-gray-900 mb-3" dir="rtl">
                        {stage.title}
                    </h1>

                    {/* Description */}
                    <p className="text-gray-500 mb-8" dir="rtl">
                        {stage.sub}
                    </p>

                    {/* Progress bar with turquoise-purple gradient */}
                    <div className="mb-4">
                        <div className="h-2 bg-surface-100 rounded-full overflow-hidden">
                            <div
                                className="h-full bg-gradient-to-r from-primary-400 via-primary-500 to-violet-500 transition-all duration-1000 ease-out"
                                style={{
                                    width: `${progressPercent ?? estPercent}%`,
                                }}
                            />
                        </div>
                    </div>

                    {/* Expectation + filename */}
                    <p className="text-xs text-gray-400 mb-2" dir="rtl">
                        בדיקה יסודית של כל המבחן — אורכת בדרך כלל כדקה־שתיים
                    </p>
                    <p className="text-sm text-gray-400" dir="ltr">
                        {filename}
                    </p>
                </div>
            </main>

            {/* Pulse animation for progress bar when no progress info */}
            <style jsx>{`
        @keyframes pulse-width {
          0%, 100% { width: 40%; }
          50% { width: 70%; }
        }
      `}</style>
        </div>
    );
}


/**
 * Alternative: Inline loading component for use within existing pages
 */
export function PdfProcessingOverlay({
    filename,
    isVisible,
}: {
    filename: string;
    isVisible: boolean;
}) {
    if (!isVisible) return null;

    return (
        <div className="fixed inset-0 z-50 bg-gradient-to-br from-surface-50 via-primary-50/20 to-surface-100 flex items-center justify-center">
            <div className="max-w-md w-full text-center px-6">
                {/* Gradient loading spinner (turquoise → purple) */}
                <div className="mb-8">
                    <div className="relative inline-block">
                        <svg
                            className="w-20 h-20 animate-spin"
                            viewBox="0 0 50 50"
                            style={{ animationDuration: '1.2s' }}
                        >
                            <defs>
                                <linearGradient id="overlaySpinnerGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                                    <stop offset="0%" stopColor="#14b8a6" />
                                    <stop offset="50%" stopColor="#6366f1" />
                                    <stop offset="100%" stopColor="#a855f7" />
                                </linearGradient>
                            </defs>
                            <circle
                                cx="25"
                                cy="25"
                                r="20"
                                fill="none"
                                stroke="#e5e7eb"
                                strokeWidth="4"
                            />
                            <circle
                                cx="25"
                                cy="25"
                                r="20"
                                fill="none"
                                stroke="url(#overlaySpinnerGradient)"
                                strokeWidth="4"
                                strokeLinecap="round"
                                strokeDasharray="80 126"
                                transform="rotate(-90 25 25)"
                            />
                        </svg>
                    </div>
                </div>

                <h1 className="text-2xl font-bold text-gray-900 mb-3" dir="rtl">
                    מתמלל כתב יד...
                </h1>

                <p className="text-gray-500 mb-8" dir="rtl">
                    ה-AI קורא את המבחן ומתמלל את התשובות
                </p>

                <div className="mb-4">
                    <div className="h-2 bg-surface-100 rounded-full overflow-hidden">
                        <div
                            className="h-full bg-gradient-to-r from-primary-400 via-primary-500 to-violet-500 animate-pulse"
                            style={{ width: '60%' }}
                        />
                    </div>
                </div>

                <p className="text-sm text-gray-400" dir="ltr">
                    {filename}
                </p>
            </div>
        </div>
    );
}