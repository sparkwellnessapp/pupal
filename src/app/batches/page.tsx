'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Loader2, AlertCircle, ClipboardCheck, Calendar } from 'lucide-react';
import { SidebarLayout } from '@/components/SidebarLayout';
import { listGradingBatches } from '@/lib/api';
import type { BatchListItem } from '@/types/batch';

function StatusBadge({ status }: { status: string }) {
    const map: Record<string, string> = {
        in_progress: 'bg-amber-100 text-amber-700',
        completed: 'bg-green-100 text-green-700',
        partially_completed: 'bg-orange-100 text-orange-700',
        failed: 'bg-red-100 text-red-700',
        pending: 'bg-gray-100 text-gray-500',
    };
    const labels: Record<string, string> = {
        in_progress: 'בתהליך',
        completed: 'הושלם',
        partially_completed: 'הושלם חלקית',
        failed: 'נכשל',
        pending: 'ממתין',
    };
    return (
        <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${map[status] ?? 'bg-gray-100 text-gray-500'}`}>
            {labels[status] ?? status}
        </span>
    );
}

export default function BatchListPage() {
    const [batches, setBatches] = useState<BatchListItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        listGradingBatches()
            .then(r => setBatches(r.batches))
            .catch(err => setError(err instanceof Error ? err.message : 'שגיאה בטעינת האצוות'))
            .finally(() => setLoading(false));
    }, []);

    const formatDate = (iso: string) => new Date(iso).toLocaleDateString('he-IL', {
        year: 'numeric', month: 'short', day: 'numeric',
    });

    return (
        <SidebarLayout>
            <div className="max-w-4xl mx-auto">
                <div className="flex items-center justify-between mb-6">
                    <div>
                        <h1 className="text-2xl font-bold text-gray-900">אצוות בדיקה</h1>
                        <p className="text-gray-500 mt-1">בדיקות קבוצתיות שהוגשו</p>
                    </div>
                    <Link
                        href="/"
                        className="flex items-center gap-2 bg-primary-500 text-white px-4 py-2.5 rounded-lg hover:bg-primary-600 transition-colors font-medium text-sm"
                    >
                        <ClipboardCheck size={16} />
                        אצווה חדשה
                    </Link>
                </div>

                {loading ? (
                    <div className="flex items-center justify-center py-20">
                        <Loader2 className="animate-spin text-primary-500" size={40} />
                    </div>
                ) : error ? (
                    <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center">
                        <AlertCircle className="mx-auto text-red-500 mb-2" size={32} />
                        <p className="text-red-700">{error}</p>
                    </div>
                ) : batches.length === 0 ? (
                    <div className="bg-white rounded-xl border border-surface-200 p-12 text-center">
                        <ClipboardCheck className="mx-auto text-gray-300 mb-4" size={48} />
                        <h3 className="text-lg font-medium text-gray-700 mb-2">אין אצוות עדיין</h3>
                        <Link href="/" className="text-primary-600 hover:underline text-sm">
                            צור אצווה ראשונה
                        </Link>
                    </div>
                ) : (
                    <div className="space-y-3">
                        {batches.map(batch => (
                            <Link
                                key={batch.id}
                                href={`/batches/${batch.id}`}
                                className="block bg-white rounded-xl border border-surface-200 px-5 py-4 hover:border-primary-300 hover:shadow-sm transition-all"
                            >
                                <div className="flex items-center justify-between">
                                    <div>
                                        <p className="font-medium text-gray-900">
                                            {batch.name ?? `אצווה ${batch.id.slice(0, 8)}`}
                                        </p>
                                        <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
                                            <span className="flex items-center gap-1">
                                                <Calendar size={12} />
                                                {formatDate(batch.created_at)}
                                            </span>
                                            <span>{batch.rollup.total} מבחנים</span>
                                            <span>{batch.rollup.approved} מאושרים</span>
                                        </div>
                                    </div>
                                    <StatusBadge status={batch.status} />
                                </div>
                                {/* Mini progress bar */}
                                {batch.rollup.total > 0 && (
                                    <div className="mt-3 w-full bg-surface-100 rounded-full h-1.5">
                                        <div
                                            className="bg-green-500 h-1.5 rounded-full"
                                            style={{ width: `${Math.round(batch.rollup.approved / batch.rollup.total * 100)}%` }}
                                        />
                                    </div>
                                )}
                            </Link>
                        ))}
                    </div>
                )}
            </div>
        </SidebarLayout>
    );
}
