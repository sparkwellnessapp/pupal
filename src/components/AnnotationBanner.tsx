import type { ReactNode } from 'react';
import { AlertCircle, AlertTriangle, Info } from 'lucide-react';
import type { Annotation } from '@/lib/api';

/**
 * The single severity-differentiated annotation renderer for the RUBRIC surface.
 *
 * PR-5 S2 (F5): lifted VERBATIM out of RubricEditor.tsx, where it had lived inline
 * — which made CLAUDE.md §10's "src/components/AnnotationBanner.tsx" a phantom.
 * Now the documented file is real. Both RubricEditor (rollback) and RubricDocument
 * (the mirror) import this one copy.
 *
 * NOT unified with TranscriptionReviewPanel's AnnotationBanner (it carries an
 * `onShowPage` page-proxy prop) or GradedTestReviewPanel's GradingAnnotationBanner
 * (a different `GradingAnnotation` type). Those stay put — different props, different
 * types; merging them would be Easy, not Simple.
 */

interface AnnotationBannerProps {
    annotation: Annotation;
}

export function AnnotationBanner({ annotation }: AnnotationBannerProps) {
    const styles: Record<string, string> = {
        error:   'bg-red-50 border-red-300 text-red-800',
        warning: 'bg-amber-50 border-amber-300 text-amber-800',
        info:    'bg-blue-50 border-blue-300 text-blue-700',
    };
    const icons: Record<string, ReactNode> = {
        error:   <AlertCircle   size={15} className="flex-shrink-0 mt-0.5 text-red-500"    />,
        warning: <AlertTriangle size={15} className="flex-shrink-0 mt-0.5 text-amber-500"  />,
        info:    <Info          size={15} className="flex-shrink-0 mt-0.5 text-blue-500"   />,
    };
    return (
        <div
            className={`flex items-start gap-2 px-3 py-2 border rounded-lg text-sm ${styles[annotation.severity] ?? styles.info}`}
            dir="rtl"
        >
            {icons[annotation.severity] ?? icons.info}
            <span>{annotation.message}</span>
        </div>
    );
}
