'use client';

import { useState } from 'react';
import { PagePreview } from '@/lib/api';
import { Check, Maximize2, X } from 'lucide-react';

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
  const [isExpanded, setIsExpanded] = useState(false);

  const handleExpandClick = (e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent triggering selection
    setIsExpanded(true);
  };

  const handleCloseExpanded = () => {
    setIsExpanded(false);
  };

  return (
    <>
      <div
        className={`
          relative cursor-pointer transition-all duration-200 rounded-lg overflow-hidden
          border-2 hover:shadow-md group
          ${isSelected
            ? 'border-primary-500 ring-2 ring-primary-200 shadow-md'
            : 'border-surface-200 hover:border-primary-300'
          }
        `}
        onClick={onClick}
      >
        {/* Page number badge */}
        <div className="absolute top-1 right-8 z-10 bg-black/60 text-white text-xs px-2 py-0.5 rounded">
          {page.page_number}
        </div>

        {/* Expand button */}
        <button
          onClick={handleExpandClick}
          className="absolute top-1 right-1 z-10 bg-black/60 hover:bg-black/80 text-white p-1 rounded opacity-70 group-hover:opacity-100 transition-opacity"
          title="הגדל תמונה"
        >
          <Maximize2 size={14} />
        </button>

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

      {/* Expanded Modal */}
      {isExpanded && (
        <PageExpandedModal
          page={page}
          onClose={handleCloseExpanded}
        />
      )}
    </>
  );
}

interface PageExpandedModalProps {
  page: PagePreview;
  onClose: () => void;
}

function PageExpandedModal({ page, onClose }: PageExpandedModalProps) {
  // Close on escape key
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      onClose();
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
      onClick={onClose}
      onKeyDown={handleKeyDown}
      tabIndex={0}
    >
      {/* Close button */}
      <button
        onClick={onClose}
        className="absolute top-4 right-4 z-50 bg-white/10 hover:bg-white/20 text-white p-2 rounded-full transition-colors"
        title="סגור"
      >
        <X size={24} />
      </button>

      {/* Page number indicator */}
      <div className="absolute top-4 left-4 z-50 bg-white/10 text-white px-3 py-1.5 rounded-lg text-sm">
        עמוד {page.page_number}
      </div>

      {/* Expanded image */}
      <div
        className="relative max-w-[90vw] max-h-[90vh] overflow-auto"
        onClick={(e) => e.stopPropagation()} // Prevent closing when clicking the image
      >
        <img
          src={`data:image/png;base64,${page.thumbnail_base64}`}
          alt={`עמוד ${page.page_number}`}
          className="max-w-full max-h-[90vh] object-contain rounded-lg shadow-2xl"
        />
      </div>
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