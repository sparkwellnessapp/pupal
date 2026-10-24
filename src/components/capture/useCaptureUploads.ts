'use client'

/**
 * useCaptureUploads — the capture upload queue (§8.1).
 *
 * Per photo: create page (the server's slot, SCN-1) → PUT straight to GCS on
 * the signed URL (retry ×3 on network errors) → `uploaded` (the server checks
 * the object exists, SCN-6, and analyzes it) → a PageView. Concurrency 3.
 *
 * SAVE IS GATED HERE: `pending` counts every photo not yet confirmed, and a
 * page the server still reports `awaiting_upload` (a reload lost its file)
 * counts too — the caller adds those from the server list, which is the
 * truth after a reload.
 *
 * Backgrounding a phone kills fetches; on `visibilitychange` → visible every
 * network-failed item is resumed from the step that failed. A PUT refused
 * because its signed URL EXPIRED (the phone slept past 15 minutes) is not a
 * verdict on the photo: the stale page is dropped and the item starts over
 * with a fresh one. Any other refusal (the page cap, a server 4xx) is
 * terminal for that item and never auto-retried. `pending` counts what is
 * still on its way; `failed` what needs her (retry or remove) — both block a
 * save, and they are reported apart so the screen says which.
 */
import { useCallback, useEffect, useRef, useState } from 'react'

import { CaptureApiError, putPhoto, type CapturePagesApi } from '@/lib/capture-api'
import type { CaptureContentType, PageView } from '@/types/capture'

export type UploadStep = 'queued' | 'creating' | 'uploading' | 'confirming' | 'failed' | 'refused'

export interface LocalUpload {
  key: string
  file: File
  contentType: CaptureContentType
  objectUrl: string
  step: UploadStep
  pageId?: string
  uploadUrl?: string
  headers?: Record<string, string>
  error?: string
  /** where to resume after a network failure */
  resumeAt?: 'create' | 'put' | 'confirm'
  /** the caller's own label, handed back with the ready page (a retake's target) */
  tag?: string
}

const CONCURRENCY = 3

export function useCaptureUploads({ api, submissionId, onPageReady }: {
  api: CapturePagesApi
  submissionId: string | null
  onPageReady: (page: PageView, objectUrl: string, tag?: string) => void
}) {
  const [items, setItems] = useState<LocalUpload[]>([])
  const itemsRef = useRef<LocalUpload[]>([])
  const running = useRef(0)
  const readyRef = useRef(onPageReady)
  readyRef.current = onPageReady

  const update = useCallback((key: string, patch: Partial<LocalUpload>) => {
    itemsRef.current = itemsRef.current.map((it) => (it.key === key ? { ...it, ...patch } : it))
    setItems(itemsRef.current)
  }, [])

  const remove = useCallback((key: string) => {
    itemsRef.current = itemsRef.current.filter((it) => it.key !== key)
    setItems(itemsRef.current)
  }, [])

  const runOne = useCallback(async (key: string) => {
    if (!submissionId) return
    const get = () => itemsRef.current.find((it) => it.key === key)
    let it = get()
    if (!it) return
    try {
      if (!it.pageId || it.resumeAt === 'create') {
        update(key, { step: 'creating', error: undefined })
        const created = await api.createPage(submissionId, it.contentType)
        update(key, { pageId: created.page_id, uploadUrl: created.upload_url,
                      headers: created.required_headers, resumeAt: 'put' })
        it = get()!
      }
      if (it.resumeAt !== 'confirm') {
        update(key, { step: 'uploading', error: undefined })
        await putPhoto(it.uploadUrl!, it.headers ?? {}, it.file)
        update(key, { resumeAt: 'confirm' })
        it = get()!
      }
      update(key, { step: 'confirming', error: undefined })
      const page = await api.confirmUpload(submissionId, it.pageId!)
      readyRef.current(page, it.objectUrl, it.tag)
      remove(key)
    } catch (err) {
      const e = err instanceof CaptureApiError ? err : null
      const cur = get()
      if (e?.code === 'upload_refused' && [400, 401, 403].includes(e.status) && cur?.pageId) {
        // The signed URL expired (or its signature no longer holds): drop the
        // stale page and start over with a fresh one — retryable, not refused.
        void api.deletePage(submissionId, cur.pageId).catch(() => undefined)
        update(key, { step: 'failed', error: undefined, pageId: undefined, uploadUrl: undefined,
                      headers: undefined, resumeAt: 'create' })
        return
      }
      const network = !e || e.code === 'network'
      update(key, {
        step: network ? 'failed' : 'refused',
        error: e?.messageHe || undefined,
        resumeAt: cur?.resumeAt ?? 'create',
      })
    }
  }, [api, submissionId, update, remove])

  const pump = useCallback(() => {
    while (running.current < CONCURRENCY) {
      const next = itemsRef.current.find((it) => it.step === 'queued')
      if (!next) return
      running.current += 1
      update(next.key, { step: 'creating' })
      void runOne(next.key).finally(() => {
        running.current -= 1
        pump()
      })
    }
  }, [runOne, update])

  const enqueue = useCallback((files: { file: File; contentType: CaptureContentType; tag?: string }[]) => {
    const fresh = files.map(({ file, contentType, tag }) => ({
      key: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      file, contentType, objectUrl: URL.createObjectURL(file), step: 'queued' as const,
      resumeAt: 'create' as const, tag,
    }))
    itemsRef.current = [...itemsRef.current, ...fresh]
    setItems(itemsRef.current)
    pump()
  }, [pump])

  const retry = useCallback((key: string) => {
    update(key, { step: 'queued' })
    pump()
  }, [pump, update])

  const discard = useCallback((key: string) => {
    const it = itemsRef.current.find((x) => x.key === key)
    if (it) URL.revokeObjectURL(it.objectUrl)
    remove(key)
  }, [remove])

  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState !== 'visible') return
      let any = false
      for (const it of itemsRef.current) {
        if (it.step === 'failed') { update(it.key, { step: 'queued' }); any = true }
      }
      if (any) pump()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => document.removeEventListener('visibilitychange', onVisible)
  }, [pump, update])

  // Photos still in the queue when the flow goes away: their previews are
  // released (a ready page's URL belongs to the flow, which releases it).
  useEffect(() => () => {
    for (const it of itemsRef.current) URL.revokeObjectURL(it.objectUrl)
  }, [])

  const failed = items.filter((it) => it.step === 'failed' || it.step === 'refused').length
  return { items, enqueue, retry, discard, pending: items.length - failed, failed }
}
