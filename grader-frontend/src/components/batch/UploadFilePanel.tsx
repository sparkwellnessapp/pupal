'use client';

/**
 * U2/U3 — the upload dropzone + file list (P4; replaces MultiFileUpload's
 * single consumer). Everything the census flagged is structural here:
 *
 *  - BOTH intake paths (drag AND picker) run the same PDF/empty filter, and
 *    every exclusion is SURFACED with its §3.2 reason (U4: nothing silent).
 *  - >50 keeps the first 50 and says so (§3.2 truncation notice).
 *  - Duplicate (name, size) pairs carry the advisory dup chip — never block.
 *  - Sizes render as LTR `X.X MB` islands (§3.1).
 *  - U3 (W4): when `uploadStates` is present the list is LOCKED and each row
 *    renders its queue state — progress %, done ✓, or the failure reason with
 *    an inline retry (same client_file_id, wired by the caller).
 */

import { useRef, useState } from 'react';
import { Check, FileText, Loader2, Upload, X } from 'lucide-react';

import {
    UPLOAD_CLEAR_ALL,
    UPLOAD_DROPZONE,
    UPLOAD_DUP_CHIP,
    UPLOAD_RETRY,
    UPLOAD_SKIPPED_SUMMARY,
    UPLOAD_TRUNCATION_NOTICE,
} from '@/copy/batch';
import {
    applyAddFiles,
    detectDuplicates,
    formatMB,
    type ExcludedFile,
    type UploadItemState,
} from '@/utils/batch-upload';
import { filesCount } from '@/utils/hebrew-plural';

const MAX_FILES = 50;

export function UploadFilePanel({
    files,
    onFilesChange,
    disabled = false,
    uploadStates = null,
    onRetry,
}: {
    files: File[];
    onFilesChange: (files: File[]) => void;
    disabled?: boolean;
    /** U3: per-file queue state by index — presence locks the list. */
    uploadStates?: ReadonlyMap<number, UploadItemState> | null;
    onRetry?: (index: number) => void;
}) {
    const inputRef = useRef<HTMLInputElement>(null);
    const [dragOver, setDragOver] = useState(false);
    const [excluded, setExcluded] = useState<ExcludedFile[]>([]);
    const [truncated, setTruncated] = useState(false);

    const locked = disabled || uploadStates !== null;
    const dups = detectDuplicates(files);
    const totalBytes = files.reduce((s, f) => s + f.size, 0);

    const addFiles = (incoming: File[]) => {
        if (locked || incoming.length === 0) return;
        const r = applyAddFiles(files, incoming, MAX_FILES);
        onFilesChange(r.files);
        if (r.excluded.length > 0) setExcluded((prev) => [...prev, ...r.excluded]);
        if (r.truncated) setTruncated(true);
    };

    const removeAt = (index: number) => {
        if (locked) return;
        onFilesChange(files.filter((_, i) => i !== index));
    };

    const clearAll = () => {
        if (locked) return;
        onFilesChange([]);
        setExcluded([]);
        setTruncated(false);
    };

    return (
        <div>
            {/* Dropzone — drag and picker feed the SAME filter */}
            <div
                onDragOver={(e) => { e.preventDefault(); if (!locked) setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => {
                    e.preventDefault();
                    setDragOver(false);
                    addFiles(Array.from(e.dataTransfer.files));
                }}
                onClick={() => { if (!locked) inputRef.current?.click(); }}
                data-testid="upload-dropzone"
                className={`border-2 border-dashed rounded-xl p-6 text-center transition-colors ${
                    locked
                        ? 'border-surface-200 bg-surface-50 cursor-default opacity-70'
                        : dragOver
                            ? 'border-primary-400 bg-primary-50 cursor-pointer'
                            : 'border-surface-300 bg-surface-50 hover:border-primary-300 cursor-pointer'
                }`}
            >
                <Upload className="mx-auto text-gray-400 mb-2" size={28} />
                <p className="text-sm text-gray-600">{UPLOAD_DROPZONE}</p>
                <input
                    ref={inputRef}
                    type="file"
                    accept=".pdf,application/pdf"
                    multiple
                    className="hidden"
                    disabled={locked}
                    onChange={(e) => {
                        addFiles(Array.from(e.target.files ?? []));
                        e.target.value = '';   // re-selecting the same file re-fires
                    }}
                />
            </div>

            {/* U2: the §3.2 truncation notice — never a silent slice */}
            {truncated && (
                <div
                    className="mt-3 px-3 py-2 rounded-lg bg-batch-amber-soft border border-batch-amber-line text-batch-amber-ink text-sm"
                    data-testid="truncation-notice"
                >
                    {UPLOAD_TRUNCATION_NOTICE}
                </div>
            )}

            {/* U4: client-side exclusions surface with their reasons */}
            {excluded.length > 0 && (
                <div
                    className="mt-3 px-3 py-2 rounded-lg bg-batch-amber-soft border border-batch-amber-line text-batch-amber-ink text-sm"
                    data-testid="excluded-summary"
                >
                    {UPLOAD_SKIPPED_SUMMARY(
                        excluded.length,
                        excluded.map((e) => `${e.filename} — ${e.reason}`).join(', '),
                    )}
                </div>
            )}

            {files.length > 0 && (
                <div className="mt-4">
                    {/* Aggregate line + clear-all */}
                    <div className="flex items-center justify-between mb-2">
                        <span className="text-sm text-gray-600">
                            {filesCount(files.length)} · <span dir="ltr">{formatMB(totalBytes)}</span>
                        </span>
                        {!locked && (
                            <button
                                onClick={clearAll}
                                className="text-sm text-gray-500 hover:text-red-600 transition-colors"
                                data-testid="clear-all"
                            >
                                {UPLOAD_CLEAR_ALL}
                            </button>
                        )}
                    </div>

                    <div className="space-y-1.5 max-h-72 overflow-y-auto" data-testid="upload-file-list">
                        {files.map((f, i) => {
                            const st = uploadStates?.get(i) ?? null;
                            return (
                                <div
                                    key={`${f.name}:${f.size}:${f.lastModified}:${i}`}
                                    className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm ${
                                        st?.kind === 'failed'
                                            ? 'border-batch-red-line bg-batch-red-soft'
                                            : 'border-surface-200 bg-white'
                                    }`}
                                    data-testid="upload-row"
                                >
                                    <FileText size={15} className="text-gray-400 shrink-0" />
                                    <span className="flex-1 truncate text-gray-800" title={f.name}>{f.name}</span>
                                    {dups.has(i) && (
                                        <span
                                            className="shrink-0 text-xs px-2 py-0.5 rounded-full bg-batch-amber-soft border border-batch-amber-line text-batch-amber-ink"
                                            data-testid="dup-chip"
                                        >
                                            {UPLOAD_DUP_CHIP}
                                        </span>
                                    )}
                                    <span dir="ltr" className="shrink-0 text-xs text-gray-500" data-testid="file-size">
                                        {formatMB(f.size)}
                                    </span>

                                    {/* U3: per-row queue state */}
                                    {st?.kind === 'uploading' && (
                                        <span className="shrink-0 flex items-center gap-1.5 text-xs text-gray-600" data-testid="row-uploading">
                                            <Loader2 size={13} className="animate-spin" />
                                            <span dir="ltr">{st.pct}%</span>
                                        </span>
                                    )}
                                    {st?.kind === 'done' && (
                                        <Check size={16} className="shrink-0 text-batch-green" data-testid="row-done" />
                                    )}
                                    {st?.kind === 'failed' && (
                                        <span className="shrink-0 flex items-center gap-2 text-xs text-batch-red-ink" data-testid="row-failed">
                                            <span className="max-w-[180px] truncate" title={st.reason}>{st.reason}</span>
                                            {st.retryable && onRetry && (
                                                <button
                                                    onClick={() => onRetry(i)}
                                                    className="px-2 py-0.5 rounded bg-batch-red text-white hover:opacity-90 transition-opacity"
                                                    data-testid="row-retry"
                                                >
                                                    {UPLOAD_RETRY}
                                                </button>
                                            )}
                                        </span>
                                    )}

                                    {!locked && (
                                        <button
                                            onClick={() => removeAt(i)}
                                            className="shrink-0 p-0.5 text-gray-400 hover:text-red-600 transition-colors"
                                            aria-label={`הסרת ${f.name}`}
                                        >
                                            <X size={15} />
                                        </button>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
}
