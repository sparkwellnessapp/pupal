'use client';

import { PagePreview } from '@/lib/api';
import { Check } from 'lucide-react';

interface PageThumbnailProps {
  page: PagePreview;
  isSelected: boolean;
  selectionLabel?: string;
  selectionColor?: string;
  onClick: () => void;
}

export function PageThumbnail({
  page,
  isSelected,
  selectionLabel,
  selectionColor = 'bg-primary-500',
  onClick,
}: PageThumbnailProps) {
  return (
    <div
      className={`
        relative cursor-pointer transition-all duration-200 rounded-lg overflow-hidden
        border-2 hover:shadow-md
        ${isSelected 
          ? 'border-primary-500 ring-2 ring-primary-200 shadow-md' 
          : 'border-surface-200 hover:border-primary-300'
        }
      `}
      onClick={onClick}
    >
      {/* Page number badge */}
      <div className="absolute top-1 right-1 z-10 bg-black/60 text-white text-xs px-2 py-0.5 rounded">
        {page.page_number}
      </div>

      {/* Selection indicator */}
      {isSelected && (
        <div className={`absolute top-1 left-1 z-10 ${selectionColor} text-white rounded-full p-1`}>
          <Check size={12} />
        </div>
      )}

      {/* Selection label */}
      {selectionLabel && (
        <div className={`absolute bottom-0 left-0 right-0 ${selectionColor} text-white text-xs py-1 text-center font-medium`}>
          {selectionLabel}
        </div>
      )}

      {/* Thumbnail image */}
      <img
        src={`data:image/png;base64,${page.thumbnail_base64}`}
        alt={`עמוד ${page.page_number}`}
        className="w-full h-auto"
        style={{ aspectRatio: `${page.width} / ${page.height}` }}
      />
    </div>
  );
}

interface PageGridProps {
  pages: PagePreview[];
  selections: Map<number, { label: string; color: string }>;
  onPageClick: (pageIndex: number) => void;
}

export function PageGrid({ pages, selections, onPageClick }: PageGridProps) {
  return (
    <div className="grid grid-cols-4 gap-3">
      {pages.map((page) => {
        const selection = selections.get(page.page_index);
        return (
          <PageThumbnail
            key={page.page_index}
            page={page}
            isSelected={!!selection}
            selectionLabel={selection?.label}
            selectionColor={selection?.color}
            onClick={() => onPageClick(page.page_index)}
          />
        );
      })}
    </div>
  );
}
