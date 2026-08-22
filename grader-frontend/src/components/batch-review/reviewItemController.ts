/**
 * Per-item review state machine: hydration, dirty-gating, the overlay flush,
 * and post-accept suppression — FRAMEWORK-FREE so the ruled behaviors are
 * unit-testable in the node-env vitest suite (plan Δ4, Δ11, Δ14, Δ12).
 * `useReviewItemState` is the thin React adapter.
 *
 * Rules owned here:
 *  - HYDRATION (overlay-over-draft): editor text comes from the saved overlay
 *    when present, else the draft; student from overlay.student_id, else the
 *    auto-match pre-seed. Re-hydration happens ONLY when the item IDENTITY
 *    (transcription_id) changes — a payload refresh of the same item must
 *    never clobber in-progress edits (Δ11).
 *  - DIRT (Δ14): only a keystroke in an answer editor or an explicit picker
 *    change counts. Hydration and the matched-student pre-seed are NOT dirt —
 *    viewing must never create an overlay.
 *  - FLUSH: `flushIfDirty` saves the FULL snapshot (draft key order); false on
 *    failure — the caller blocks navigation. Not dirty → no request at all.
 *  - SUPPRESSION (Δ4): after a successful accept, every overlay PATCH for the
 *    item is suppressed — flushIfDirty no-ops forever for this item.
 */

import type { TranscriptionReview, TranscriptionReviewSaveRequest } from '@/lib/api';
import type { BatchTranscriptionItem } from '@/types/batch';
import { answerTargetId } from '@/utils/review-flags';

export type SaveFn = (
  transcriptionId: string,
  body: TranscriptionReviewSaveRequest,
) => Promise<TranscriptionReview>;

export interface ReviewAnswerInput {
  question_number: number;
  sub_question_id: string | null;
  answer_text: string;
}

export interface ReviewItemSnapshot {
  editedAnswers: Readonly<Record<string, string>>;
  /** Display provenance per key (page-jump chips). Initialized from the
   *  draft; SWAPPED alongside text on reassignment so chips keep pointing at
   *  the moved content's source pages. Session-scoped display state — not
   *  persisted (a save+refresh reverts chips to draft provenance; known
   *  minor limitation of the reassignment feature). */
  pageNumbers: Readonly<Record<string, number[]>>;
  studentId: string | null;
  dirty: boolean;
  saving: boolean;
  saveError: string | null;
  /** True after at least one successful flush for the current item. */
  saved: boolean;
  accepted: boolean;
}

function hydrateAnswers(item: BatchTranscriptionItem): Record<string, string> {
  // R7: an APPROVED item hydrates from the FROZEN contract's answers (B6) —
  // what was actually committed — never the draft or the overlay (nulled at
  // approval; a stale one must not resurface). Overlay-over-draft remains the
  // fallback for legacy approved rows that predate the approved_answers field.
  const fromApproved = new Map<string, string>();
  if (item.transcription_status === 'approved') {
    for (const a of item.approved_answers ?? []) {
      fromApproved.set(
        answerTargetId({ question_number: a.question_number, sub_question_id: a.sub_question_id ?? null }),
        a.answer_text,
      );
    }
  }
  const fromOverlay = new Map<string, string>();
  for (const a of item.review?.answers ?? []) {
    fromOverlay.set(
      answerTargetId({ question_number: a.question_number, sub_question_id: a.sub_question_id ?? null }),
      a.answer_text,
    );
  }
  const out: Record<string, string> = {};
  for (const a of item.draft.answers) {
    const key = answerTargetId(a);
    out[key] = fromApproved.get(key) ?? fromOverlay.get(key) ?? a.answer_text;
  }
  return out;
}

/**
 * Rider-1 amended OD-8 ruling: the browser-unload guard fires when there is
 * actually something to lose — the item is DIRTY, or a save is in-flight or
 * failed. (The original in-flight/failed-only rule left a hole: typing and
 * closing the tab without navigating lost the edits with no warning, because
 * autosave-on-navigate never fires without a navigation.) An accepted item has
 * nothing to lose — PATCHes are suppressed (Δ4) — so it never guards.
 */
export function needsUnloadGuard(
  s: Pick<ReviewItemSnapshot, 'dirty' | 'saving' | 'saveError' | 'accepted'>,
): boolean {
  if (s.accepted) return false;
  return s.dirty || s.saving || s.saveError !== null;
}

export class ReviewItemController {
  private item: BatchTranscriptionItem;
  private readonly save: SaveFn;
  private snapshot: ReviewItemSnapshot;
  private readonly listeners = new Set<() => void>();

  constructor(item: BatchTranscriptionItem, save: SaveFn) {
    this.item = item;
    this.save = save;
    this.snapshot = ReviewItemController.hydrated(item);
  }

  private static hydrated(item: BatchTranscriptionItem): ReviewItemSnapshot {
    const pageNumbers: Record<string, number[]> = {};
    for (const a of item.draft.answers) {
      pageNumbers[answerTargetId(a)] = a.page_numbers;
    }
    return {
      editedAnswers: hydrateAnswers(item),
      pageNumbers,
      studentId: item.review?.student_id ?? item.matched_student_id ?? null,
      dirty: false,
      saving: false,
      saveError: null,
      saved: false,
      accepted: item.transcription_status === 'approved',
    };
  }

  getSnapshot = (): ReviewItemSnapshot => this.snapshot;

  subscribe = (fn: () => void): (() => void) => {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  };

  private set(patch: Partial<ReviewItemSnapshot>): void {
    this.snapshot = { ...this.snapshot, ...patch };
    this.listeners.forEach((fn) => fn());
  }

  /** Δ11 guard: re-hydrate ONLY on item-identity change; same-id payload
   *  refreshes are ignored entirely. */
  maybeRehydrate(item: BatchTranscriptionItem): void {
    if (item.transcription_id === this.item.transcription_id) return;
    this.item = item;
    this.snapshot = ReviewItemController.hydrated(item);
    this.listeners.forEach((fn) => fn());
  }

  onAnswerChange = (key: string, text: string): void => {
    this.set({
      editedAnswers: { ...this.snapshot.editedAnswers, [key]: text },
      dirty: true,
      saved: false,
    });
  };

  onStudentPick = (id: string): void => {
    this.set({ studentId: id, dirty: true, saved: false });
  };

  /**
   * Reassignment (2026-08-07, owner-ruled SWAP semantics): exchange the two
   * containers' texts — never overwrite, so no block can be lost and a chain
   * of misassignments resolves in any click order. Keys stay frozen (the
   * overlay's full-snapshot key-multiset rule); only content moves. Display
   * provenance (page chips) travels with the content.
   */
  swapAnswers = (keyA: string, keyB: string): void => {
    if (this.snapshot.accepted || keyA === keyB) return;
    const ea = { ...this.snapshot.editedAnswers };
    [ea[keyA], ea[keyB]] = [ea[keyB] ?? '', ea[keyA] ?? ''];
    const pn = { ...this.snapshot.pageNumbers };
    [pn[keyA], pn[keyB]] = [pn[keyB] ?? [], pn[keyA] ?? []];
    this.set({ editedAnswers: ea, pageNumbers: pn, dirty: true, saved: false });
  };

  /** Full snapshot in draft key order — the flush body and the accept body. */
  buildAnswers = (): ReviewAnswerInput[] => {
    return this.item.draft.answers.map((a) => ({
      question_number: a.question_number,
      sub_question_id: a.sub_question_id,
      answer_text: this.snapshot.editedAnswers[answerTargetId(a)] ?? a.answer_text,
    }));
  };

  /** True = safe to navigate. False = save failed; navigation must block. */
  flushIfDirty = async (): Promise<boolean> => {
    if (this.snapshot.accepted) return true;  // Δ4: suppressed after accept
    if (!this.snapshot.dirty) return true;    // Δ14: viewing never creates an overlay
    this.set({ saving: true, saveError: null });
    try {
      await this.save(this.item.transcription_id, {
        answers: this.buildAnswers(),
        student_id: this.snapshot.studentId,
      });
      this.set({ saving: false, dirty: false, saved: true });
      return true;
    } catch (e) {
      this.set({
        saving: false,
        saveError: e instanceof Error ? e.message : 'השמירה נכשלה',
      });
      return false;                           // failed save BLOCKS navigation (OD-8)
    }
  };

  /** Call after a successful accept — suppresses all further PATCHes (Δ4). */
  markAccepted = (): void => {
    this.set({ accepted: true, dirty: false });
  };
}
