'use client';

import { useEffect } from 'react';

interface PdfProcessingPageProps {
    filename: string;
    // Called when PDF processing is complete and pages are ready
    onPagesReady: () => void;
    // Called on error
    onError: (message: string) => void;
    // Progress info (optional)
    progress?: {
        currentPage?: number;
        totalPages?: number;
    };
}

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

                    {/* Title */}
                    <h1 className="text-2xl font-bold text-gray-900 mb-3" dir="rtl">
                        מתמלל כתב יד...
                    </h1>

                    {/* Description */}
                    <p className="text-gray-500 mb-8" dir="rtl">
                        ה-AI קורא את המבחן ומתמלל את התשובות
                    </p>

                    {/* Progress bar with turquoise-purple gradient */}
                    <div className="mb-4">
                        <div className="h-2 bg-surface-100 rounded-full overflow-hidden">
                            <div
                                className="h-full bg-gradient-to-r from-primary-400 via-primary-500 to-violet-500 transition-all duration-500 ease-out"
                                style={{
                                    width: progressPercent !== null ? `${progressPercent}%` : '60%',
                                    // Animate width if no progress info
                                    animation: progressPercent === null ? 'pulse-width 2s ease-in-out infinite' : 'none'
                                }}
                            />
                        </div>
                    </div>

                    {/* Filename */}
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