'use client';

import { useEffect, useState } from 'react';
import { Check, Loader2 } from 'lucide-react';

import { listSubjectMatters } from '@/lib/api';
import { surfaceError } from '@/lib/errorSurface';
import { pickOnboardingSubjects } from '@/lib/onboarding';
import type { SubjectMatterOption } from '@/types/classroom';
import {
    RETRY,
    SUBJECTS_HINT,
    SUBJECTS_LOADING,
    SUBJECTS_LOAD_ERROR,
} from '@/copy/onboarding';

/**
 * Step 2 — the three subjects Vivi actually extracts and grades (D6).
 *
 * The chips are resolved against `GET /users/subject-matters` rather than
 * hardcoding ids: ids are database rows, and a hardcoded number would silently
 * point at a different subject if the seed ever changed. Codes are stable.
 */
export function SubjectsStep({
    selected,
    onChange,
    showHint,
}: {
    selected: number[];
    onChange: (ids: number[]) => void;
    /** True once she has tried to advance with nothing chosen. */
    showHint: boolean;
}) {
    const [options, setOptions] = useState<SubjectMatterOption[] | null>(null);
    const [failed, setFailed] = useState(false);
    const [authLapsed, setAuthLapsed] = useState(false);
    const [attempt, setAttempt] = useState(0);

    useEffect(() => {
        let alive = true;
        setFailed(false);
        listSubjectMatters()
            .then((all) => {
                if (alive) setOptions(pickOnboardingSubjects(all));
            })
            .catch((err) => {
                if (!alive) return;
                // 401/403 is TERMINAL everywhere (the seam's standing rule): a
                // lapsed session is not "we couldn't load subjects", and a retry
                // button that can only fail again is a lie. surfaceError says
                // the honest thing and tells us it was an auth failure.
                if (surfaceError(err)) setAuthLapsed(true);
                setFailed(true);
            });
        return () => {
            alive = false;
        };
    }, [attempt]);

    const toggle = (id: number) => {
        onChange(
            selected.includes(id)
                ? selected.filter((x) => x !== id)
                : [...selected, id],
        );
    };

    if (failed) {
        return (
            <div className="space-y-3">
                <p className="text-sm text-red-700">{SUBJECTS_LOAD_ERROR}</p>
                {/* No retry offer after an auth failure — it could only fail
                    again. The toast has already said the true thing. */}
                {!authLapsed && (
                <button
                    type="button"
                    onClick={() => setAttempt((a) => a + 1)}
                    className="rounded-grade-ctl border border-surface-300 px-4 py-2 text-sm
                               text-gray-700 transition-colors hover:bg-surface-100"
                >
                    {RETRY}
                </button>
                )}
            </div>
        );
    }

    if (options === null) {
        return (
            <p className="flex items-center gap-2 text-sm text-gray-500">
                <Loader2 className="animate-spin motion-reduce:animate-none" size={16} />
                {SUBJECTS_LOADING}
            </p>
        );
    }

    return (
        <div className="space-y-4">
            <div className="flex flex-wrap gap-3" role="group">
                {options.map((subject) => {
                    const isOn = selected.includes(subject.id);
                    return (
                        <button
                            key={subject.id}
                            type="button"
                            onClick={() => toggle(subject.id)}
                            aria-pressed={isOn}
                            data-testid={`subject-${subject.code}`}
                            className={`flex items-center gap-2 rounded-grade-ctl border px-5 py-3 text-base
                                        transition-colors ${
                                            isOn
                                                ? 'border-primary-500 bg-primary-50 text-primary-800 font-medium'
                                                : 'border-surface-300 bg-white text-gray-700 hover:border-primary-300'
                                        }`}
                        >
                            {isOn && <Check size={16} className="text-primary-600" />}
                            {subject.name_he}
                        </button>
                    );
                })}
            </div>

            {showHint && selected.length === 0 && (
                <p className="text-sm text-amber-700" data-testid="subjects-hint">
                    {SUBJECTS_HINT}
                </p>
            )}
        </div>
    );
}
