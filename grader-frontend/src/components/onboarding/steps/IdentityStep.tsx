'use client';

import type { Gender } from '@/lib/onboarding';
import {
    GENDER_OPTIONS,
    IDENTITY_GENDER_LABEL,
    IDENTITY_NAME_LABEL,
    IDENTITY_NAME_PLACEHOLDER,
    IDENTITY_NAME_REQUIRED,
} from '@/copy/onboarding';

/**
 * Step 4 — name and gender, both required (D7).
 *
 * The name is PREFILLED from signup, so "required" costs the teacher nothing in
 * the normal case; it is here because until this endpoint existed nothing could
 * write `full_name`, and a typo at signup was permanent.
 *
 * Gender is answerable by anyone: «מעדיפ/ה לא לציין» is a stored answer, not a
 * silence. Nothing in the product's copy reads it yet (D4) — it is collected for
 * future address forms, and this step does not promise otherwise.
 */
export function IdentityStep({
    fullName,
    gender,
    onNameChange,
    onGenderChange,
    showHint,
}: {
    fullName: string;
    gender: Gender | null;
    onNameChange: (value: string) => void;
    onGenderChange: (value: Gender) => void;
    showHint: boolean;
}) {
    const nameMissing = showHint && fullName.trim().length === 0;

    return (
        <div className="space-y-6">
            <div className="space-y-1.5">
                <label
                    htmlFor="onboarding-full-name"
                    className="block text-sm font-medium text-gray-600"
                >
                    {IDENTITY_NAME_LABEL}
                </label>
                <input
                    id="onboarding-full-name"
                    type="text"
                    value={fullName}
                    onChange={(e) => onNameChange(e.target.value)}
                    placeholder={IDENTITY_NAME_PLACEHOLDER}
                    data-autofocus
                    aria-invalid={nameMissing}
                    aria-describedby={nameMissing ? 'onboarding-name-hint' : undefined}
                    className={`w-full rounded-grade-ctl border bg-white px-4 py-3 text-sm
                                transition-colors focus:outline-none focus:ring-2 ${
                                    nameMissing
                                        ? 'border-red-300 focus:border-red-400 focus:ring-red-400/40'
                                        : 'border-surface-300 focus:border-primary-400 focus:ring-primary-400/40'
                                }`}
                />
                {nameMissing && (
                    <p id="onboarding-name-hint" className="text-sm text-amber-700">
                        {IDENTITY_NAME_REQUIRED}
                    </p>
                )}
            </div>

            <fieldset className="space-y-2">
                <legend className="mb-2 block text-sm font-medium text-gray-600">
                    {IDENTITY_GENDER_LABEL}
                </legend>
                <div className="flex flex-wrap gap-3">
                    {GENDER_OPTIONS.map((option) => {
                        const isOn = gender === option.value;
                        return (
                            <button
                                key={option.value}
                                type="button"
                                onClick={() => onGenderChange(option.value)}
                                aria-pressed={isOn}
                                data-testid={`gender-${option.value}`}
                                className={`rounded-grade-ctl border px-5 py-2.5 text-sm transition-colors ${
                                    isOn
                                        ? 'border-primary-500 bg-primary-50 font-medium text-primary-800'
                                        : 'border-surface-300 bg-white text-gray-700 hover:border-primary-300'
                                }`}
                            >
                                {option.label}
                            </button>
                        );
                    })}
                </div>
            </fieldset>
        </div>
    );
}
