'use client'

/**
 * CaptureFlow — the shared core of both capture pages (§8.1). It owns the
 * page list, the capture inputs, the upload queue and the corner editor; it
 * owns NO auth (it is handed an API adapter) and no save button (each page
 * gates its own save on the state this reports — SCN-6, and SCN-8 on the
 * teacher page).
 *
 * The server's page list is the truth: after a reload, a page still
 * `awaiting_upload` lost its file and says so (retake or remove). A page the
 * queue is still uploading is the QUEUE's to show until it is ready — a
 * refresh mid-upload must not also list it as a broken server page.
 *
 * Every edit request in flight (corners, rotation, reset, order, delete)
 * counts as pending, so a save can never freeze a version missing her last
 * change.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Camera, ImagePlus, RotateCcw, X } from 'lucide-react'

import type { FlowCopy } from '@/copy/capture'
import type { CapturePagesApi } from '@/lib/capture-api'
import type { PageView, Quad, Rotation } from '@/types/capture'
import { ACCEPT_ATTR, MAX_FILE_BYTES, contentTypeOf, orderFiles } from '@/utils/capture-files'

import { CornerEditor } from './CornerEditor'
import { PageStrip, type StripPage } from './PageStrip'
import { useCaptureUploads } from './useCaptureUploads'

export interface CaptureFlowState {
  pageCount: number
  /** photos still on their way, plus edit requests still in flight */
  pending: number
  /** photos whose upload failed or was refused — she retries or removes them */
  failed: number
  /** server pages that never finished uploading — they block a save too */
  awaiting: number
  firstPage: PageView | null
}

const MAX_PAGES = 20
// Display URLs are signed for 15 minutes (SCN-11): re-read before they lapse.
const PREVIEW_REFRESH_MS = 10 * 60_000
const IMAGE_ERROR_REFRESH_GAP_MS = 60_000

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
  const [edits, setEdits] = useState(0)
  const cameraRef = useRef<HTMLInputElement>(null)
  const filesRef = useRef<HTMLInputElement>(null)
  // The page a «צילום מחדש» replaces — kept until its new photo is READY, so
  // a cancelled camera loses nothing.
  const retakeOf = useRef<string | null>(null)
  const inFlightIds = useRef<Set<string>>(new Set())
  const lastImageRefresh = useRef(0)
  const localRef = useRef(local)
  localRef.current = local

  const refresh = useCallback(async () => {
    const sub = await api.getSubmission(submissionId)
    setPages(sub.pages.filter((p) => !inFlightIds.current.has(p.page_id)))
  }, [api, submissionId])

  /** Run one edit request: counted as pending while it flies; on failure the
   *  server's state is re-read and she is told — never a silent rejection. */
  const edit = useCallback(async <T,>(fn: () => Promise<T>): Promise<T | undefined> => {
    setEdits((n) => n + 1)
    try {
      return await fn()
    } catch {
      setNotice(copy.actionFailed)
      await refresh().catch(() => undefined)
      return undefined
    } finally {
      setEdits((n) => n - 1)
    }
  }, [copy.actionFailed, refresh])

  const finishRetake = useCallback(async (oldId: string, fresh: PageView) => {
    await edit(async () => {
      await api.deletePage(submissionId, oldId)
      const current = await api.getSubmission(submissionId)
      const ids = current.pages.map((p) => p.page_id).filter((id) => id !== fresh.page_id)
      const at = pages.findIndex((p) => p.page_id === oldId)
      if (at >= 0 && ids.length >= at) {
        ids.splice(at, 0, fresh.page_id)
        if (ids.length === current.pages.length) await api.reorder(submissionId, ids)
      }
      await refresh()
    })
  }, [api, edit, pages, refresh, submissionId])

  const uploads = useCaptureUploads({
    api, submissionId,
    onPageReady: (page, objectUrl, tag) => {
      setPages((ps) => [...ps.filter((p) => p.page_id !== page.page_id), page]
        .sort((a, b) => a.position - b.position))
      setLocal((m) => ({ ...m, [page.page_id]: objectUrl }))
      setSelected(page.page_id)
      if (tag) void finishRetake(tag, page)
    },
  })
  // Rebuilt every render from the queue itself, so a discarded item can never
  // leave its page hidden from the list (and from the save gate) for good.
  inFlightIds.current = new Set(uploads.items.flatMap((it) => (it.pageId ? [it.pageId] : [])))

  // The SERVER's page list on every mount: `initialPages` is the parent's
  // copy and goes stale the moment pages are added here — switching groups on
  // the teacher page, or «הוספה או החלפה» after a save, remounts this with it.
  useEffect(() => {
    setPages(initialPages)
    void refresh().catch(() => undefined)
    const t = setInterval(() => { void refresh().catch(() => undefined) }, PREVIEW_REFRESH_MS)
    return () => clearInterval(t)
  }, [submissionId]) // eslint-disable-line react-hooks/exhaustive-deps

  // Release this device's photo URLs when the flow goes away.
  useEffect(() => () => { for (const u of Object.values(localRef.current)) URL.revokeObjectURL(u) }, [])

  const awaiting = pages.filter((p) => p.status === 'awaiting_upload').length
  useEffect(() => {
    onState?.({ pageCount: pages.length, pending: uploads.pending + edits, failed: uploads.failed,
                awaiting, firstPage: pages[0] ?? null })
  }, [pages, uploads.pending, uploads.failed, edits, awaiting, onState])

  const room = MAX_PAGES - pages.length - uploads.pending - uploads.failed
  const full = room <= 0

  const onFiles = (list: FileList | null) => {
    setNotice(null)
    const replacing = retakeOf.current
    retakeOf.current = null
    if (!list || list.length === 0) return
    const typed = orderFiles(Array.from(list))                          // D15
      .map((file) => ({ file, contentType: contentTypeOf(file) }))
      .filter((f): f is { file: File; contentType: NonNullable<typeof f.contentType> } => f.contentType !== null)
    const accepted = typed.filter((f) => f.file.size <= MAX_FILE_BYTES)
    if (typed.length < list.length) setNotice(copy.unsupportedFile)
    else if (accepted.length < typed.length) setNotice(copy.tooLarge)
    if (replacing && accepted.length > 0) {
      // A retake replaces ONE page: its photo takes the old page's place.
      uploads.enqueue([{ ...accepted[0], tag: replacing }])
      return
    }
    if (accepted.length > room) setNotice(copy.maxPages)
    uploads.enqueue(accepted.slice(0, Math.max(0, room)))
  }

  const openCamera = () => { retakeOf.current = null; cameraRef.current?.click() }
  const openFiles = () => { retakeOf.current = null; filesRef.current?.click() }

  const replacePage = (page: PageView | undefined) => {
    if (page) setPages((ps) => ps.map((p) => (p.page_id === page.page_id ? page : p)))
  }

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

  const removePage = (pageId: string) => edit(async () => {
    await api.deletePage(submissionId, pageId)
    setSelected(null)
    await refresh()
  })

  const move = (key: string, delta: -1 | 1) => edit(async () => {
    const ids = pages.map((p) => p.page_id)
    const i = ids.indexOf(key)
    const j = i + delta
    if (i < 0 || j < 0 || j >= ids.length) return
    ;[ids[i], ids[j]] = [ids[j], ids[i]]
    await api.reorder(submissionId, ids)
    await refresh()
  })

  const onImageError = () => {
    const now = Date.now()
    if (now - lastImageRefresh.current < IMAGE_ERROR_REFRESH_GAP_MS) return
    lastImageRefresh.current = now
    void refresh().catch(() => undefined)
  }

  const failedItems = uploads.items.filter((it) => it.step === 'failed' || it.step === 'refused')
  // Reordering while a photo is still landing would send an order that is
  // missing its page — the server refuses it (order_mismatch).
  const canMove = uploads.pending === 0 && edits === 0

  return (
    <div className="space-y-4" dir="rtl">
      <div className="flex flex-wrap gap-2">
        {phone && (
          <button type="button" disabled={full} onClick={openCamera}
                  className="flex min-h-[48px] flex-1 items-center justify-center gap-2 rounded-xl bg-primary-600 px-4 text-white disabled:opacity-50">
            <Camera size={18} />{pages.length > 0 && primaryCamera ? copy.nextPage : copy.camera}
          </button>
        )}
        <button type="button" disabled={full} onClick={openFiles}
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
      {(full || notice) && <p className="text-sm text-amber-700" role="status">{notice ?? copy.maxPages}</p>}

      {failedItems.map((it) => (
        <div key={it.key} className="flex items-center gap-2 rounded-lg bg-red-50 px-3 py-1 text-sm text-red-800" role="alert">
          <span className="flex-1">{it.error || copy.uploadFailed}</span>
          {it.step === 'failed' && (
            <button type="button" onClick={() => uploads.retry(it.key)}
                    className="flex min-h-[44px] items-center gap-1 px-2 underline">
              <RotateCcw size={14} />{copy.retry}
            </button>
          )}
          <button type="button" aria-label={copy.remove}
                  className="flex h-11 w-11 items-center justify-center"
                  onClick={() => {
                    if (it.pageId) void api.deletePage(submissionId, it.pageId).then(refresh).catch(() => undefined)
                    uploads.discard(it.key)
                  }}><X size={16} /></button>
        </div>
      ))}

      {strip.length === 0 ? (
        <p className="py-6 text-center text-sm text-gray-500">{copy.noPagesYet}</p>
      ) : (
        <PageStrip pages={strip} selectedKey={selected} copy={copy} canMove={canMove}
                   onSelect={setSelected} onMove={(k, d) => void move(k, d)} />
      )}

      {selectedPage && selectedPage.status !== 'awaiting_upload' && (
        <CornerEditor
          page={selectedPage}
          localSrc={local[selectedPage.page_id]}
          copy={copy}
          onImageError={onImageError}
          onCorners={(q: Quad) => void edit(() => api.patchPage(submissionId, selectedPage.page_id, { corners: q }))
            .then(replacePage)}
          onRotate={(r: Rotation) => void edit(() => api.patchPage(submissionId, selectedPage.page_id, { rotation: r }))
            .then(replacePage)}
          onReset={(to) => void edit(() => api.resetCorners(submissionId, selectedPage.page_id, to)).then(replacePage)}
          onRetake={() => { retakeOf.current = selectedPage.page_id; cameraRef.current?.click() }}
          onRemove={() => void removePage(selectedPage.page_id)}
        />
      )}
      {selectedPage && selectedPage.status === 'awaiting_upload' && (
        <div className="flex items-center gap-2 rounded-lg bg-red-50 px-3 py-1 text-sm text-red-800">
          <span className="flex-1">{copy.uploadIncomplete}</span>
          <button type="button" onClick={() => void removePage(selectedPage.page_id)}
                  className="min-h-[44px] px-2 underline">{copy.remove}</button>
        </div>
      )}
    </div>
  )
}
