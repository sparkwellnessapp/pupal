'use client';

import { Fragment, useMemo, useState } from 'react';
import { Check, ChevronDown, ChevronUp, Pencil } from 'lucide-react';
import { type NestedTableBlock, type TableSegment, inferGridDir, parseMarkdownText } from '@/utils/markdown-parser';

// =============================================================================
// Public component
// =============================================================================

interface MarkdownTextRendererProps {
  value: string;
  onChange: (val: string) => void;
  placeholder?: string;
  className?: string;
  /** Extra classes forwarded to the <textarea> in edit mode */
  textareaClassName?: string;
  minHeight?: string;
  maxHeight?: string;
}

/**
 * Renders a text field that may contain [TABLE N: RxC] markdown produced by
 * the v3 DOCX pipeline. Tables are shown as proper HTML tables; the rest is
 * shown as styled paragraphs.
 *
 * Hover the display area to reveal a pencil edit button. Click it (or the
 * placeholder) to switch to a raw textarea. Blur or click ✓ to return to
 * display mode.
 */
export function MarkdownTextRenderer({
  value,
  onChange,
  placeholder = '',
  className = '',
  textareaClassName = '',
  minHeight = '60px',
  maxHeight = '240px',
}: MarkdownTextRendererProps) {
  const [isEditing, setIsEditing] = useState(false);

  const parsed = useMemo(() => parseMarkdownText(value), [value]);
  const isEmpty = !value || !value.trim();

  const startEditing = () => setIsEditing(true);
  const stopEditing  = () => setIsEditing(false);

  const autoResize = (el: HTMLTextAreaElement) => {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, parseInt(maxHeight)) + 'px';
  };

  if (isEditing) {
    return (
      <div className={`relative ${className}`}>
        <textarea
          // eslint-disable-next-line jsx-a11y/no-autofocus
          autoFocus
          ref={(el) => { if (el) autoResize(el); }}
          value={value}
          onChange={e => {
            onChange(e.target.value);
            autoResize(e.target);
          }}
          onBlur={stopEditing}
          className={`w-full p-3 border border-primary-300 rounded-lg text-sm resize-none focus:ring-2 focus:ring-primary-300 focus:border-primary-400 overflow-y-auto ${textareaClassName}`}
          style={{ minHeight, maxHeight, unicodeBidi: 'plaintext' as React.CSSProperties['unicodeBidi'] }}
          dir="rtl"
        />
        <button
          onMouseDown={e => { e.preventDefault(); stopEditing(); }}
          className="absolute top-1.5 left-1.5 p-1 bg-white/90 border border-primary-200 rounded text-primary-600 hover:bg-primary-50 shadow-sm"
          title="סיים עריכה"
        >
          <Check size={13} />
        </button>
      </div>
    );
  }

  return (
    <div
      className={`relative group rounded-lg border border-surface-200 bg-surface-50 p-3 cursor-text ${className}`}
      onClick={isEmpty ? startEditing : undefined}
      style={{ minHeight }}
    >
      {/* Edit button (appears on hover) */}
      <button
        onClick={e => { e.stopPropagation(); startEditing(); }}
        className="absolute top-1.5 left-1.5 p-1 bg-white/90 border border-surface-200 rounded text-gray-400 hover:text-primary-600 hover:border-primary-200 shadow-sm opacity-0 group-hover:opacity-100 transition-opacity z-10"
        title="ערוך"
      >
        <Pencil size={13} />
      </button>

      {isEmpty ? (
        <span className="text-sm text-gray-400 select-none" dir="rtl">
          {placeholder || 'לחץ לעריכה...'}
        </span>
      ) : (
        <div className="space-y-2">
          {parsed.map((seg, idx) =>
            seg.type === 'text'
              ? <TextBlock key={idx} content={seg.content} />
              : <MarkdownTableDisplay key={idx} segment={seg} />
          )}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Text block — paragraphs + line breaks, RTL-aware
// =============================================================================

function TextBlock({ content }: { content: string }) {
  const paragraphs = content.split(/\n{2,}/);
  const hebrewRe = /[֐-׿]/;

  return (
    <>
      {paragraphs.map((para, i) => {
        if (!para.trim()) return null;
        const dir = hebrewRe.test(para) ? 'rtl' : 'ltr';
        // Code-ish paragraph: lines starting with spaces or braces
        const isCode = para.split('\n').every(l => /^[\s{}()[\]<>]/.test(l) || !l.trim());
        if (isCode && para.includes('\n')) {
          return (
            <pre
              key={i}
              dir="ltr"
              className="text-xs font-mono bg-gray-50 border border-gray-200 rounded p-2 overflow-x-auto whitespace-pre-wrap break-words"
            >
              {para}
            </pre>
          );
        }
        return (
          <p key={i} dir={dir} className="text-sm text-gray-800 leading-relaxed">
            {para.split('\n').map((line, j, arr) => (
              <span key={j}>
                {line}
                {j < arr.length - 1 && <br />}
              </span>
            ))}
          </p>
        );
      })}
    </>
  );
}

// =============================================================================
// Table display
// =============================================================================

interface MarkdownTableDisplayProps {
  segment: TableSegment;
}

function MarkdownTableDisplay({ segment }: MarkdownTableDisplayProps) {
  const { rows, nestedTables } = segment;
  if (rows.length === 0) return null;

  const headerRow = rows[0];
  const dataRows  = rows.slice(1);
  const colCount  = headerRow.length;
  const dir       = inferGridDir(rows);

  // Build a lookup: data row index → nested blocks that follow it
  const nestedByRow = new Map<number, NestedTableBlock[]>();
  for (const nb of nestedTables) {
    const key = nb.afterRowIndex;
    if (!nestedByRow.has(key)) nestedByRow.set(key, []);
    nestedByRow.get(key)!.push(nb);
  }

  return (
    <div className="border border-blue-200 rounded-lg overflow-hidden text-xs" dir={dir}>
      <table className="w-full border-collapse">
        <thead>
          <tr className="bg-blue-100">
            {headerRow.map((cell, ci) => (
              <th
                key={ci}
                className={`px-3 py-2 border border-blue-200 font-semibold text-blue-900 align-top ${dir === 'rtl' ? 'text-right' : 'text-left'}`}
              >
                {cell || ''}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {dataRows.map((row, ri) => {
            const isEven = ri % 2 === 0;
            const nested = nestedByRow.get(ri);
            return (
              <Fragment key={ri}>
                <tr className={isEven ? 'bg-white' : 'bg-blue-50/40'}>
                  {row.map((cell, ci) => (
                    <td
                      key={ci}
                      className={`px-3 py-2 border border-blue-100 align-top ${!cell ? 'text-gray-300' : 'text-gray-700'} ${dir === 'rtl' ? 'text-right' : 'text-left'}`}
                    >
                      {cell || ''}
                    </td>
                  ))}
                </tr>
                {nested?.map((nb, ni) => (
                  <NestedTableRow key={`nested-${ri}-${ni}`} block={nb} colCount={colCount} dir={dir} />
                ))}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// =============================================================================
// Nested table row (collapsible)
// =============================================================================

function NestedTableRow({
  block,
  colCount,
  dir,
}: {
  block: NestedTableBlock;
  colCount: number;
  dir: 'rtl' | 'ltr';
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const dataRows = block.rows.slice(1);
  const headerRow = block.rows[0];

  return (
    <tr className="bg-indigo-50/60">
      <td colSpan={colCount} className="px-3 py-0">
        <div className="py-1.5">
          <button
            onClick={() => setIsExpanded(v => !v)}
            className="flex items-center gap-1.5 text-xs text-indigo-600 hover:text-indigo-800 font-medium transition-colors"
            dir={dir}
          >
            {isExpanded
              ? <ChevronUp size={13} />
              : <ChevronDown size={13} />
            }
            <span>פירוט ({dataRows.length})</span>
          </button>

          {isExpanded && block.rows.length > 0 && (
            <div className="mt-2 border border-indigo-200 rounded overflow-hidden" dir={dir}>
              <table className="w-full border-collapse text-xs">
                {headerRow && (
                  <thead>
                    <tr className="bg-indigo-100">
                      {headerRow.map((cell, ci) => (
                        <th
                          key={ci}
                          className={`px-2 py-1.5 border border-indigo-200 font-semibold text-indigo-900 ${dir === 'rtl' ? 'text-right' : 'text-left'}`}
                        >
                          {cell || ''}
                        </th>
                      ))}
                    </tr>
                  </thead>
                )}
                <tbody>
                  {dataRows.map((row, ri) => (
                    <tr key={ri} className={ri % 2 === 0 ? 'bg-white' : 'bg-indigo-50/40'}>
                      {row.map((cell, ci) => (
                        <td
                          key={ci}
                          className={`px-2 py-1.5 border border-indigo-100 align-top ${!cell ? 'text-gray-300' : 'text-gray-700'} ${dir === 'rtl' ? 'text-right' : 'text-left'}`}
                        >
                          {cell || ''}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </td>
    </tr>
  );
}
