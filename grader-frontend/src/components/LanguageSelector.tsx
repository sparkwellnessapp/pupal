'use client';

import { useState, useRef, useEffect } from 'react';
import { ChevronDown, Code2, AlertTriangle } from 'lucide-react';

interface LanguageSelectorProps {
    value: string;
    onChange: (language: string) => void;
    className?: string;
}

const LANGUAGES = [
    'Java',
    'Python',
    'C',
    'C++',
    'C#',
    'JavaScript',
    'TypeScript',
    'HTML/CSS',
    'SQL',
    'Pseudocode',
];

const KNOWN_LANGUAGES = new Set(LANGUAGES.map(l => l.toLowerCase()));

export function LanguageSelector({ value, onChange, className = '' }: LanguageSelectorProps) {
    const [isOpen, setIsOpen] = useState(false);
    const [customValue, setCustomValue] = useState('');
    const [isRecognized, setIsRecognized] = useState(true);
    const containerRef = useRef<HTMLDivElement>(null);

    // Check if value is recognized
    useEffect(() => {
        if (value) {
            const recognized = KNOWN_LANGUAGES.has(value.toLowerCase());
            setIsRecognized(recognized);
        } else {
            setIsRecognized(true);
        }
    }, [value]);

    // Close on outside click
    useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
                setIsOpen(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const handleSelect = (lang: string) => {
        onChange(lang);
        setIsOpen(false);
        setCustomValue('');
    };

    const handleCustomSubmit = () => {
        if (customValue.trim()) {
            onChange(customValue.trim());
            setIsOpen(false);
            setCustomValue('');
        }
    };

    return (
        <div ref={containerRef} className={`relative ${className}`}>
            <label className="block text-sm font-medium text-gray-700 mb-1">
                שפת תכנות (אופציונלי)
            </label>

            <button
                type="button"
                onClick={() => setIsOpen(!isOpen)}
                className="w-full flex items-center justify-between gap-2 px-3 py-2 bg-white border border-gray-300 rounded-lg text-right hover:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-500 transition-colors"
            >
                <div className="flex items-center gap-2">
                    <Code2 size={16} className="text-gray-400" />
                    <span className={value ? 'text-gray-800' : 'text-gray-400'}>
                        {value || 'בחר שפה...'}
                    </span>
                </div>
                <ChevronDown
                    size={16}
                    className={`text-gray-400 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
                />
            </button>

            {/* Unknown language warning */}
            {!isRecognized && value && (
                <div className="flex items-center gap-1.5 mt-1.5 text-xs text-amber-600">
                    <AlertTriangle size={12} />
                    <span>שפה לא מוכרת - הבדיקה תתבצע ללא הנחיות ספציפיות</span>
                </div>
            )}

            {isOpen && (
                <div className="absolute z-50 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-64 overflow-y-auto">
                    {/* Custom input */}
                    <div className="p-2 border-b border-gray-100">
                        <div className="flex gap-2">
                            <input
                                type="text"
                                value={customValue}
                                onChange={(e) => setCustomValue(e.target.value)}
                                onKeyDown={(e) => e.key === 'Enter' && handleCustomSubmit()}
                                placeholder="הקלד שפה אחרת..."
                                className="flex-1 px-2 py-1.5 text-sm border border-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-primary-500"
                            />
                            {customValue && (
                                <button
                                    type="button"
                                    onClick={handleCustomSubmit}
                                    className="px-3 py-1.5 text-xs bg-primary-500 text-white rounded hover:bg-primary-600 transition-colors"
                                >
                                    הוסף
                                </button>
                            )}
                        </div>
                    </div>

                    {/* Preset options */}
                    <div className="py-1">
                        {/* Clear selection option */}
                        {value && (
                            <button
                                type="button"
                                onClick={() => handleSelect('')}
                                className="w-full px-3 py-2 text-right text-sm text-gray-500 hover:bg-gray-50"
                            >
                                ללא שפה (כללי)
                            </button>
                        )}

                        {LANGUAGES.map((lang) => (
                            <button
                                key={lang}
                                type="button"
                                onClick={() => handleSelect(lang)}
                                className={`w-full px-3 py-2 text-right text-sm hover:bg-primary-50 ${value === lang
                                        ? 'bg-primary-50 text-primary-700 font-medium'
                                        : 'text-gray-700'
                                    }`}
                            >
                                {lang}
                            </button>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
