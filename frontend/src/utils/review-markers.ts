/**
 * The markers `F` walks (spec §4.2 R9).
 *
 * R9 names SIX deterministic marker kinds, not one:
 *   evidence that did not validate (`not_found` / `fuzzy`)   — per CHECK
 *   bounds-clamped, closed-world                             — per TERMINAL flag
 *   `skipped_no_answer`, `failed`                            — per SCOPE
 *   audit-marked                                             — deferred (R-1)
 *
 * An earlier version walked only the evidence markers, so `F` silently skipped
 * a clamped terminal and a failed question — the two markers that most need her
 * eye, because neither is visible in the score. A key that claims to take her
 * to "the next thing to check" and quietly omits kinds of thing is worse than
 * no key: it teaches her the page has been swept when it has not.
 *
 * MARKERS NEVER BLOCK APPROVAL (R9). They route attention; they do not gate.
 *
 * The counting rule matches `look-count.ts` (and the backend `look_count.py`)
 * exactly — one marker per DISTINCT (anchor, reason) — so the number on the
 * dashboard card and the number of stops `F` makes cannot disagree.
 */

import type { LookCountDraft, LookCountLeaf } from './look-count';

export type MarkerReason =
    | 'not_found'
    | 'fuzzy'
    | 'bounds_clamped'
    | 'closed_world_violation'
    | 'unverified_check'
    | 'evidence_unverified'
    | 'skipped_no_answer'
    | 'failed';

export interface ReviewMarker {
    /**
     * Unique per marker, because `id` is NOT.
     *
     * One terminal can carry two different flags (clamped AND closed-world),
     * producing two markers that share an id. Walking by id then finds the
     * first one every time and `F` ping-pongs between two stops forever,
     * stranding every later marker on the page — a key that claims to sweep
     * and silently cannot.
     */
    key: string;
    /** `check` focuses a row; `scope` scrolls to the section. */
    kind: 'check' | 'scope';
    /** check_id, terminal_id or scope id, depending on `kind`. */
    id: string;
    /** The scope this marker sits in — what the nav highlights. */
    scopeId: string;
    reason: MarkerReason;
}

const LOOK_FLAGS: ReadonlySet<string> = new Set([
    'bounds_clamped', 'closed_world_violation', 'unverified_check', 'evidence_unverified',
]);
const V3_QUOTE_FLAGS: ReadonlySet<string> = new Set(['quote_not_found', 'fuzzy_match']);
const UNVALIDATED: ReadonlySet<string> = new Set(['not_found', 'fuzzy']);

function scopeKey(scope: { question_id: string; sub_question_id?: string | null }): string {
    return scope.sub_question_id == null
        ? scope.question_id
        : `${scope.question_id}.${scope.sub_question_id}`;
}

/**
 * Every marker in DOCUMENT ORDER — the order she reads, so `F` moves down the
 * page rather than jumping around it.
 */
export function reviewMarkers(draft: LookCountDraft): ReviewMarker[] {
    const out: ReviewMarker[] = [];
    const seen = new Set<string>();
    const push = (marker: Omit<ReviewMarker, 'key'>) => {
        const key = `${marker.kind}:${marker.id}:${marker.reason}`;
        if (seen.has(key)) return;
        seen.add(key);
        out.push({ ...marker, key });
    };

    for (const scope of draft.scope_outcomes ?? []) {
        // Never owed, so never a stop — the same exclusion look_count makes.
        if (scope.graded_by === 'excluded_by_selection') continue;
        const sid = scopeKey(scope);

        if (scope.graded_by === 'skipped_no_answer' || scope.graded_by === 'failed') {
            push({ kind: 'scope', id: sid, scopeId: sid, reason: scope.graded_by });
            continue;
        }

        for (const criterion of scope.criterion_outcomes ?? []) {
            const leaves: LookCountLeaf[] = criterion.sub_criterion_outcomes?.length
                ? criterion.sub_criterion_outcomes
                : [criterion];
            for (const leaf of leaves) {
                const terminalId = leaf.sub_criterion_id || criterion.criterion_id;
                const hasChecks = Boolean(leaf.checks && leaf.checks.length > 0);
                for (const flag of leaf.flags ?? []) {
                    if (LOOK_FLAGS.has(flag.reason)) {
                        push({
                            kind: 'scope', id: terminalId, scopeId: sid,
                            reason: flag.reason as MarkerReason,
                        });
                    } else if (V3_QUOTE_FLAGS.has(flag.reason) && !hasChecks) {
                        // v3 leaves carry quote problems only as flags; a v5
                        // leaf would otherwise be counted twice.
                        push({
                            kind: 'scope', id: terminalId, scopeId: sid,
                            reason: flag.reason === 'quote_not_found' ? 'not_found' : 'fuzzy',
                        });
                    }
                }
                for (const check of leaf.checks ?? []) {
                    if (check.quote_status && UNVALIDATED.has(check.quote_status)) {
                        push({
                            kind: 'check', id: check.check_id, scopeId: sid,
                            reason: check.quote_status as MarkerReason,
                        });
                    }
                }
            }
        }
    }
    return out;
}

/**
 * The next marker after `currentKey`, wrapping.
 *
 * Keyed, not id'd — see `ReviewMarker.key`. Wrapping is deliberate: `F` means
 * "show me the next thing to look at", and stopping dead at the last marker
 * would leave her hunting for the first one by hand on a thirty-paper evening.
 */
export function nextMarker(
    markers: readonly ReviewMarker[],
    currentKey: string | null,
): ReviewMarker | null {
    if (markers.length === 0) return null;
    const at = currentKey === null ? -1 : markers.findIndex((m) => m.key === currentKey);
    return markers[(at + 1) % markers.length];
}

/** How many markers sit in each scope — the nav's amber dot (R3/R9). */
export function markerCountByScope(
    markers: readonly ReviewMarker[],
): Record<string, number> {
    const out: Record<string, number> = {};
    for (const marker of markers) {
        out[marker.scopeId] = (out[marker.scopeId] ?? 0) + 1;
    }
    return out;
}
