'use client';

import { useState, useEffect } from 'react';
import { RubricListItem, listRubrics } from '@/lib/api';
import { FileText, Calendar, Loader2, RefreshCw } from 'lucide-react';

interface RubricSelectorProps {
  onSelect: (rubric: RubricListItem) => void;
}

export function RubricSelector({ onSelect }: RubricSelectorProps) {
  const [rubrics, setRubrics] = useState<RubricListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadRubrics = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listRubrics();
      setRubrics(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'שגיאה בטעינת המחוונים');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadRubrics();
  }, []);

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('he-IL', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="animate-spin text-primary-500" size={32} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-8">
        <p className="text-red-600 mb-4">{error}</p>
        <button
          onClick={loadRubrics}
          className="flex items-center gap-2 mx-auto text-primary-600 hover:text-primary-700"
        >
          <RefreshCw size={16} />
          נסה שוב
        </button>
      </div>
    );
  }

  if (rubrics.length === 0) {
    return (
      <div className="text-center py-12 bg-surface-50 rounded-xl">
        <FileText className="mx-auto text-gray-300 mb-3" size={48} />
        <p className="text-gray-500">אין מחוונים שמורים</p>
        <p className="text-gray-400 text-sm mt-1">צור מחוון חדש כדי להתחיל</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-medium text-gray-700">בחר מחוון</h3>
        <button
          onClick={loadRubrics}
          className="text-gray-400 hover:text-primary-500 transition-colors"
          title="רענן רשימה"
        >
          <RefreshCw size={16} />
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 max-h-[400px] overflow-y-auto p-1">
        {rubrics.map((rubric) => (
          <button
            key={rubric.id}
            onClick={() => onSelect(rubric)}
            className="group bg-white rounded-xl border-2 border-surface-200 hover:border-primary-400 hover:shadow-lg transition-all p-4 text-right"
          >
            {/* Mini PDF preview placeholder */}
            <div className="bg-gradient-to-br from-surface-100 to-surface-200 rounded-lg h-24 mb-3 flex items-center justify-center relative overflow-hidden">
              {/* Fake PDF lines */}
              <div className="absolute inset-3 space-y-2">
                <div className="h-2 bg-surface-300/50 rounded w-3/4"></div>
                <div className="h-2 bg-surface-300/50 rounded w-full"></div>
                <div className="h-2 bg-surface-300/50 rounded w-5/6"></div>
                <div className="h-2 bg-surface-300/50 rounded w-2/3"></div>
                <div className="h-2 bg-surface-300/50 rounded w-4/5"></div>
              </div>
              <FileText 
                className="text-primary-300 group-hover:text-primary-400 transition-colors absolute bottom-2 right-2" 
                size={24} 
              />
            </div>

            {/* Rubric info */}
            <h4 className="font-medium text-gray-800 truncate group-hover:text-primary-700 transition-colors">
              {rubric.name || 'מחוון ללא שם'}
            </h4>
            
            <div className="flex items-center gap-1 mt-2 text-xs text-gray-400">
              <Calendar size={12} />
              <span>{formatDate(rubric.created_at)}</span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
