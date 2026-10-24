'use client'

/**
 * The capture link's new-class step: which of her existing students belong to
 * the class being created. «שיוך כל התלמידים» selects everyone; she can untick
 * or search. Students matter here because the student link identifies a name
 * against the CLASS roster — a student she already has but who is not in the
 * class would arrive as «not on the list» and wait for her approval.
 *
 * Selection only; the adds happen after the class exists (one bounded add-all,
 * `lib/class-membership`).
 */
import { useMemo, useState } from 'react'

import { P } from '@/copy/capture'

export interface RosterOption { id: string; full_name: string }

export function NewClassStudents({ roster, selected, onChange, disabled }: {
  roster: RosterOption[]
  selected: ReadonlySet<string>
  onChange: (next: Set<string>) => void
  disabled?: boolean
}) {
  const [query, setQuery] = useState('')
  const sorted = useMemo(
    () => [...roster].sort((a, b) => a.full_name.localeCompare(b.full_name, 'he', { numeric: true })), [roster])
  const shown = useMemo(() => {
    // A plain substring, not the identity normalizer: that one sorts tokens
    // (OD-6), which is right for matching a whole name and wrong for typing
    // the start of one.
    const q = query.trim().toLowerCase()
    return q ? sorted.filter((s) => s.full_name.toLowerCase().includes(q)) : sorted
  }, [sorted, query])

  const all = selected.size === roster.length && roster.length > 0
  const toggle = (id: string) => {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    onChange(next)
  }

  return (
    <div className="space-y-2 rounded-lg border border-batch-line p-3" data-testid="new-class-students">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm font-medium text-batch-ink">{P.assignStudentsTitle}</span>
        <button type="button" disabled={disabled}
                onClick={() => onChange(all ? new Set() : new Set(roster.map((s) => s.id)))}
                data-testid="assign-all-students"
                className="min-h-[36px] rounded-lg border border-primary-200 px-3 text-xs font-medium text-primary-700 hover:bg-primary-50 disabled:opacity-50">
          {all ? P.clearAssigned : P.assignAll}
        </button>
      </div>
      <p className="text-xs text-batch-muted">{P.assignedCount(selected.size, roster.length)}</p>
      {roster.length > 8 && (
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={P.searchStudents}
               className="block w-full rounded-lg border border-batch-line px-3 py-1.5 text-sm" />
      )}
      <ul className="max-h-48 space-y-0.5 overflow-y-auto">
        {shown.map((s) => (
          <li key={s.id}>
            <label className="flex min-h-[36px] cursor-pointer items-center gap-2 rounded px-1 text-sm text-batch-ink hover:bg-surface-50">
              <input type="checkbox" checked={selected.has(s.id)} disabled={disabled}
                     onChange={() => toggle(s.id)} />
              <span>{s.full_name}</span>
            </label>
          </li>
        ))}
      </ul>
    </div>
  )
}
