'use client'

/**
 * CaptureFlow — the shared core of both capture pages (§8.1). It owns the
 * page list, the capture inputs, the upload queue and the corner editor; it
 * owns NO auth (it is handed an API adapter) and no save button (each page
 * gates its own save on the state this reports — SCN-6, and SCN-8 on the
 * teacher page).
 *
 * The server's page list is the truth: after a reload, a page still
 * `awaiting_upload` lost its file and says so (retake or remove).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Camera, ImagePlus, RotateCcw, X } from 'lucide-react'

import type { FlowCopy } from '@/copy/capture'
import type { CapturePagesApi } from '@/lib/capture-api'
import type { PageView, Quad, Rotation } from '@/types/capture'
import { ACCEPT_ATTR, contentTypeOf, orderFiles } from '@/utils/capture-files'

import { CornerEditor } from './CornerEditor'
import { PageStrip, type StripPage } from './PageStrip'
import { useCaptureUploads } from './useCaptureUploads'

export interface CaptureFlowState {
  pageCount: number
  /** photos still on their way (queued, uploading, confirming, failed) */
  pending: number
  /** server pages that never finished uploading — they block a save too */
  awaiting: number
  firstPage: PageView | null
}

const MAX_PAGES = 20

function usePhone(): boolean {
  const [phone, setPhone] = useState(false)
  useEffect(() => {
    const mq = window.matchMedia('(pointer: coarse)')
    setPhone(mq.matches)
    const on = (e: MediaQueryListEvent) => setPhone(e.matches)
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [])
  return phone
}

export function CaptureFlow({ api, submissionId, initialPages, copy, onState, primaryCamera }: {
  api: CapturePagesApi
  submissionId: string
  initialPages: PageView[]
  copy: FlowCopy
  onState?: (s: CaptureFlowState) => void
  /** Label for the camera button once a page exists («צילום העמוד הבא»). */
  primaryCamera?: boolean
}) {
  const phone = usePhone()
  const [pages, setPages] = useState<PageView[]>(initialPages)
  const [local, setLocal] = useState<Record<string, string>>({})
  const [selected, setSelected] = useState<string | null>(initialPages.at(-1)?.page_id ?? null)
  const [notice, setNotice] = useState<string | null>(null)
  const cameraRef = useRef<HTMLInputElement>(null)
  const filesRef = useRef<HTMLInputElement>(null)

  useEffect(() => { setPages(initialPages) }, [submissionId]) // eslint-disable-line react-hooks/exhaustive-deps

  const refresh = useCallback(async () => {
    const sub = await api.getSubmission(submissionId)
    setPages(sub.pages)
  }, [api, submissionId])

  const uploads = useCaptureUploads({
    api, submissionId,
    onPageReady: (page, objectUrl) => {
      setPages((ps) => [...ps.filter((p) => p.page_id !== page.page_id), page]
        .sort((a, b) => a.position - b.position))
      setLocal((m) => ({ ...m, [page.page_id]: objectUrl }))
      setSelected(page.page_id)
    },
  })

  const awaiting = pages.filter((p) => p.status === 'awaiting_upload').length
  useEffect(() => {
    onState?.({ pageCount: pages.length, pending: uploads.pending, awaiting,
                firstPage: pages[0] ?? null })
  }, [pages, uploads.pending, awaiting, onState])

  const room = MAX_PAGES - pages.length - uploads.pending
  const full = room <= 0

  const onFiles = (list: FileList | null) => {
    setNotice(null)
    if (!list || list.length === 0) return
    const accepted = orderFiles(Array.from(list))                       // D15
      .map((file) => ({ file, contentType: contentTypeOf(file) }))
      .filter((f): f is { file: File; contentType: NonNullable<typeof f.contentType> } => f.contentType !== null)
    if (accepted.length < list.length) setNotice(copy.unsupportedFile)
    if (accepted.length > room) setNotice(copy.maxPages)
    uploads.enqueue(accepted.slice(0, Math.max(0, room)))
  }

  const replacePage = (page: PageView) =>
    setPages((ps) => ps.map((p) => (p.page_id === page.page_id ? page : p)))

  const selectedPage = pages.find((p) => p.page_id === selected) ?? null

  const strip: StripPage[] = useMemo(() => [
    ...pages.map((p) => ({
      key: p.page_id, page: p, localSrc: local[p.page_id],
      state: (p.status === 'awaiting_upload' ? 'incomplete'
        : p.quality?.verdict === 'warn' ? 'warning' : 'ready') as StripPage['state'],
    })),
    ...uploads.items.map((it) => ({
      key: it.key, localSrc: it.objectUrl,
      state: (it.step === 'failed' || it.step === 'refused' ? 'failed' : 'uploading') as StripPage['state'],
    })),
  ], [pages, local, uploads.items])

  const removePage = async (pageId: string) => {
    await api.deletePage(submissionId, pageId)
    setSelected(null)
    await refresh()
  }

  const move = async (key: string, delta: -1 | 1) => {
    const ids = pages.map((p) => p.page_id)
    const i = ids.indexOf(key)
    const j = i + delta
    if (i < 0 || j < 0 || j >= ids.length) return
    ;[ids[i], ids[j]] = [ids[j], ids[i]]
    await api.reorder(submissionId, ids)
    await refresh()
  }

  const failed = uploads.items.filter((it) => it.step === 'failed' || it.step === 'refused')

  return (
    <div className="space-y-4" dir="rtl">
      <div className="flex flex-wrap gap-2">
        {phone && (
          <button type="button" disabled={full} onClick={() => cameraRef.current?.click()}
                  className="flex min-h-[48px] flex-1 items-center justify-center gap-2 rounded-xl bg-primary-600 px-4 text-white disabled:opacity-50">
            <Camera size={18} />{pages.length > 0 && primaryCamera ? copy.nextPage : copy.camera}
          </button>
        )}
        <button type="button" disabled={full} onClick={() => filesRef.current?.click()}
                className={`flex min-h-[48px] flex-1 items-center justify-center gap-2 rounded-xl border px-4 disabled:opacity-50 ${
                  phone ? 'border-surface-300 text-gray-700' : 'border-primary-600 bg-primary-600 text-white'}`}>
          <ImagePlus size={18} />{copy.gallery}
        </button>
        {/* JPEG listed FIRST so iOS transcodes HEIC on capture (§8.1). */}
        <input ref={cameraRef} type="file" accept={ACCEPT_ATTR} capture="environment" hidden
               onChange={(e) => { onFiles(e.target.files); e.target.value = '' }} />
        <input ref={filesRef} type="file" accept={ACCEPT_ATTR} multiple hidden
               onChange={(e) => { onFiles(e.target.files); e.target.value = '' }} />
      </div>
      {(full || notice) && <p className="text-sm text-amber-700" role="status">{full ? copy.maxPages : notice}</p>}

      {failed.map((it) => (
        <div key={it.key} className="flex items-center gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
          <span className="flex-1">{it.error || copy.uploadFailed}</span>
          {it.step === 'failed' && (
            <button type="button" onClick={() => uploads.retry(it.key)} className="flex items-center gap-1 underline">
              <RotateCcw size={14} />{copy.retry}
            </button>
          )}
          <button type="button" aria-label={copy.remove} onClick={() => {
            if (it.pageId) void api.deletePage(submissionId, it.pageId).then(refresh).catch(() => undefined)
            uploads.discard(it.key)
          }}><X size={16} /></button>
        </div>
      ))}

      {strip.length === 0 ? (
        <p className="py-6 text-center text-sm text-gray-500">{copy.noPagesYet}</p>
      ) : (
        <PageStrip pages={strip} selectedKey={selected} copy={copy}
                   onSelect={setSelected} onMove={(k, d) => void move(k, d)} />
      )}

      {selectedPage && selectedPage.status !== 'awaiting_upload' && (
        <CornerEditor
          page={selectedPage}
          localSrc={local[selectedPage.page_id]}
          copy={copy}
          onCorners={(q: Quad) => void api.patchPage(submissionId, selectedPage.page_id, { corners: q })
            .then(replacePage).catch(() => refresh())}
          onRotate={(r: Rotation) => void api.patchPage(submissionId, selectedPage.page_id, { rotation: r })
            .then(replacePage)}
          onReset={(to) => void api.resetCorners(submissionId, selectedPage.page_id, to).then(replacePage)}
          onRetake={() => { void removePage(selectedPage.page_id); cameraRef.current?.click() }}
          onRemove={() => void removePage(selectedPage.page_id)}
        />
      )}
      {selectedPage && selectedPage.status === 'awaiting_upload' && (
        <div className="flex items-center gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">
          <span className="flex-1">{copy.uploadIncomplete}</span>
          <button type="button" onClick={() => void removePage(selectedPage.page_id)} className="underline">{copy.remove}</button>
        </div>
      )}
    </div>
  )
}
