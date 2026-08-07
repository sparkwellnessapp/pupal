'use client';

/**
 * Thin React adapter over ReviewItemController (where the ruled state machine
 * lives, framework-free and node-testable). See reviewItemController.ts for
 * the Δ4/Δ11/Δ14 rules.
 */

import { useEffect, useRef, useSyncExternalStore } from 'react';

import type { BatchTranscriptionItem } from '@/types/batch';
import {
  ReviewItemController,
  type ReviewItemSnapshot,
  type SaveFn,
} from './reviewItemController';

export interface ReviewItemState extends ReviewItemSnapshot {
  onAnswerChange: (key: string, text: string) => void;
  onStudentPick: (id: string) => void;
  buildAnswers: ReviewItemController['buildAnswers'];
  flushIfDirty: ReviewItemController['flushIfDirty'];
  markAccepted: () => void;
}

export function useReviewItemState(
  item: BatchTranscriptionItem,
  save: SaveFn,
): ReviewItemState {
  const ctrlRef = useRef<ReviewItemController | null>(null);
  ctrlRef.current ??= new ReviewItemController(item, save);
  const ctrl = ctrlRef.current;

  // Δ11 guard lives in the controller: same-id refresh is a no-op.
  useEffect(() => { ctrl.maybeRehydrate(item); }, [ctrl, item]);

  const snapshot = useSyncExternalStore(ctrl.subscribe, ctrl.getSnapshot, ctrl.getSnapshot);

  return {
    ...snapshot,
    onAnswerChange: ctrl.onAnswerChange,
    onStudentPick: ctrl.onStudentPick,
    buildAnswers: ctrl.buildAnswers,
    flushIfDirty: ctrl.flushIfDirty,
    markAccepted: ctrl.markAccepted,
  };
}
