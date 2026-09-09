'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { Loader2, Plus, Search, X } from 'lucide-react';

import { queryExactlyMatches, searchSchools, type School } from '@/utils/school-search';
import { MAX_SCHOOLS, type PickedSchool } from '@/lib/onboarding';
import {
    SCHOOLS_ADD_FREE_TEXT,
    SCHOOLS_CHOSEN,
    SCHOOLS_EMPTY,
    SCHOOLS_LOADING,
    SCHOOLS_LOAD_ERROR,
    SCHOOLS_MAX_REACHED,
    SCHOOLS_PLACEHOLDER,
    SCHOOLS_REMOVE,
} from '@/copy/onboarding';

/**
 * The school picker: type-ahead over the display index, plus free text for a
 * school the list does not have.
 *
 * The index is loaded with a DYNAMIC import (see data/israeli-schools.ts) — the
 * full list is large and belongs to this step only. A load failure is not fatal:
 * the field keeps working as free text, because a teacher whose network hiccuped
 * should still be able to name her school.
 *
 * Order is meaningful downstream (the first school becomes the PR-G6
 * attribution key), so picks append and nothing here sorts the chosen list.
 */
export function SchoolCombobox({
    picked,
    onChange,
}: {
    picked: PickedSchool[];
    onChange: (next: PickedSchool[]) => void;
}) {
    const [index, setIndex] = useState<School[] | null>(null);
    const [loadFailed, setLoadFailed] = useState(false);
    const [query, setQuery] = useState('');
    const [open, setOpen] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        let alive = true;
        import('@/data/israeli-schools')
            .then((mod) => {
                if (alive) setIndex(mod.schools);
            })
            .catch(() => {
                if (alive) {
                    setLoadFailed(true);
                    setIndex([]);      // free text still works
                }
            });
        return () => {
            alive = false;
        };
    }, []);

    useEffect(() => {
        function onDocMouseDown(e: MouseEvent) {
            if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
                setOpen(false);
            }
        }
        document.addEventListener('mousedown', onDocMouseDown);
        return () => document.removeEventListener('mousedown', onDocMouseDown);
    }, []);

    const results = useMemo(
        () => (index ? searchSchools(index, query) : []),
        [index, query],
    );

    const atMax = picked.length >= MAX_SCHOOLS;
    const trimmed = query.trim();
    const alreadyPicked = (label: string) =>
        picked.some((p) => p.label.toLowerCase() === label.toLowerCase());

    /** An index row → a pick. The dataset's `id` IS the Ministry symbol, and
     *  this is the ONE place that fact is used, so a future dataset that keys
     *  differently changes here and nowhere else. */
    const fromIndex = (school: School): PickedSchool => ({
        id: school.id,
        name: school.name,
        city: school.city,
        label: school.label,
        ministrySymbol: school.id,
    });

    const add = (school: PickedSchool) => {
        if (atMax || alreadyPicked(school.label)) {
            setQuery('');
            setOpen(false);
            return;
        }
        onChange([...picked, school]);
        setQuery('');
        setOpen(false);
    };

    const addFreeText = () => {
        if (!trimmed) return;
        // A free-text entry carries no city: the teacher typed one string and
        // splitting it on a comma would be a guess about which half is the city.
        // The server takes the name as written.
        // No symbol: the list does not have this school, so nothing identifies
        // it but the name she typed. That is honest, and the server falls back
        // to the name rule for exactly these.
        add({
            id: `free:${trimmed}`,
            name: trimmed,
            city: '',
            label: trimmed,
            ministrySymbol: null,
        });
    };

    const remove = (id: string) => onChange(picked.filter((p) => p.id !== id));

    const showFreeText =
        trimmed.length > 0 && !queryExactlyMatches(results, trimmed) && !atMax;

    return (
        <div className="space-y-3" ref={containerRef}>
            <div className="relative">
                <Search
                    className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-gray-400"
                    size={18}
                />
                <input
                    type="text"
                    value={query}
                    disabled={atMax}
                    onChange={(e) => {
                        setQuery(e.target.value);
                        setOpen(true);
                    }}
                    onFocus={() => setOpen(true)}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                            e.preventDefault();
                            if (results.length > 0) add(fromIndex(results[0]));
                            else if (showFreeText) addFreeText();
                        }
                    }}
                    placeholder={SCHOOLS_PLACEHOLDER}
                    aria-label={SCHOOLS_PLACEHOLDER}
                    data-testid="school-input"
                    className="w-full rounded-grade-ctl border border-surface-300 bg-white py-3 pr-12 pl-4
                               text-sm transition-colors focus:border-primary-400 focus:outline-none
                               focus:ring-2 focus:ring-primary-400/40 disabled:bg-surface-100"
                />

                {open && (trimmed.length > 0 || index === null) && (
                    <div
                        className="absolute z-10 mt-1 w-full overflow-hidden rounded-grade-ctl border
                                   border-surface-200 bg-white shadow-lg"
                        data-testid="school-results"
                    >
                        {index === null ? (
                            <p className="flex items-center gap-2 px-4 py-3 text-sm text-gray-500">
                                <Loader2 className="animate-spin motion-reduce:animate-none" size={14} />
                                {SCHOOLS_LOADING}
                            </p>
                        ) : (
                            <>
                                {results.map((school) => (
                                    <button
                                        key={school.id}
                                        type="button"
                                        onClick={() => add(fromIndex(school))}
                                        className="block w-full px-4 py-2.5 text-right text-sm text-gray-700
                                                   transition-colors hover:bg-primary-50"
                                    >
                                        {school.label}
                                    </button>
                                ))}

                                {results.length === 0 && !loadFailed && (
                                    <p className="px-4 py-2.5 text-sm text-gray-500">{SCHOOLS_EMPTY}</p>
                                )}
                                {loadFailed && (
                                    <p className="px-4 py-2.5 text-sm text-amber-700">
                                        {SCHOOLS_LOAD_ERROR}
                                    </p>
                                )}

                                {showFreeText && (
                                    <button
                                        type="button"
                                        onClick={addFreeText}
                                        data-testid="school-free-text"
                                        className="flex w-full items-center gap-2 border-t border-surface-200 px-4
                                                   py-2.5 text-right text-sm text-primary-700 transition-colors
                                                   hover:bg-primary-50"
                                    >
                                        <Plus size={14} />
                                        {SCHOOLS_ADD_FREE_TEXT(trimmed)}
                                    </button>
                                )}
                            </>
                        )}
                    </div>
                )}
            </div>

            {atMax && (
                <p className="text-sm text-amber-700">{SCHOOLS_MAX_REACHED(MAX_SCHOOLS)}</p>
            )}

            {picked.length > 0 && (
                <div className="space-y-2">
                    <p className="text-xs font-medium text-gray-500">{SCHOOLS_CHOSEN}</p>
                    <ul className="flex flex-wrap gap-2" data-testid="school-chips">
                        {picked.map((school) => (
                            <li
                                key={school.id}
                                className="flex items-center gap-2 rounded-full bg-primary-50 py-1.5 pr-3 pl-2
                                           text-sm text-primary-800"
                            >
                                {school.label}
                                <button
                                    type="button"
                                    onClick={() => remove(school.id)}
                                    aria-label={SCHOOLS_REMOVE(school.label)}
                                    className="rounded-full p-0.5 text-primary-600 transition-colors
                                               hover:bg-primary-100 hover:text-primary-900"
                                >
                                    <X size={14} />
                                </button>
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    );
}
